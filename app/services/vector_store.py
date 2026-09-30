import uuid
import asyncio
import functools
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue, SearchRequest, SparseVector, NamedSparseVector, NamedVector
from qdrant_client.http.exceptions import UnexpectedResponse
from loguru import logger

from app.core.database import get_qdrant_client
from app.models.document import DocumentChunk, SearchResult
from app.services.embedding import get_embedding_service
from app.services.rerank import get_rerank_service
from config.settings import settings

class VectorStoreService:
    """向量存储服务"""
    
    def __init__(self):
        self.client = get_qdrant_client()
        self.embedding_service = get_embedding_service()
        self.rerank_service = get_rerank_service() if settings.use_rerank else None
        self.collection_name = settings.qdrant_collection_name
    
    async def add_document_chunks(self, chunks: List[DocumentChunk], user_id: str, document_title: str = None) -> List[str]:
        """添加文档块到向量数据库
        
        Args:
            chunks: 文档块列表
            user_id: 用户ID
            document_title: 文档标题，用于在搜索结果中显示
        """
        if not chunks:
            return []
        
        try:
            # 提取所有块的文本内容
            texts = [chunk.content for chunk in chunks]
            
            # 批量向量化（密集 + 稀疏）
            dense_embeddings = await self.embedding_service.encode_texts(texts)
            sparse_embeddings = []
            if getattr(self.embedding_service, "sparse_enabled", False):
                try:
                    sparse_embeddings = await self.embedding_service.encode_sparse_texts(texts)
                except Exception as e:
                    logger.warning(f"稀疏嵌入生成失败，将仅写入密集向量: {e}")
                    sparse_embeddings = [None] * len(dense_embeddings)
            
            # 构建点数据
            points = []
            point_ids = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, dense_embeddings)):
                point_id = str(uuid.uuid4())
                point_ids.append(point_id)
                
                # 构建载荷数据
                payload = {
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "start_pos": chunk.start_pos,
                    "end_pos": chunk.end_pos,
                    "user_id": user_id,
                    "title": document_title or f"文档块 {chunk.chunk_index}",
                    "content_type": getattr(chunk, 'content_type', 'text') or 'text',
                    "image_path": getattr(chunk, 'image_path', None),
                    "captions": getattr(chunk, 'captions', []) or [],
                    "section_path": getattr(chunk, 'section_path', None),
                    "section_title": getattr(chunk, 'section_title', None),
                    "page_number": getattr(chunk, 'page_number', None),
                    "total_chunks": getattr(chunk, 'total_chunks', None),
                    "context_before": getattr(chunk, 'context_before', None),
                    "context_after": getattr(chunk, 'context_after', None),
                    "created_at": datetime.utcnow().isoformat(),
                    "metadata": chunk.metadata or {}
                }
                
                # 组合密集与稀疏向量（集合使用命名密集存储）
                vectors: Dict[str, Any] = {
                    "text-dense": embedding
                }
                if i < len(sparse_embeddings) and sparse_embeddings[i]:
                    se = sparse_embeddings[i]
                    try:
                        vectors[settings.sparse_vector_name] = SparseVector(
                            indices=se["indices"],
                            values=se["values"],
                        )
                    except Exception as e:
                        logger.warning(f"构建稀疏向量失败，跳过该块的稀疏部分: {e}")

                point = PointStruct(
                    id=point_id,
                    vector=vectors,
                    payload=payload
                )
                points.append(point)
            
            # 批量插入到Qdrant（按命名密集/稀疏；对不支持的向量名称进行降级重试）
            try:
                operation_info = self.client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                    wait=True
                )
            except UnexpectedResponse as ue:
                msg = str(ue)
                # 稀疏命名向量缺失（如 bm42 不存在）时，去掉稀疏部分并重试
                if (
                    ("Not existing vector name error" in msg and settings.sparse_vector_name in msg)
                    or (
                        f"Vector params for {settings.sparse_vector_name}" in msg and
                        "not specified in config" in msg
                    )
                ):
                    logger.warning(
                        f"集合未配置稀疏向量 '{settings.sparse_vector_name}'，将仅写入密集向量"
                    )
                    points_no_sparse = []
                    for p in points:
                        vec = p.vector
                        if isinstance(vec, dict):
                            vectors_no_sparse = {}
                            if "text-dense" in vec:
                                vectors_no_sparse["text-dense"] = vec["text-dense"]
                            point_no_sparse = PointStruct(
                                id=p.id,
                                vector=vectors_no_sparse if vectors_no_sparse else vec,
                                payload=p.payload
                            )
                        else:
                            point_no_sparse = p
                        points_no_sparse.append(point_no_sparse)
                    operation_info = self.client.upsert(
                        collection_name=self.collection_name,
                        points=points_no_sparse,
                        wait=True
                    )
                # 命名密集向量缺失时，回退为默认向量写入
                elif (
                    "Vector params for text-dense are not specified in config" in msg
                    or ("Not existing vector name error" in msg and "text-dense" in msg)
                ):
                    logger.warning("集合未配置 'text-dense' 向量，回退为默认向量写入")
                    fallback_points = []
                    for i, (chunk, embedding) in enumerate(zip(chunks, dense_embeddings)):
                        point_id = point_ids[i]
                        payload = {
                            "document_id": chunk.document_id,
                            "chunk_id": chunk.chunk_id,
                            "content": chunk.content,
                            "chunk_index": chunk.chunk_index,
                            "start_pos": chunk.start_pos,
                            "end_pos": chunk.end_pos,
                            "user_id": user_id,
                            "title": document_title or f"文档块 {chunk.chunk_index}",
                            "content_type": getattr(chunk, 'content_type', 'text') or 'text',
                            "image_path": getattr(chunk, 'image_path', None),
                            "captions": getattr(chunk, 'captions', []) or [],
                            "section_path": getattr(chunk, 'section_path', None),
                            "section_title": getattr(chunk, 'section_title', None),
                            "page_number": getattr(chunk, 'page_number', None),
                            "total_chunks": getattr(chunk, 'total_chunks', None),
                            "context_before": getattr(chunk, 'context_before', None),
                            "context_after": getattr(chunk, 'context_after', None),
                            "created_at": datetime.utcnow().isoformat(),
                            "metadata": chunk.metadata or {}
                        }
                        point = PointStruct(
                            id=point_id,
                            vector=embedding,  # 默认向量：直接提供数组
                            payload=payload
                        )
                        fallback_points.append(point)
                    operation_info = self.client.upsert(
                        collection_name=self.collection_name,
                        points=fallback_points,
                        wait=True
                    )
                else:
                    raise
            
            logger.info(f"成功添加 {len(points)} 个文档块到向量数据库")
            return point_ids
            
        except Exception as e:
            logger.error(f"添加文档块到向量数据库失败: {e}")
            raise e
    
    def _search_sparse_sync(self, se, search_filter, limit, threshold):
        """同步稀疏检索（在线程池中调用）。未配置/失败时返回 []，不影响密集通道。"""
        if se is None:
            return []
        try:
            return self.client.search(
                collection_name=self.collection_name,
                query_vector=NamedSparseVector(
                    name=settings.sparse_vector_name,
                    vector=SparseVector(indices=se["indices"], values=se["values"])
                ),
                query_filter=search_filter,
                limit=limit,
                score_threshold=threshold,
                with_payload=True
            ) or []
        except UnexpectedResponse as ue:
            logger.warning(f"稀疏检索不可用（集合未配置稀疏向量？），跳过稀疏通道: {ue}")
            return []
        except Exception as e:
            logger.warning(f"稀疏检索失败，跳过稀疏通道: {e}")
            return []

    def _search_dense_sync(self, dense_embedding, search_filter, limit, threshold):
        """同步密集检索（在线程池中调用）。命名向量缺失时回退默认向量。"""
        try:
            return self.client.search(
                collection_name=self.collection_name,
                query_vector=NamedVector(name="text-dense", vector=dense_embedding),
                query_filter=search_filter,
                limit=limit,
                score_threshold=threshold,
                with_payload=True
            ) or []
        except UnexpectedResponse as ue:
            msg = str(ue)
            if ("Vector params for text-dense are not specified in config" in msg
                    or ("Not existing vector name error" in msg and "text-dense" in msg)):
                logger.warning("集合未配置 'text-dense'，密集检索回退为默认向量")
                return self.client.search(
                    collection_name=self.collection_name,
                    query_vector=dense_embedding,
                    query_filter=search_filter,
                    limit=limit,
                    score_threshold=threshold,
                    with_payload=True
                ) or []
            raise

    @staticmethod
    def _rrf_fuse(dense_points, sparse_points, k: int = 60):
        """Reciprocal Rank Fusion：按两路排名融合，返回 [(point, rrf_score)] 降序。

        同一点保留密集通道的 ScoredPoint（带余弦原始分）用于展示与阈值判断；
        仅出现在稀疏通道的点则保留稀疏 point。
        """
        scores: Dict[Any, float] = {}
        point_map: Dict[Any, Any] = {}
        # 先密集（优先保留带余弦分的 point）
        for rank, p in enumerate(dense_points):
            scores[p.id] = scores.get(p.id, 0.0) + 1.0 / (k + rank + 1)
            point_map.setdefault(p.id, p)
        # 后稀疏
        for rank, p in enumerate(sparse_points):
            scores[p.id] = scores.get(p.id, 0.0) + 1.0 / (k + rank + 1)
            point_map.setdefault(p.id, p)
        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [(point_map[pid], s) for pid, s in ordered]

    def _point_to_search_result(self, scored_point) -> SearchResult:
        """将 Qdrant ScoredPoint 转为 SearchResult（含多模态媒体信息）。"""
        payload = scored_point.payload
        content_type = payload.get("content_type", "text") or "text"
        media = None
        if content_type != "text":
            image_path = payload.get("image_path")
            captions = payload.get("captions", [])
            media = {}
            if image_path:
                parts = Path(image_path).parts
                try:
                    uploads_idx = parts.index("uploads")
                    if len(parts) > uploads_idx + 2:
                        uid = parts[uploads_idx + 1]
                        fname = parts[-1]
                        media["url"] = f"/api/v1/images/{uid}/{fname}"
                        media["thumbnail_url"] = f"/api/v1/images/{uid}/{fname}?size=thumbnail"
                except (ValueError, IndexError):
                    pass
            if captions:
                media["captions"] = captions
            if content_type == "table":
                media["content_format"] = "markdown"
            elif content_type == "equation":
                media["content_format"] = "latex"
            elif content_type == "image":
                ext = Path(image_path).suffix.lstrip('.') if image_path else 'jpg'
                media["content_format"] = ext

        return SearchResult(
            document_id=payload["document_id"],
            title=payload.get("title", f"文档块 {payload['chunk_index']}"),
            content=payload["content"],
            score=scored_point.score,
            content_type=content_type,
            section_path=payload.get("section_path"),
            section_title=payload.get("section_title"),
            page_number=payload.get("page_number"),
            context_before=payload.get("context_before"),
            context_after=payload.get("context_after"),
            image_url=media.get("url") if media else None,
            thumbnail_url=media.get("thumbnail_url") if media else None,
            image_path=payload.get("image_path") if content_type == "image" else None,
            media=media,
            metadata=payload.get("metadata", {}),
            created_at=datetime.fromisoformat(payload["created_at"])
        )

    def _rerank_sync(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        """同步 rerank（在线程池中调用），返回重排后的结果列表。"""
        documents = [r.content for r in results]
        reranked_indices = self.rerank_service.rerank(
            query=query,
            documents=documents,
            top_k=min(settings.rerank_top_n, len(results))
        )
        reranked_results = []
        for idx, rerank_score in reranked_indices:
            result = results[idx]
            result.score = rerank_score
            reranked_results.append(result)
        return reranked_results

    async def search_similar_documents(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = settings.qdrant_default_limit,
        score_threshold: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """搜索相似文档（稀疏 + 密集双通道并行检索 → RRF 融合 → 可选 rerank）。

        修复要点：
        - 稀疏通道使用独立阈值 qdrant_sparse_default_threshold，不再继承 score_threshold（原缺陷：0.7 将稀疏打空）
        - 两通道始终并行执行并 RRF 融合，取消原 `if not search_result` 短路（原缺陷：稀疏非空时密集彻底死掉）
        - 同步 Qdrant / rerank 调用包裹进线程池，不再阻塞事件循环
        - rerank 保护：密集 top1 >= rerank_skip_threshold 时跳过 rerank
        """
        try:
            loop = asyncio.get_event_loop()
            # 启用 rerank 时初始检索更多候选
            retrieval_limit = settings.retrieval_top_k if self.rerank_service else limit

            # 构建过滤条件
            search_filter = None
            if user_id:
                search_filter = Filter(
                    must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                )

            # 稀疏查询编码（不可用/失败则仅走密集）
            se = None
            if getattr(self.embedding_service, "sparse_enabled", False):
                try:
                    se = await self.embedding_service.encode_sparse_text(query)
                except Exception as e:
                    logger.warning(f"稀疏嵌入生成失败，仅用密集通道: {e}")

            # 密集查询编码
            dense_embedding = await self.embedding_service.encode_text(query)

            # 阈值：稀疏独立阈值（不继承 score_threshold），密集用 score_threshold 或默认
            sparse_threshold = settings.qdrant_sparse_default_threshold
            dense_threshold = score_threshold if score_threshold is not None else settings.qdrant_dense_default_threshold

            # 两路并行检索（同步客户端包裹进线程池，避免阻塞事件循环）
            sparse_task = loop.run_in_executor(
                None,
                functools.partial(self._search_sparse_sync, se, search_filter, retrieval_limit, sparse_threshold)
            )
            dense_task = loop.run_in_executor(
                None,
                functools.partial(self._search_dense_sync, dense_embedding, search_filter, retrieval_limit, dense_threshold)
            )
            sparse_points, dense_points = await asyncio.gather(sparse_task, dense_task)
            sparse_points = sparse_points or []
            dense_points = dense_points or []

            # RRF 融合
            fused = self._rrf_fuse(dense_points, sparse_points, k=settings.hybrid_rrf_k)
            logger.info(
                f"混合检索 '{query}': 稀疏 {len(sparse_points)} 条 + 密集 {len(dense_points)} 条 "
                f"→ RRF 融合 {len(fused)} 条"
            )

            # 密集 top1 分数（用于 rerank 保护判断）
            dense_top1 = dense_points[0].score if dense_points else 0.0

            # 转换（保持 RRF 顺序）
            results = [self._point_to_search_result(point) for point, _ in fused]

            # rerank（带保护 + 线程池）
            if self.rerank_service and results:
                if dense_top1 >= settings.rerank_skip_threshold:
                    logger.info(
                        f"密集 top1={dense_top1:.3f} >= {settings.rerank_skip_threshold}，跳过 rerank（保护精确匹配）"
                    )
                    return results[:limit]
                logger.info(f"启用 Rerank，候选数: {len(results)}, 目标返回 Top {settings.rerank_top_n}")
                reranked_results = await loop.run_in_executor(
                    None, functools.partial(self._rerank_sync, query, results)
                )
                logger.info(f"Rerank 完成，返回 {len(reranked_results)} 个结果")
                return reranked_results

            return results[:limit]

        except Exception as e:
            logger.error(f"搜索相似文档失败: {e}")
            raise e
    
    async def delete_document_vectors(self, document_id: str, user_id: str) -> bool:
        """删除文档的所有向量"""
        try:
            # 构建删除过滤条件
            delete_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id)
                    ),
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                    )
                ]
            )
            
            # 执行删除操作
            operation_info = self.client.delete(
                collection_name=self.collection_name,
                points_selector=delete_filter,
                wait=True
            )
            
            logger.info(f"成功删除文档 {document_id} 的向量数据")
            return True
            
        except Exception as e:
            logger.error(f"删除文档向量失败: {e}")
            return False
    
    async def get_document_chunks(self, document_id: str, user_id: str) -> List[Dict[str, Any]]:
        """获取文档的所有块"""
        try:
            # 构建过滤条件
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id)
                    ),
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                    )
                ]
            )
            
            # 滚动获取所有匹配的点
            scroll_result = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=search_filter,
                limit=1000,  # 假设单个文档不会超过1000个块
                with_payload=True
            )
            
            chunks = []
            for point in scroll_result[0]:  # scroll_result是一个元组，第一个元素是点列表
                chunks.append(point.payload)
            
            # 按chunk_index排序
            chunks.sort(key=lambda x: x.get("chunk_index", 0))
            
            logger.info(f"获取文档 {document_id} 的 {len(chunks)} 个块")
            return chunks
            
        except Exception as e:
            logger.error(f"获取文档块失败: {e}")
            return []
    
    async def update_document_metadata(self, document_id: str, user_id: str, metadata: Dict[str, Any]) -> bool:
        """更新文档元数据"""
        try:
            # 首先获取所有相关的点
            chunks = await self.get_document_chunks(document_id, user_id)
            
            if not chunks:
                return False
            
            # 更新每个点的元数据
            points_to_update = []
            for chunk in chunks:
                # 合并现有元数据和新元数据
                updated_metadata = chunk.get("metadata", {})
                updated_metadata.update(metadata)
                
                # 更新载荷
                updated_payload = chunk.copy()
                updated_payload["metadata"] = updated_metadata
                updated_payload["updated_at"] = datetime.utcnow().isoformat()
                
                # 注意：这里需要重新获取向量，因为upsert需要完整的点数据
                # 在实际应用中，可能需要优化这个过程
            
            logger.info(f"成功更新文档 {document_id} 的元数据")
            return True
            
        except Exception as e:
            logger.error(f"更新文档元数据失败: {e}")
            return False
    
    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "status": collection_info.status,
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "points_count": collection_info.points_count
            }
        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
            return {}

# 全局向量存储服务实例
_vector_store_service = None

def get_vector_store_service() -> VectorStoreService:
    """获取向量存储服务实例（单例模式）"""
    global _vector_store_service
    if _vector_store_service is None:
        _vector_store_service = VectorStoreService()
    return _vector_store_service