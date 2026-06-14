"""
系统管理API - 内存监控、健康检查等
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/system", tags=["system"])


class MemoryStatsResponse(BaseModel):
    """内存统计响应"""
    timestamp: str
    process: dict
    system: dict
    components: Optional[dict] = None


class MemoryCheckResponse(BaseModel):
    """内存检查响应"""
    threshold_mb: int
    current_mb: float
    exceeded: bool
    usage_percent: float
    recommendation: str


@router.get("/memory", response_model=MemoryStatsResponse, summary="获取内存使用统计")
async def get_memory_stats():
    """
    获取详细的内存使用统计信息
    
    包括:
    - 进程内存(RSS/VMS)
    - 系统内存
    - 各组件使用情况(文档缓存、Redis、模型等)
    """
    try:
        from app.services.memory_monitor import get_memory_monitor
        monitor = get_memory_monitor()
        stats = monitor.get_memory_stats()
        
        return MemoryStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取内存统计失败: {str(e)}")


@router.get("/memory/check", response_model=MemoryCheckResponse, summary="检查内存是否超标")
async def check_memory_threshold(threshold_mb: int = 2048):
    """
    检查当前内存使用是否超过阈值
    
    Args:
        threshold_mb: 内存阈值(MB),默认2048MB
        
    Returns:
        检查结果和建议
    """
    try:
        from app.services.memory_monitor import get_memory_monitor
        monitor = get_memory_monitor()
        result = monitor.check_threshold(threshold_mb)
        
        return MemoryCheckResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"内存检查失败: {str(e)}")


@router.post("/memory/cleanup", summary="紧急清理内存")
async def emergency_cleanup():
    """
    执行紧急内存清理
    
    操作包括:
    1. 清空文档缓存
    2. 清空Redis缓存
    3. 强制垃圾回收
    
    ⚠️ 慎用!会导致后续查询变慢
    """
    try:
        from app.services.memory_monitor import get_memory_monitor
        monitor = get_memory_monitor()
        result = monitor.emergency_cleanup()
        
        return {
            "success": True,
            "cleanup_result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"内存清理失败: {str(e)}")


@router.get("/health/detailed", summary="详细健康检查")
async def detailed_health_check():
    """
    详细的系统健康检查
    
    包括:
    - 内存状态
    - 数据库连接
    - Redis连接
    - Qdrant连接
    - Neo4j连接
    """
    health = {
        "status": "healthy",
        "checks": {}
    }
    
    # 内存检查
    try:
        from app.services.memory_monitor import get_memory_monitor
        monitor = get_memory_monitor()
        mem_stats = monitor.get_memory_stats()
        health["checks"]["memory"] = {
            "status": "ok",
            "rss_mb": mem_stats["process"]["rss_mb"],
            "usage_percent": mem_stats["process"]["percent"]
        }
    except Exception as e:
        health["checks"]["memory"] = {"status": "error", "error": str(e)}
        health["status"] = "degraded"
    
    # Redis检查
    try:
        from app.services.document_cache import get_document_metadata_cache
        cache = get_document_metadata_cache()
        if cache.health_check():
            health["checks"]["redis"] = {"status": "ok"}
        else:
            health["checks"]["redis"] = {"status": "error"}
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["redis"] = {"status": "error", "error": str(e)}
        health["status"] = "degraded"
    
    # Qdrant检查
    try:
        from app.core.database import get_qdrant_client
        client = get_qdrant_client()
        client.http_api.collections_api.collections_list()
        health["checks"]["qdrant"] = {"status": "ok"}
    except Exception as e:
        health["checks"]["qdrant"] = {"status": "error", "error": str(e)}
        health["status"] = "degraded"
    
    # Neo4j检查
    try:
        from config.settings import settings
        if settings.neo4j_enabled:
            from app.services.knowledge_graph import get_knowledge_graph_service
            kg_service = get_knowledge_graph_service()
            if kg_service.available:
                health["checks"]["neo4j"] = {"status": "ok"}
            else:
                health["checks"]["neo4j"] = {"status": "unavailable"}
        else:
            health["checks"]["neo4j"] = {"status": "disabled"}
    except Exception as e:
        health["checks"]["neo4j"] = {"status": "error", "error": str(e)}
    
    return health
