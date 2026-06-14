from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os
import sys
import asyncio
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 预加载 .env 并注入 HuggingFace 缓存与镜像相关变量，确保每次启动都使用本地缓存
try:
    load_dotenv()
except Exception:
    pass

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HOME", os.path.join(_PROJECT_ROOT, "huggingface_cache"))
os.environ.setdefault("FASTEMBED_CACHE_PATH", os.environ.get("HF_HOME", os.path.join(_PROJECT_ROOT, "huggingface_cache")))
# 设置离线模式，使用本地缓存，不连接HuggingFace
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from config.settings import settings
from app.core.database import init_qdrant
from app.core.sql import init_mysql_tables
from app.api import api_router
from app.core.logging import init_app_logging
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.documents import router as documents_router
from app.api.scrape import router as scrape_router
from app.api.llm import router as llm_router
from app.api.conversations import router as conversations_router
from app.api.stats import router as stats_router
from app.api.sessions import router as sessions_router
from app.api.system import router as system_router

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    from loguru import logger
    logger.info("应用启动：初始化数据库和Qdrant集合")
    # 初始化MySQL表结构
    init_mysql_tables()
    
    # 从MySQL加载已有文档到内存存储（解决重启后数据丢失问题）
    try:
        from app.services.document_service import get_document_service
        document_service = get_document_service()
        loaded_count = document_service.load_documents_from_db()
        logger.info(f"从数据库加载了 {loaded_count} 个文档到内存")
    except Exception as e:
        logger.warning(f"加载数据库文档失败: {e}")
    
    # 单用户模式：不再需要初始化默认管理员
    # 初始化Qdrant集合（增加容错，不阻断应用启动）
    try:
        await init_qdrant()
        setattr(app.state, "qdrant_ready", True)
    except Exception as e:
        setattr(app.state, "qdrant_ready", False)
        logger.error(f"Qdrant未就绪，向量检索相关功能暂不可用: {e}")
    
    # 启动定时清理任务
    from app.tasks.cleanup_tasks import cleanup_expired_sessions_task
    cleanup_task = asyncio.create_task(cleanup_expired_sessions_task())
    logger.info("已启动定时清理过期会话任务")

    # 初始化知识图谱连接（Neo4j）
    if settings.neo4j_enabled:
        try:
            from app.services.knowledge_graph import get_knowledge_graph_service
            kg_service = get_knowledge_graph_service()
            if kg_service.available:
                logger.info("Neo4j 知识图谱服务已就绪")
            else:
                logger.warning("Neo4j 知识图谱服务不可用")
        except Exception as e:
            logger.warning(f"知识图谱初始化失败: {e}")
    
    logger.info("应用启动：初始化完成")
    yield
    # 关闭时清理资源
    logger.info("应用关闭：清理资源")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.info("定时清理任务已取消")

    # 关闭知识图谱连接
    if settings.neo4j_enabled:
        try:
            from app.services.knowledge_graph import get_knowledge_graph_service
            kg_service = get_knowledge_graph_service()
            kg_service.close()
        except Exception:
            pass

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于Qdrant向量数据库的个人知识库系统",
    lifespan=lifespan
)

# 初始化统一日志（输出到控制台与文件、请求/响应日志、异常处理）
init_app_logging(app)

# 添加 CORS 中间件（必须在路由之前）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加可信主机中间件
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # 生产环境中应该限制具体主机
)

# 定义根路由（必须在静态文件挂载之前）
@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, 'index.html'))

# 注册API路由
app.include_router(auth_router, prefix="/api/v1")  # 已禁用的认证端点
app.include_router(users_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(scrape_router, prefix="/api/v1")
app.include_router(llm_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(stats_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(system_router)  # system router already has /api/v1/system prefix

# 挂载静态文件目录（必须在路由之后）
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
async def health_check():
    kg_status = "disabled"
    if settings.neo4j_enabled:
        try:
            from app.services.knowledge_graph import get_knowledge_graph_service
            kg_service = get_knowledge_graph_service()
            kg_status = "ready" if kg_service.available else "unavailable"
        except Exception:
            kg_status = "error"
    return {
        "status": "healthy",
        "qdrant_ready": getattr(app.state, "qdrant_ready", None),
        "knowledge_graph": kg_status,
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.debug
    )