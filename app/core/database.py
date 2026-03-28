from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, CollectionStatus, SparseVectorParams
from qdrant_client.http.exceptions import UnexpectedResponse
from config.settings import settings
from loguru import logger
import asyncio
import httpx

# 全局Qdrant客户端实例
qdrant_client: QdrantClient = None

def get_qdrant_client() -> QdrantClient:
    """获取Qdrant客户端实例（使用 gRPC 连接）"""
    global qdrant_client
    if qdrant_client is None:
        # 使用 gRPC 连接（端口 6334）绕过 httpx 的 502 问题
        if settings.qdrant_api_key:
            qdrant_client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,  # 6334 gRPC 端口
                api_key=settings.qdrant_api_key,
                timeout=60.0,
                prefer_grpc=True,  # 强制使用 gRPC
                grpc_port=settings.qdrant_port
            )
        else:
            qdrant_client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,  # 6334 gRPC 端口
                timeout=60.0,
                prefer_grpc=True,  # 强制使用 gRPC
                grpc_port=settings.qdrant_port
            )
        logger.info(f"连接到 Qdrant 服务器 (gRPC): {settings.qdrant_host}:{settings.qdrant_port}")
    return qdrant_client

async def init_qdrant():
    """初始化Qdrant数据库和集合（使用 gRPC）"""
    try:
        client = get_qdrant_client()
        
        # 检查集合是否存在（直接使用 gRPC 客户端）
        exists = False
        try:
            info = client.get_collection(settings.qdrant_collection_name)
            exists = True
            logger.info(f"集合 '{settings.qdrant_collection_name}' 已存在")
        except Exception as e:
            logger.info(f"集合 '{settings.qdrant_collection_name}' 不存在: {e}")
            exists = False

        if not exists:
            # 创建新集合（包含稀疏向量配置用于BM42）
            sparse_config = None
            if settings.use_sparse_bm42:
                # 当前客户端版本 SparseVectorParams 仅支持 index 参数
                sparse_config = {settings.sparse_vector_name: SparseVectorParams()}
            client.create_collection(
                collection_name=settings.qdrant_collection_name,
                vectors_config={
                    "text-dense": VectorParams(
                        size=settings.vector_size,
                        distance=Distance.COSINE
                    )
                },
                sparse_vectors_config=sparse_config
            )
            logger.info(
                f"成功创建集合 '{settings.qdrant_collection_name}'"
                + (f"，包含稀疏向量 '{settings.sparse_vector_name}' 配置" if sparse_config else "")
            )
        else:
            # 集合已存在：检查是否需要重建以启用命名密集向量与稀疏向量
            try:
                url = f"http://{settings.qdrant_host}:{settings.qdrant_port}/collections/{settings.qdrant_collection_name}"
                resp = httpx.get(url, timeout=3.0)
                if resp.status_code == 200:
                    result = resp.json().get("result", {})
                    config = result.get("config", {})

                    needs_recreate = False
                    # 检查密集向量配置
                    vectors_cfg = config.get("vectors") or config.get("vectors_config") or {}
                    if isinstance(vectors_cfg, dict):
                        # 命名密集
                        if "text-dense" not in vectors_cfg:
                            needs_recreate = True
                        else:
                            dense_cfg = vectors_cfg.get("text-dense") or {}
                            size = dense_cfg.get("size") if isinstance(dense_cfg, dict) else None
                            if size and int(size) != int(settings.vector_size):
                                needs_recreate = True
                    else:
                        # 非命名密集（默认向量），需要重建为命名密集
                        needs_recreate = True

                    # 检查稀疏配置（BM42）
                    if settings.use_sparse_bm42:
                        sparse_cfg = config.get("sparse_vectors") or config.get("sparse_vectors_config") or {}
                        has_bm42 = isinstance(sparse_cfg, dict) and (settings.sparse_vector_name in list(sparse_cfg.keys()))
                        if not has_bm42:
                            needs_recreate = True

                    if needs_recreate:
                        if not settings.qdrant_allow_recreate_on_mismatch:
                            logger.warning(
                                "检测到集合配置不匹配，但已禁用自动重建。为避免数据丢失，跳过重建。"
                                "如需重建，请设置环境变量 'QDRANT_ALLOW_RECREATE_ON_MISMATCH=true' 后重启。"
                            )
                        else:
                            try:
                                client.recreate_collection(
                                    collection_name=settings.qdrant_collection_name,
                                    vectors_config={
                                        "text-dense": VectorParams(size=settings.vector_size, distance=Distance.COSINE)
                                    },
                                    sparse_vectors_config={
                                        settings.sparse_vector_name: SparseVectorParams()
                                    } if settings.use_sparse_bm42 else None,
                                )
                                logger.info(
                                    f"已重建集合 '{settings.qdrant_collection_name}'：命名密集 'text-dense'(size={settings.vector_size})"
                                    + (f"，并启用稀疏 '{settings.sparse_vector_name}'" if settings.use_sparse_bm42 else "")
                                )
                            except UnexpectedResponse as ue:
                                logger.error(f"重建集合失败(服务端响应异常): {ue}")
                                raise
                            except Exception as e:
                                logger.error(f"重建集合失败: {e}")
                                raise
                    else:
                        logger.info(f"集合 '{settings.qdrant_collection_name}' 已具备所需命名密集与稀疏配置")
                else:
                    logger.warning(f"获取集合配置失败，状态码: {resp.status_code}")
            except Exception as e:
                logger.warning(f"检查/重建集合配置时出错: {e}")

        # 等待集合准备就绪
        await wait_for_collection_ready(client, settings.qdrant_collection_name)
        
    except Exception as e:
        logger.error(f"初始化Qdrant失败: {e}")
        raise e

async def wait_for_collection_ready(client: QdrantClient, collection_name: str, timeout: int = 30):
    """等待集合准备就绪"""
    for _ in range(timeout):
        try:
                # 优先使用客户端，失败则回退到REST
                try:
                    collection_info = client.get_collection(collection_name)
                    status = getattr(collection_info, "status", None)
                    if status == CollectionStatus.GREEN or status == "green":
                        logger.info(f"集合 '{collection_name}' 已准备就绪")
                        return
                except Exception:
                    url = f"http://{settings.qdrant_host}:{settings.qdrant_port}/collections/{collection_name}"
                    resp = httpx.get(url, timeout=2.0)
                    if resp.status_code == 200:
                        status = resp.json().get("result", {}).get("status")
                        if str(status).lower() == "green":
                            logger.info(f"集合 '{collection_name}' 已准备就绪 (REST)")
                            return
        except Exception as e:
            logger.warning(f"检查集合状态时出错: {e}")
        
        await asyncio.sleep(1)
    
    raise TimeoutError(f"等待集合 '{collection_name}' 准备就绪超时")

def close_qdrant_connection():
    """关闭Qdrant连接"""
    global qdrant_client
    if qdrant_client:
        qdrant_client.close()
        qdrant_client = None
        logger.info("Qdrant连接已关闭")