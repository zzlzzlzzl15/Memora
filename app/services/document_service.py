import uuid
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
import os
import json
from pathlib import Path
import threading
from collections import defaultdict

from app.models.document import (
    DocumentCreate, DocumentUpdate, Document, DocumentInDB, 
    DocumentStatus, DocumentType, DocumentChunk, SearchQuery, SearchResult, SearchResponse
)
from app.services.document_processor import get_document_processor
from app.services.vector_store import get_vector_store_service
from app.services.embedding import get_embedding_service
from app.services.hybrid_fusion import get_query_mode_router
from app.services.query_cache import get_query_cache
from config.settings import settings

# 优化的内存存储（添加索引、线程安全保护和懒加载机制）
class InMemoryDocumentStore:
    """内存文档存储（优化版：支持懒加载、LRU缓存、并发安全和多维索引）"""
    
    def __init__(self, max_cached_documents: int = 100):
        # 主存储 - 只缓存最近访问的完整文档
        self.documents: Dict[str, DocumentInDB] = {}
        
        # 元数据存储 - 所有文档的轻量级元数据(不含content)
        self.document_metadata: Dict[str, Dict[str, Any]] = {}
        
        # 多维度索引（提升查询性能）
        self.user_documents: Dict[str, List[str]] = defaultdict(list)  # user_id -> [document_ids]
        self.status_index: Dict[str, List[str]] = defaultdict(list)    # status -> [document_ids]
        self.type_index: Dict[str, List[str]] = defaultdict(list)      # file_type -> [document_ids]
        
        # LRU缓存管理
        self.access_order: List[str] = []  # 记录访问顺序(最新在前)
        self.max_cached_documents = max_cached_documents  # 最大缓存文档数
        
        # 读写锁（保证线程安全）
        self.lock = threading.RLock()
        
        logger.info(f"InMemoryDocumentStore初始化完成（懒加载模式，最大缓存{max_cached_documents}个文档）")
    
    def create_document(self, document: DocumentInDB) -> DocumentInDB:
        """创建文档（线程安全）"""
        with self.lock:
            doc_id = document.document_id
            
            # 存储完整文档到缓存
            self.documents[doc_id] = document
            
            # 同时存储轻量级元数据
            self.document_metadata[doc_id] = {
                'document_id': doc_id,
                'user_id': document.user_id,
                'title': document.title,
                'file_path': document.file_path,
                'file_size': document.file_size,
                'file_type': document.file_type,
                'status': document.status,
                'vector_id': document.vector_id,
                'tags': document.tags,
                'created_at': document.created_at,
                'updated_at': document.updated_at,
                'has_content': document.content is not None and len(document.content) > 0
            }
            
            # 更新多维索引
            self.user_documents[document.user_id].append(doc_id)
            self.status_index[document.status].append(doc_id)
            self.type_index[document.file_type].append(doc_id)
            
            # 更新访问顺序
            self._update_access_order(doc_id)
            
            logger.debug(f"文档已创建: {doc_id}, 用户: {document.user_id}")
            return document
    
    def get_document(self, document_id: str) -> Optional[DocumentInDB]:
        """获取文档（线程安全，支持懒加载提示）"""
        with self.lock:
            doc = self.documents.get(document_id)
            if doc:
                # 更新访问顺序(LRU)
                self._update_access_order(document_id)
            return doc
    
    def get_document_metadata(self, document_id: str) -> Optional[Dict[str, Any]]:
        """获取文档元数据（轻量级，不含content）"""
        with self.lock:
            return self.document_metadata.get(document_id)
    
    def update_document(self, document_id: str, update_data: Dict[str, Any]) -> Optional[DocumentInDB]:
        """更新文档（线程安全，支持索引更新和元数据同步）"""
        with self.lock:
            if document_id not in self.documents:
                return None
            
            document = self.documents[document_id]
            old_status = document.status
            old_type = document.file_type
            
            # 更新文档字段
            for key, value in update_data.items():
                if hasattr(document, key):
                    setattr(document, key, value)
            
            document.updated_at = datetime.utcnow()
            
            # 同步更新元数据
            if document_id in self.document_metadata:
                meta = self.document_metadata[document_id]
                for key, value in update_data.items():
                    if key in meta:
                        meta[key] = value
                meta['updated_at'] = document.updated_at
                meta['has_content'] = document.content is not None and len(document.content) > 0
            
            # 如果状态或类型变更，更新索引
            if 'status' in update_data and update_data['status'] != old_status:
                self._update_status_index(document_id, old_status, document.status)
            
            if 'file_type' in update_data and update_data['file_type'] != old_type:
                self._update_type_index(document_id, old_type, document.file_type)
            
            # 更新访问顺序
            self._update_access_order(document_id)
            
            return document
    
    def delete_document(self, document_id: str) -> bool:
        """删除文档（线程安全，清理所有索引和元数据）"""
        with self.lock:
            if document_id not in self.documents:
                return False
            
            document = self.documents[document_id]
            user_id = document.user_id
            status = document.status
            file_type = document.file_type
            
            # 从主存储删除
            del self.documents[document_id]
            
            # 从元数据存储删除
            self.document_metadata.pop(document_id, None)
            
            # 从访问顺序中删除
            try:
                self.access_order.remove(document_id)
            except ValueError:
                pass
            
            # 从所有索引中删除
            self._remove_from_index(self.user_documents[user_id], document_id)
            self._remove_from_index(self.status_index[status], document_id)
            self._remove_from_index(self.type_index[file_type], document_id)
            
            logger.debug(f"文档已删除: {document_id}")
            return True
    
    def list_user_documents(self, user_id: str, skip: int = 0, limit: int = 100, include_deleted: bool = False) -> List[DocumentInDB]:
        """列出用户的文档（线程安全，使用索引优化，返回轻量级对象）"""
        with self.lock:
            # 使用索引快速定位用户文档
            document_ids = self.user_documents.get(user_id, [])
            
            # 根据参数决定是否包含已删除的文档
            if include_deleted:
                valid_ids = [doc_id for doc_id in document_ids if doc_id in self.document_metadata]
            else:
                # 过滤掉已删除的文档（非DELETED状态）
                valid_ids = [
                    doc_id for doc_id in document_ids 
                    if doc_id in self.document_metadata and 
                    self.document_metadata[doc_id].get('status') != DocumentStatus.DELETED
                ]
            
            # 按创建时间倒序排序（从元数据中读取）
            valid_ids.sort(
                key=lambda x: self.document_metadata[x].get('created_at'), 
                reverse=True
            )
            
            # 分页并构建轻量级文档对象
            page_ids = valid_ids[skip:skip + limit]
            docs = []
            for doc_id in page_ids:
                # 优先从缓存获取完整文档
                if doc_id in self.documents:
                    docs.append(self.documents[doc_id])
                    # 更新访问顺序
                    self._update_access_order(doc_id)
                else:
                    # 否则从元数据构建轻量级对象
                    meta = self.document_metadata[doc_id]
                    from app.models.document import DocumentInDB
                    doc = DocumentInDB(
                        document_id=meta['document_id'],
                        user_id=meta['user_id'],
                        title=meta['title'],
                        file_path=meta['file_path'],
                        file_size=meta['file_size'],
                        file_type=meta['file_type'],
                        content=None,  # 懒加载时不加载content
                        status=meta['status'],
                        progress=0,
                        error_message=None,
                        vector_id=meta['vector_id'],
                        tags=meta['tags'],
                        metadata={},
                        created_at=meta['created_at'],
                        updated_at=meta['updated_at']
                    )
                    docs.append(doc)
            
            return docs
    
    def count_user_documents(self, user_id: str, include_deleted: bool = False) -> int:
        """统计用户文档数量（线程安全，基于元数据）"""
        with self.lock:
            document_ids = self.user_documents.get(user_id, [])
            
            if include_deleted:
                return len([doc_id for doc_id in document_ids if doc_id in self.document_metadata])
            else:
                return len([
                    doc_id for doc_id in document_ids 
                    if doc_id in self.document_metadata and 
                    self.document_metadata[doc_id].get('status') != DocumentStatus.DELETED
                ])
    
    # --- 私有辅助方法 ---
    def _update_access_order(self, document_id: str) -> None:
        """更新LRU访问顺序（将文档移到最前面）"""
        try:
            self.access_order.remove(document_id)
        except ValueError:
            pass
        self.access_order.insert(0, document_id)
        
        # 如果超过最大缓存数，淘汰最旧的文档
        if len(self.access_order) > self.max_cached_documents:
            evicted_id = self.access_order.pop()
            # 从完整文档缓存中移除，但保留元数据
            if evicted_id in self.documents:
                del self.documents[evicted_id]
                logger.debug(f"LRU缓存淘汰: {evicted_id}")
    
    def _remove_from_index(self, index_list: List[str], document_id: str) -> None:
        """从索引列表中移除文档ID"""
        try:
            index_list.remove(document_id)
        except ValueError:
            pass  # 如果不存在，忽略
    
    def _update_status_index(self, document_id: str, old_status: str, new_status: str) -> None:
        """更新状态索引"""
        self._remove_from_index(self.status_index[old_status], document_id)
        self.status_index[new_status].append(document_id)
    
    def _update_type_index(self, document_id: str, old_type: str, new_type: str) -> None:
        """更新类型索引"""
        self._remove_from_index(self.type_index[old_type], document_id)
        self.type_index[new_type].append(document_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取存储统计信息（线程安全）"""
        with self.lock:
            return {
                "total_documents": len(self.document_metadata),  # 总文档数（基于元数据）
                "cached_documents": len(self.documents),  # 缓存的完整文档数
                "max_cache_size": self.max_cached_documents,
                "total_users": len(self.user_documents),
                "by_status": {status: len(docs) for status, docs in self.status_index.items()},
                "by_type": {file_type: len(docs) for file_type, docs in self.type_index.items()}
            }
    
    def load_full_document(self, document_id: str, full_document: DocumentInDB) -> DocumentInDB:
        """将完整文档加载到缓存中（用于懒加载场景）"""
        with self.lock:
            # 存入完整文档缓存
            self.documents[document_id] = full_document
            
            # 更新元数据
            if document_id not in self.document_metadata:
                self.document_metadata[document_id] = {
                    'document_id': full_document.document_id,
                    'user_id': full_document.user_id,
                    'title': full_document.title,
                    'file_path': full_document.file_path,
                    'file_size': full_document.file_size,
                    'file_type': full_document.file_type,
                    'status': full_document.status,
                    'vector_id': full_document.vector_id,
                    'tags': full_document.tags,
                    'created_at': full_document.created_at,
                    'updated_at': full_document.updated_at,
                    'has_content': full_document.content is not None and len(full_document.content) > 0
                }
            else:
                self.document_metadata[document_id]['has_content'] = True
            
            # 更新访问顺序（可能触发LRU淘汰）
            self._update_access_order(document_id)
            
            logger.debug(f"完整文档已加载到缓存: {document_id}")
            return full_document
    
    def is_document_cached(self, document_id: str) -> bool:
        """检查文档是否在缓存中（有完整内容）"""
        with self.lock:
            return document_id in self.documents

class DocumentService:
    """文档服务"""

    # 旧状态映射表：兼容已有数据
    _STATUS_MAP = {
        'uploading': DocumentStatus.PENDING,
        'processing': DocumentStatus.PENDING,
        'indexed': DocumentStatus.COMPLETED,
    }

    @staticmethod
    def _map_old_status(status_str: str) -> DocumentStatus:
        """将旧状态字符串映射到新状态枚举"""
        try:
            status = DocumentStatus(status_str)
            # 兼容旧数据映射
            return DocumentService._STATUS_MAP.get(status_str, status)
        except ValueError:
            logger.warning(f"未知文档状态: {status_str}, 回退到 PENDING")
            return DocumentStatus.PENDING

    def __init__(self):
        self.store = InMemoryDocumentStore(max_cached_documents=100)  # 最多缓存100个完整文档
        self.processor = get_document_processor()
        self.vector_store = get_vector_store_service()
        self.embedding_service = get_embedding_service()
        
        # 初始化Redis缓存
        from app.services.document_cache import get_document_metadata_cache
        self.metadata_cache = get_document_metadata_cache()

    def load_documents_from_db(self) -> int:
        """从数据库加载所有文档元数据到内存存储（应用启动时调用，懒加载模式）"""
        try:
            from app.core.sql import get_db
            from app.models.db_models import DocumentORM
            from app.models.document import DocumentInDB, DocumentStatus
            import json
            
            db = next(get_db())
            
            # 查询所有未软删除的文档
            documents_orm = db.query(DocumentORM).filter(
                DocumentORM.is_deleted == False
            ).all()
            
            loaded_count = 0
            for doc_orm in documents_orm:
                # 解析JSON字段
                tags = json.loads(doc_orm.tags) if doc_orm.tags else []
                metadata = json.loads(doc_orm.doc_metadata) if doc_orm.doc_metadata else {}
                
                # 创建DocumentInDB对象（不加载content，实现懒加载）
                document = DocumentInDB(
                    document_id=doc_orm.doc_id,
                    user_id=doc_orm.user_id,
                    title=doc_orm.title,
                    file_path=doc_orm.file_path,
                    file_size=doc_orm.file_size,
                    file_type=doc_orm.doc_type,
                    content=None,  # 懒加载：不加载内容
                    status=doc_orm.status,
                    progress=getattr(doc_orm, 'progress', 0),
                    error_message=getattr(doc_orm, 'error_message', None),
                    vector_id=doc_orm.vector_id,
                    tags=tags,
                    metadata=metadata,
                    created_at=doc_orm.created_at,
                    updated_at=doc_orm.updated_at
                )
                
                # 添加到内存存储（只存元数据）
                self.store.create_document(document)
                
                # 同时写入Redis缓存
                meta_for_cache = {
                    'document_id': doc_orm.doc_id,
                    'user_id': doc_orm.user_id,
                    'title': doc_orm.title,
                    'file_path': doc_orm.file_path,
                    'file_size': doc_orm.file_size,
                    'file_type': doc_orm.doc_type,
                    'status': doc_orm.status,
                    'vector_id': doc_orm.vector_id,
                    'tags': tags,
                    'created_at': doc_orm.created_at.isoformat() if hasattr(doc_orm.created_at, 'isoformat') else str(doc_orm.created_at),
                    'updated_at': doc_orm.updated_at.isoformat() if hasattr(doc_orm.updated_at, 'isoformat') else str(doc_orm.updated_at),
                    'has_content': False
                }
                self.metadata_cache.set(doc_orm.doc_id, meta_for_cache)
                
                loaded_count += 1
            
            logger.info(f"成功从数据库加载 {loaded_count} 个文档元数据（懒加载模式，content按需加载）")
            return loaded_count
        except Exception as e:
            logger.error(f"从数据库加载文档失败: {e}")
            return 0

    # --- 新增：数据库同步 ---
    def _sync_to_database(self, document: DocumentInDB) -> None:
        """同步文档到数据库"""
        try:
            from app.core.sql import get_db
            from app.models.db_models import DocumentORM
            import json
            
            db = next(get_db())
            
            # 检查文档是否已存在
            existing = db.query(DocumentORM).filter(
                DocumentORM.doc_id == document.document_id
            ).first()
            
            # 准备JSON字段
            tags_json = json.dumps(document.tags, ensure_ascii=False) if document.tags else None
            metadata_json = json.dumps(document.metadata, ensure_ascii=False) if document.metadata else None
            
            if existing:
                # 更新现有记录
                existing.user_id = document.user_id
                existing.title = document.title
                existing.filename = Path(document.file_path).name if document.file_path else None
                existing.file_path = document.file_path
                existing.file_size = document.file_size
                existing.doc_type = document.file_type
                existing.content = document.content
                existing.status = document.status
                existing.progress = getattr(document, 'progress', 0)
                existing.error_message = getattr(document, 'error_message', None)
                existing.vector_id = document.vector_id
                existing.tags = tags_json
                existing.doc_metadata = metadata_json
                existing.updated_at = document.updated_at
            else:
                # 创建新记录
                doc_orm = DocumentORM(
                    doc_id=document.document_id,
                    user_id=document.user_id,
                    title=document.title,
                    filename=Path(document.file_path).name if document.file_path else None,
                    file_path=document.file_path,
                    file_size=document.file_size,
                    doc_type=document.file_type,
                    content=document.content,
                    status=document.status,
                    progress=getattr(document, 'progress', 0),
                    error_message=getattr(document, 'error_message', None),
                    vector_id=document.vector_id,
                    is_deleted=False,
                    deleted_at=None,
                    tags=tags_json,
                    doc_metadata=metadata_json,
                    created_at=document.created_at,
                    updated_at=document.updated_at
                )
                db.add(doc_orm)
            
            db.commit()
            logger.info(f"文档已同步到数据库: {document.document_id}")
            
            # 更新Redis缓存
            meta_for_redis = {
                'document_id': document.document_id,
                'user_id': document.user_id,
                'title': document.title,
                'file_path': document.file_path,
                'file_size': document.file_size,
                'file_type': document.file_type,
                'status': document.status,
                'vector_id': document.vector_id,
                'tags': document.tags,
                'created_at': document.created_at.isoformat() if hasattr(document.created_at, 'isoformat') else str(document.created_at),
                'updated_at': document.updated_at.isoformat() if hasattr(document.updated_at, 'isoformat') else str(document.updated_at),
                'has_content': document.content is not None and len(document.content) > 0
            }
            self.metadata_cache.set(document.document_id, meta_for_redis)
            
        except Exception as e:
            logger.error(f"同步文档到数据库失败: {e}")
            if 'db' in locals():
                db.rollback()
    
    def _delete_from_database(self, document_id: str, user_id: str, soft_delete: bool = True) -> None:
        """从数据库删除文档"""
        try:
            from app.core.sql import get_db
            from app.models.db_models import DocumentORM
            
            db = next(get_db())
            
            doc_orm = db.query(DocumentORM).filter(
                DocumentORM.doc_id == document_id,
                DocumentORM.user_id == user_id
            ).first()
            
            if doc_orm:
                if soft_delete:
                    # 软删除
                    doc_orm.is_deleted = True
                    doc_orm.deleted_at = datetime.utcnow()
                    doc_orm.status = 'deleted'
                    logger.info(f"文档已软删除: {document_id}")
                else:
                    # 物理删除
                    db.delete(doc_orm)
                    logger.info(f"文档已从数据库删除: {document_id}")
                
                db.commit()
                
                # 失效Redis缓存
                self.metadata_cache.delete(document_id)
                logger.debug(f"Redis缓存已失效: {document_id}")
                
        except Exception as e:
            logger.error(f"从数据库删除文档失败: {e}")
            if 'db' in locals():
                db.rollback()
    
    def _restore_in_database(self, document_id: str, user_id: str) -> None:
        """在数据库中恢复文档"""
        try:
            from app.core.sql import get_db
            from app.models.db_models import DocumentORM
            
            db = next(get_db())
            
            doc_orm = db.query(DocumentORM).filter(
                DocumentORM.doc_id == document_id,
                DocumentORM.user_id == user_id
            ).first()
            
            if doc_orm:
                doc_orm.is_deleted = False
                doc_orm.deleted_at = None
                doc_orm.status = 'completed'
                doc_orm.progress = 100
                db.commit()
                logger.info(f"文档已在数据库中恢复: {document_id}")
        except Exception as e:
            logger.error(f"在数据库中恢复文档失败: {e}")
            if 'db' in locals():
                db.rollback()

    # --- 新增：元数据持久化/加载 ---
    def _metadata_path(self, user_id: str, document_id: str) -> Path:
        user_dir = Path(settings.upload_dir) / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir / f"{document_id}.json"

    def _persist_metadata(self, document: DocumentInDB) -> None:
        try:
            meta_path = self._metadata_path(document.user_id, document.document_id)
            data = {
                "document_id": document.document_id,
                "user_id": document.user_id,
                "title": document.title,
                "content": document.content,
                "file_type": document.file_type,
                "tags": document.tags,
                "metadata": document.metadata,
                "file_path": document.file_path,
                "file_size": document.file_size,
                "status": document.status,
                "progress": getattr(document, 'progress', 0),
                "error_message": getattr(document, 'error_message', None),
                "vector_id": document.vector_id,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"文档元数据已保存: {meta_path}")
        except Exception as e:
            logger.warning(f"保存文档元数据失败: {e}")

    def _load_user_documents_from_disk(self, user_id: str) -> None:
        try:
            user_dir = Path(settings.upload_dir) / user_id
            if not user_dir.exists():
                return
            # 记录已加载的文件路径，避免重复为同一文件构造文档
            loaded_file_paths = set()
            # 先加载有元数据的文档
            for meta_file in user_dir.glob("*.json"):
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # 避免重复加载同一 document_id
                    doc_id = data.get("document_id")
                    if doc_id and self.store.get_document(doc_id):
                        # 记录其文件路径，防止后续回退再次为同一文件构造文档
                        fp = data.get("file_path")
                        if fp:
                            loaded_file_paths.add(fp)
                        continue
                    created_at = datetime.fromisoformat(data.get("created_at")) if data.get("created_at") else datetime.utcnow()
                    updated_at = datetime.fromisoformat(data.get("updated_at")) if data.get("updated_at") else created_at
                    doc_in_db = DocumentInDB(
                        document_id=data.get("document_id"),
                        user_id=data.get("user_id", user_id),
                        title=data.get("title") or "未命名文档",
                        content=data.get("content"),
                        file_type=data.get("file_type") or DocumentType.OTHER,
                        tags=data.get("tags") or [],
                        metadata=data.get("metadata") or {},
                        file_path=data.get("file_path"),
                        file_size=data.get("file_size"),
                        status=self._map_old_status(data.get("status") or DocumentStatus.PENDING),
                        progress=data.get("progress", 0),
                        error_message=data.get("error_message"),
                        vector_id=data.get("vector_id"),
                        created_at=created_at,
                        updated_at=updated_at,
                    )
                    self.store.create_document(doc_in_db)
                    if doc_in_db.file_path:
                        loaded_file_paths.add(doc_in_db.file_path)
                except Exception as e:
                    logger.warning(f"加载元数据失败 {meta_file}: {e}")
            # 再兜底：仅有文件无元数据（避免为已有元数据文件重复构造条目）
            for file in user_dir.iterdir():
                if not file.is_file():
                    continue
                if file.suffix.lower() not in settings.allowed_file_types:
                    continue
                # 如果该文件已在元数据或内存中出现，则跳过
                if str(file) in loaded_file_paths:
                    continue
                # 如果内存已有同路径文件的文档，也跳过（容错）
                already_in_store = any(
                    (doc.user_id == user_id and doc.file_path == str(file))
                    for doc in self.store.documents.values()
                )
                if already_in_store:
                    continue
                # 构造一个可用的条目（使用文件名作为标题、生成新的document_id）
                doc_id = str(uuid.uuid4())
                meta = self.processor.get_file_metadata(str(file))
                created_at = datetime.fromtimestamp(meta.get("created_time", datetime.utcnow().timestamp()))
                updated_at = datetime.fromtimestamp(meta.get("modified_time", created_at.timestamp()))
                try:
                    doc_in_db = DocumentInDB(
                        document_id=doc_id,
                        user_id=user_id,
                        title=file.name,
                        content=None,
                        file_type=self.processor.detect_file_type(file.name),
                        tags=[],
                        metadata={"restored_from_file": True},
                        file_path=str(file),
                        file_size=meta.get("file_size"),
                        status=DocumentStatus.PROCESSING,
                        vector_id=None,
                        created_at=created_at,
                        updated_at=updated_at,
                    )
                    self.store.create_document(doc_in_db)
                    # 立即持久化新生成的元数据，避免重复恢复
                    self._persist_metadata(doc_in_db)
                    loaded_file_paths.add(doc_in_db.file_path)
                except Exception as e:
                    logger.warning(f"构造文档条目失败 {file}: {e}")
        except Exception as e:
            logger.warning(f"从磁盘加载用户文档失败: {e}")

    async def create_document(
        self, 
        document_create: DocumentCreate, 
        user_id: str,
        file_content: Optional[bytes] = None,
        filename: Optional[str] = None
    ) -> Document:
        """创建文档"""
        try:
            document_id = str(uuid.uuid4())
            
            # 创建文档记录
            document_in_db = DocumentInDB(
                document_id=document_id,
                user_id=user_id,
                title=document_create.title,
                content=document_create.content,
                file_type=document_create.file_type,
                tags=document_create.tags or [],
                metadata=document_create.metadata or {},
                status=DocumentStatus.PENDING,
                progress=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # 如果有文件内容，保存文件并提取文本
            if file_content and filename:
                # 保存文件
                file_path = await self.processor.save_uploaded_file(
                    file_content, filename, user_id
                )
                document_in_db.file_path = file_path
                document_in_db.file_size = len(file_content)

                # 更新状态：PARSING
                self._update_status(document_id, DocumentStatus.PARSING, progress=10)

                # 使用结构化解析器解析文档
                from app.services.structured_parser import get_structured_parser_service
                from app.services.multimodal_processor import get_multimodal_processor

                structured_parser = get_structured_parser_service()
                content_list = await structured_parser.parse_document(
                    file_path, document_create.file_type, user_id
                )

                # 合并所有文本内容（用于存储到 document.content）
                text_parts = [
                    c.text for c in content_list
                    if c.content_type == "text" and c.text
                ]
                extracted_text = "\n\n".join(text_parts)

                # 如果没有提供内容，使用提取的文本
                if not document_in_db.content:
                    document_in_db.content = extracted_text

                # 将多模态内容信息存入 metadata
                multimodal_meta = {
                    "has_multimodal": any(
                        c.content_type != "text" for c in content_list
                    ),
                    "content_type_counts": {},
                }
                for c in content_list:
                    ct = c.content_type
                    multimodal_meta["content_type_counts"][ct] = (
                        multimodal_meta["content_type_counts"].get(ct, 0) + 1
                    )
                document_in_db.metadata = {
                    **(document_in_db.metadata or {}),
                    **multimodal_meta,
                }
            
            # 保存到存储
            created_document = self.store.create_document(document_in_db)
            # 新增：持久化元数据
            self._persist_metadata(created_document)
            # 新增：同步到数据库
            self._sync_to_database(created_document)
            
            # 异步处理向量化（在后台进行）
            await self._process_document_vectors(created_document)

            # 新文档入库后清除用户查询缓存
            try:
                get_query_cache().invalidate_user(user_id)
            except Exception:
                pass
            
            return self._convert_to_document(created_document)
            
        except Exception as e:
            logger.error(f"创建文档失败: {e}")
            # 更新文档状态为失败
            if 'document_in_db' in locals():
                self.store.update_document(document_id, {"status": DocumentStatus.FAILED})
            raise e

    async def _process_document_vectors(self, document: DocumentInDB):
        """处理文档向量化（带细粒度状态机 + 多模态支持）"""
        doc_id = document.document_id
        try:
            if not document.content and not document.file_path:
                logger.warning(f"文档 {doc_id} 没有内容且无文件，跳过向量化")
                self._update_status(doc_id, DocumentStatus.FAILED, error_message="文档内容为空")
                return

            # 阶段1：CHUNKING（分块）
            self._update_status(doc_id, DocumentStatus.CHUNKING, progress=30)

            # 检查是否有文件路径（多模态文档）
            all_chunks = []

            if document.file_path and os.path.exists(document.file_path):
                # 多模态文档：使用结构化解析 + 多模态处理器
                all_chunks = await self._process_multimodal_chunks(document)

            # 如果多模态处理未产生 chunk，回退到纯文本分块
            if not all_chunks and document.content:
                all_chunks = self.processor.split_text_into_chunks(
                    document.content, doc_id
                )

            if not all_chunks:
                logger.warning(f"文档 {doc_id} 分块失败")
                self._update_status(doc_id, DocumentStatus.FAILED, error_message="文档分块失败，内容可能为空")
                return

            # 阶段2：EMBEDDING（向量化）
            self._update_status(doc_id, DocumentStatus.EMBEDDING, progress=60)
            vector_ids = await self.vector_store.add_document_chunks(
                all_chunks, document.user_id, document.title
            )

            # 阶段2.5：知识图谱构建（异步，不阻塞主流程）
            if settings.neo4j_enabled:
                try:
                    await self._build_knowledge_graph(document, all_chunks)
                except Exception as kg_err:
                    logger.warning(f"知识图谱构建失败（不影响主流程）: {kg_err}")

            # 阶段3：COMPLETED（完成）
            self.store.update_document(doc_id, {
                "status": DocumentStatus.COMPLETED,
                "progress": 100,
                "vector_id": ",".join(vector_ids) if vector_ids else None,
                "error_message": None,
            })
            updated = self.store.get_document(doc_id)
            if updated:
                self._persist_metadata(updated)
                self._sync_to_database(updated)

            logger.info(f"文档 {doc_id} 处理完成，共 {len(all_chunks)} 个块")

        except Exception as e:
            error_msg = str(e)[:500]
            logger.error(f"文档向量化失败: {e}")
            self._update_status(doc_id, DocumentStatus.FAILED, error_message=error_msg)

    async def _process_multimodal_chunks(self, document: DocumentInDB) -> list:
        """
        处理多模态文档，生成包含所有内容类型的 chunk 列表。

        参照 RAG-Anything _process_multimodal_content_batch_type_aware：
        - 阶段1：asyncio.Semaphore + asyncio.gather 并发调用 VLM/LLM 描述生成
        - 阶段2：串行组装 DocumentChunk 对象（纯 CPU，不需要并发）
        """
        from app.services.structured_parser import get_structured_parser_service
        from app.services.multimodal_processor import get_multimodal_processor

        doc_id = document.document_id

        # 解析文档
        structured_parser = get_structured_parser_service()
        content_list = await structured_parser.parse_document(
            document.file_path,
            document.file_type,
            document.user_id,
        )

        if not content_list:
            return []

        multimodal_proc = get_multimodal_processor()

        # ─── 阶段1：分离文本/多模态，并发处理多模态 VLM/LLM 描述 ────────────
        text_items = []      # (index_in_content_list, content)
        multimodal_items = []  # (index_in_content_list, content)

        for i, content in enumerate(content_list):
            if content.content_type == "text" and content.text:
                text_items.append((i, content))
            else:
                multimodal_items.append((i, content))

        # 并发控制：最大并行 VLM/LLM 调用数
        max_parallel = getattr(settings, "multimodal_max_parallel", 2)
        semaphore = asyncio.Semaphore(max_parallel)

        async def _process_one_multimodal(idx: int, content):
            """单个多模态内容处理（在 semaphore 控制下并发执行）"""
            async with semaphore:
                try:
                    chunk_data = await multimodal_proc.process_content(content, doc_id)
                    return (idx, content, chunk_data)
                except Exception as e:
                    logger.warning(f"多模态内容处理失败 (idx={idx}): {e}")
                    return (idx, content, None)

        # 并发提交所有多模态任务
        multimodal_tasks = [
            asyncio.create_task(_process_one_multimodal(idx, content))
            for idx, content in multimodal_items
        ]
        multimodal_results_raw = await asyncio.gather(*multimodal_tasks, return_exceptions=True)

        # 将结果整理为 {index_in_content_list: chunk_data}
        multimodal_results: Dict[int, Optional[Dict]] = {}
        for raw in multimodal_results_raw:
            if isinstance(raw, Exception):
                logger.error(f"多模态任务异常: {raw}")
                continue
            idx, content, chunk_data = raw
            multimodal_results[idx] = chunk_data

        # ─── 阶段2：串行组装 DocumentChunk，保持原始顺序 ────────────────────
        all_chunks = []
        chunk_index = 0

        for i, content in enumerate(content_list):
            if content.content_type == "text" and content.text:
                # 文本内容：分块器分割
                text_chunks = self.processor.split_text_into_chunks(
                    content.text, doc_id
                )
                for tc in text_chunks:
                    tc.content_type = "text"
                    tc.page_number = content.page_idx
                    tc.section_path = content.section_path
                    tc.chunk_index = chunk_index
                    tc.chunk_id = f"{doc_id}_chunk_{chunk_index}"
                    chunk_index += 1
                all_chunks.extend(text_chunks)

            else:
                # 多模态：从并发结果中取出（已在阶段1处理完）
                chunk_data = multimodal_results.get(i)
                if chunk_data:
                    chunk = DocumentChunk(
                        chunk_id=f"{doc_id}_chunk_{chunk_index}",
                        document_id=doc_id,
                        content=chunk_data["content"],
                        chunk_index=chunk_index,
                        start_pos=0,
                        end_pos=len(chunk_data["content"]),
                        content_type=chunk_data.get("content_type", "text"),
                        image_path=chunk_data.get("image_path"),
                        captions=chunk_data.get("captions", []),
                        section_path=chunk_data.get("section_path"),
                        page_number=chunk_data.get("page_number"),
                        metadata=chunk_data.get("metadata", {}),
                    )
                    all_chunks.append(chunk)
                    chunk_index += 1

        logger.info(
            f"多模态并发处理完成: doc={doc_id}, "
            f"content_items={len(content_list)}, "
            f"multimodal={len(multimodal_items)}(并发={max_parallel}), "
            f"chunks={len(all_chunks)}"
        )
        return all_chunks

    async def _build_knowledge_graph(self, document: DocumentInDB, chunks: list):
        """
        从文档块中提取实体和关系，写入 Neo4j 知识图谱 (并发优化版)
        
        参照 RAG-Anything:
        - 使用 entity_extractor 内部的 Semaphore + asyncio.gather 并发实体提取
        - 批量写入 Neo4j (MERGE 避免重复),提升性能
        """
        from app.services.knowledge_graph import get_knowledge_graph_service
        from app.services.entity_extractor import get_entity_extractor
        
        kg_service = get_knowledge_graph_service()
        if not kg_service.available:
            logger.info("Neo4j 不可用,跳过知识图谱构建")
            return
        
        # 创建文档节点
        kg_service.add_document_node(
            doc_id=document.document_id,
            title=document.title,
            user_id=document.user_id,
        )
        
        # 准备块数据 (仅文本类型,限制最多10块控制成本)
        extractor = get_entity_extractor()
        if not extractor.available:
            logger.info("实体提取器不可用,跳过知识图谱构建")
            return
        
        logger.info(f"开始实体提取: {len(chunks)} chunks, 提取器可用={extractor.available}")
        
        chunk_data = [
            {"content": c.content[:100] + "..." if len(c.content) > 100 else c.content, "chunk_id": c.chunk_id}
            for c in chunks[:3]  # 只打印前3个chunk的内容预览
            if getattr(c, 'content_type', 'text') == 'text' and c.content
        ]
        logger.info(f"Chunk数据预览: {chunk_data}")
        
        chunk_data = [
            {"content": c.content, "chunk_id": c.chunk_id}
            for c in chunks
            if getattr(c, 'content_type', 'text') == 'text' and c.content
        ]
        
        if not chunk_data:
            logger.warning("没有有效的chunk数据,跳过实体提取")
            return
        
        # 并发实体提取（处理所有chunk，不再限制数量）
        logger.info(f"调用extractor.extract_from_chunks... 共 {len(chunk_data)} 个chunk")
        extraction_result = await extractor.extract_from_chunks(
            chunk_data, max_chunks=len(chunk_data)
        )
        logger.info(f"提取结果: entities={len(extraction_result.entities)}, relations={len(extraction_result.relations)}")
        
        # 批量写入图谱 (使用 MERGE 避免重复)
        kg_service.add_entities_batch(
            entities=[
                {
                    "name": e.name,
                    "type": e.entity_type,
                    "description": e.description,
                    "source_chunk_id": None  # 当前 Entity 模型中没有此字段
                }
                for e in extraction_result.entities
            ],
            doc_id=document.document_id,
            user_id=document.user_id
        )
        
        kg_service.add_relations_batch(
            relations=[
                {
                    "source": r.source,
                    "target": r.target,
                    "type": r.relation_type,
                    "description": r.description
                }
                for r in extraction_result.relations
            ],
            doc_id=document.document_id,
            user_id=document.user_id
        )
        
        logger.info(
            f"知识图谱构建完成: doc={document.document_id}, "
            f"entities={len(extraction_result.entities)}, "
            f"relations={len(extraction_result.relations)}"
        )

    def _update_status(self, document_id: str, status: DocumentStatus, progress: int = None, error_message: str = None):
        """更新文档状态（内部辅助方法，自动持久化）"""
        update_data = {"status": status}
        if progress is not None:
            update_data["progress"] = progress
        if error_message is not None:
            update_data["error_message"] = error_message
        self.store.update_document(document_id, update_data)
        updated = self.store.get_document(document_id)
        if updated:
            self._persist_metadata(updated)
            self._sync_to_database(updated)
    
    async def get_document(self, document_id: str, user_id: str) -> Optional[Document]:
        """获取文档（支持懒加载）"""
        # 先从缓存获取
        document = self.store.get_document(document_id)
        
        # 如果不在缓存中，尝试从数据库懒加载
        if not document or document.user_id != user_id:
            logger.debug(f"文档 {document_id} 不在缓存中，尝试从数据库加载")
            document = await self._load_document_from_db(document_id, user_id)
            if not document:
                # 兜底：从磁盘加载用户文档
                self._load_user_documents_from_disk(user_id)
                document = self.store.get_document(document_id)
                if not document or document.user_id != user_id:
                    return None
        
        # 如果文档没有内容，尝试加载
        try:
            if (not document.content or not str(document.content).strip()) and document.file_path and os.path.exists(document.file_path):
                file_type = document.file_type
                if file_type == DocumentType.OTHER:
                    file_type = self.processor.detect_file_type(Path(document.file_path).name)
                if file_type in {DocumentType.TEXT, DocumentType.MARKDOWN, DocumentType.PDF, DocumentType.DOCX}:
                    extracted_text = await self.processor.extract_text_from_file(document.file_path, file_type)
                    updated = self.store.update_document(document_id, {
                        "content": extracted_text,
                        "status": DocumentStatus.INDEXED
                    })
                    if updated:
                        self._persist_metadata(updated)
                        document = updated
        except Exception as e:
            logger.warning(f"详情加载内容失败: {e}")
        
        return self._convert_to_document(document)
    
    async def _load_document_from_db(self, document_id: str, user_id: str) -> Optional[DocumentInDB]:
        """从数据库懒加载单个文档到缓存（优先检查Redis）"""
        try:
            # 1. 先尝试从Redis缓存获取元数据
            cached_meta = self.metadata_cache.get(document_id)
            if cached_meta and cached_meta.get('user_id') == user_id:
                logger.debug(f"Redis缓存命中: {document_id}")
                # 可以从缓存快速构建轻量级对象，但完整内容仍需从DB读取
            
            from app.core.sql import get_db
            from app.models.db_models import DocumentORM
            from app.models.document import DocumentInDB, DocumentStatus
            import json
            
            db = next(get_db())
            
            # 查询单个文档
            doc_orm = db.query(DocumentORM).filter(
                DocumentORM.doc_id == document_id,
                DocumentORM.user_id == user_id,
                DocumentORM.is_deleted == False
            ).first()
            
            if not doc_orm:
                logger.debug(f"数据库中未找到文档: {document_id}")
                return None
            
            # 解析JSON字段
            tags = json.loads(doc_orm.tags) if doc_orm.tags else []
            metadata = json.loads(doc_orm.doc_metadata) if doc_orm.doc_metadata else {}
            
            # 创建DocumentInDB对象
            document = DocumentInDB(
                document_id=doc_orm.doc_id,
                user_id=doc_orm.user_id,
                title=doc_orm.title,
                file_path=doc_orm.file_path,
                file_size=doc_orm.file_size,
                file_type=doc_orm.doc_type,
                content=doc_orm.content,  # 完整内容
                status=doc_orm.status,
                progress=getattr(doc_orm, 'progress', 0),
                error_message=getattr(doc_orm, 'error_message', None),
                vector_id=doc_orm.vector_id,
                tags=tags,
                metadata=metadata,
                created_at=doc_orm.created_at,
                updated_at=doc_orm.updated_at
            )
            
            # 加载到内存缓存中
            self.store.load_full_document(document_id, document)
            
            # 更新Redis缓存（包含has_content=True）
            meta_for_redis = {
                'document_id': document_id,
                'user_id': user_id,
                'title': document.title,
                'file_path': document.file_path,
                'file_size': document.file_size,
                'file_type': document.file_type,
                'status': document.status,
                'vector_id': document.vector_id,
                'tags': tags,
                'created_at': document.created_at.isoformat() if hasattr(document.created_at, 'isoformat') else str(document.created_at),
                'updated_at': document.updated_at.isoformat() if hasattr(document.updated_at, 'isoformat') else str(document.updated_at),
                'has_content': True
            }
            self.metadata_cache.set(document_id, meta_for_redis)
            
            logger.debug(f"文档已从数据库懒加载到缓存: {document_id}")
            
            return document
        except Exception as e:
            logger.error(f"从数据库懒加载文档失败: {e}")
            return None
    
    async def _ensure_document_loaded(self, document_id: str, user_id: str) -> Optional[DocumentInDB]:
        """确保文档已加载（支持懒加载），返回DocumentInDB对象"""
        # 先从缓存获取
        document = self.store.get_document(document_id)
        
        # 如果不在缓存中或权限不匹配，尝试从数据库加载
        if not document or document.user_id != user_id:
            logger.debug(f"文档 {document_id} 不在缓存中，尝试从数据库加载")
            document = await self._load_document_from_db(document_id, user_id)
            if not document:
                # 兜底：从磁盘加载用户文档
                self._load_user_documents_from_disk(user_id)
                document = self.store.get_document(document_id)
                if not document or document.user_id != user_id:
                    return None
        
        return document
    
    async def update_document(
        self, 
        document_id: str, 
        user_id: str, 
        document_update: DocumentUpdate
    ) -> Optional[Document]:
        """更新文档（支持懒加载）"""
        document = await self._ensure_document_loaded(document_id, user_id)
        if not document:
            return None
        
        update_data = document_update.dict(exclude_unset=True)
        
        # 如果更新了内容，需要重新向量化
        content_updated = "content" in update_data
        
        updated_document = self.store.update_document(document_id, update_data)
        if not updated_document:
            return None
        # 持久化更新
        self._persist_metadata(updated_document)
        # 同步到数据库
        self._sync_to_database(updated_document)
        
        # 如果内容更新了，重新处理向量
        if content_updated:
            # 删除旧的向量
            await self.vector_store.delete_document_vectors(document_id, user_id)
            
            # 更新状态为解析中
            self.store.update_document(document_id, {"status": DocumentStatus.PARSING, "progress": 10})
            updated2 = self.store.get_document(document_id)
            if updated2:
                self._persist_metadata(updated2)
            
            # 重新向量化
            await self._process_document_vectors(updated_document)
        
        return self._convert_to_document(updated_document)
    
    async def delete_document(self, document_id: str, user_id: str) -> bool:
        """删除文档（支持懒加载）"""
        # 先从缓存获取
        document = self.store.get_document(document_id)
        
        # 如果不在缓存中，尝试从数据库加载元数据
        if not document or document.user_id != user_id:
            logger.debug(f"文档 {document_id} 不在缓存中，尝试从数据库加载")
            from app.core.sql import get_db
            from app.models.db_models import DocumentORM
            import json
            
            db = next(get_db())
            doc_orm = db.query(DocumentORM).filter(
                DocumentORM.doc_id == document_id,
                DocumentORM.user_id == user_id,
                DocumentORM.is_deleted == False
            ).first()
            
            if not doc_orm:
                return False
            
            # 构建轻量级文档对象用于删除
            tags = json.loads(doc_orm.tags) if doc_orm.tags else []
            metadata = json.loads(doc_orm.doc_metadata) if doc_orm.doc_metadata else {}
            from app.models.document import DocumentInDB
            document = DocumentInDB(
                document_id=doc_orm.doc_id,
                user_id=doc_orm.user_id,
                title=doc_orm.title,
                file_path=doc_orm.file_path,
                file_size=doc_orm.file_size,
                file_type=doc_orm.doc_type,
                content=None,
                status=doc_orm.status,
                progress=getattr(doc_orm, 'progress', 0),
                error_message=getattr(doc_orm, 'error_message', None),
                vector_id=doc_orm.vector_id,
                tags=tags,
                metadata=metadata,
                created_at=doc_orm.created_at,
                updated_at=doc_orm.updated_at
            )
        
        try:
            # 删除向量数据
            await self.vector_store.delete_document_vectors(document_id, user_id)

            # 删除知识图谱数据
            if settings.neo4j_enabled:
                try:
                    from app.services.knowledge_graph import get_knowledge_graph_service
                    kg_service = get_knowledge_graph_service()
                    kg_service.delete_document_graph(document_id, user_id)
                except Exception as kg_err:
                    logger.warning(f"删除知识图谱数据失败（不影响主流程）: {kg_err}")
            
            # 删除文件
            if document.file_path:
                await self.processor.delete_file(document.file_path)
            
            # 删除文档记录
            ok = self.store.delete_document(document_id)
            if ok:
                # 从数据库删除
                self._delete_from_database(document_id, user_id, soft_delete=False)
                # 删除元数据文件
                try:
                    meta_path = self._metadata_path(user_id, document_id)
                    if meta_path.exists():
                        os.remove(meta_path)
                except Exception as e:
                    logger.warning(f"删除元数据文件失败: {e}")
            return ok
            
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False

    async def soft_delete_document(self, document_id: str, user_id: str) -> bool:
        """软删除文档（支持懒加载）：
        - 立即从向量库移除
        - 清空 vector_id 字段（保持数据一致性）
        - 标记状态为 DELETED
        - 写入 metadata.deleted_at（ISO8601）
        - 保留文件与元数据，便于回收站中恢复
        """
        document = await self._ensure_document_loaded(document_id, user_id)
        if not document:
            return False
        try:
            # 移除向量数据（若不存在则忽略）
            await self.vector_store.delete_document_vectors(document_id, user_id)
            # 移除知识图谱数据（Document节点 + 孤立Entity节点）
            if settings.neo4j_enabled:
                try:
                    from app.services.knowledge_graph import get_knowledge_graph_service
                    kg_service = get_knowledge_graph_service()
                    kg_service.delete_document_graph(document_id, user_id)
                except Exception as kg_err:
                    logger.warning(f"删除知识图谱数据失败（不影响主流程）: {kg_err}")
            # 标记软删除，同时清空 vector_id 字段
            deleted_at = datetime.utcnow().isoformat()
            updated = self.store.update_document(document_id, {
                "status": DocumentStatus.DELETED,
                "vector_id": None,  # 清空向量ID，避免数据不一致
                "metadata": {**(document.metadata or {}), "deleted_at": deleted_at}
            })
            if updated:
                self._persist_metadata(updated)
                # 同步到数据库（软删除）
                self._delete_from_database(document_id, user_id, soft_delete=True)
                # 删除后清除用户查询缓存
                try:
                    get_query_cache().invalidate_user(user_id)
                except Exception:
                    pass
                return True
            return False
        except Exception as e:
            logger.error(f"软删除文档失败: {e}")
            return False

    async def restore_document(self, document_id: str, user_id: str) -> Optional[Document]:
        """从回收站恢复文档（仅限30天内，支持懒加载）"""
        document = await self._ensure_document_loaded(document_id, user_id)
        if not document:
            return None
        # 必须是软删除状态
        if document.status != DocumentStatus.DELETED:
            return None
        try:
            deleted_at_str = (document.metadata or {}).get("deleted_at")
            if not deleted_at_str:
                return None
            try:
                deleted_at = datetime.fromisoformat(deleted_at_str)
            except Exception:
                # 元数据异常时，拒绝恢复
                return None
            # 超过30天不可恢复
            if (datetime.utcnow() - deleted_at).days > 30:
                return None
            # 清理删除标记并重新向量化
            new_meta = dict(document.metadata or {})
            new_meta.pop("deleted_at", None)
            updated = self.store.update_document(document_id, {
                "status": DocumentStatus.PENDING,
                "progress": 0,
                "error_message": None,
                "metadata": new_meta
            })
            if not updated:
                return None
            self._persist_metadata(updated)
            # 同步到数据库
            self._sync_to_database(updated)
            # 如果仍有内容则重新入库向量
            await self._process_document_vectors(updated)
            refreshed = self.store.get_document(document_id)
            if refreshed:
                self._persist_metadata(refreshed)
                # 恢复在数据库中的状态
                self._restore_in_database(document_id, user_id)
                return self._convert_to_document(refreshed)
            return None
        except Exception as e:
            logger.error(f"恢复文档失败: {e}")
            return None

    async def purge_document(self, document_id: str, user_id: str) -> bool:
        """彻底删除文档：删除文件、元数据及内存记录（向量已在软删除时移除，支持懒加载）"""
        document = await self._ensure_document_loaded(document_id, user_id)
        if not document:
            return False
        try:
            # 双保险：再次尝试删除向量
            await self.vector_store.delete_document_vectors(document_id, user_id)
            # 双保险：再次尝试删除知识图谱数据
            if settings.neo4j_enabled:
                try:
                    from app.services.knowledge_graph import get_knowledge_graph_service
                    kg_service = get_knowledge_graph_service()
                    kg_service.delete_document_graph(document_id, user_id)
                except Exception as kg_err:
                    logger.warning(f"删除知识图谱数据失败（不影响主流程）: {kg_err}")
            # 删除文件
            if document.file_path:
                await self.processor.delete_file(document.file_path)
            # 删除文档记录
            ok = self.store.delete_document(document_id)
            if ok:
                # 删除元数据文件
                try:
                    meta_path = self._metadata_path(user_id, document_id)
                    if meta_path.exists():
                        os.remove(meta_path)
                except Exception as e:
                    logger.warning(f"删除元数据文件失败: {e}")
                # 从数据库物理删除
                self._delete_from_database(document_id, user_id, soft_delete=False)
                # 彻底删除后清除用户查询缓存
                try:
                    get_query_cache().invalidate_user(user_id)
                except Exception:
                    pass
            return ok
        except Exception as e:
            logger.error(f"彻底删除文档失败: {e}")
            return False

    async def list_deleted_documents(self, user_id: str, skip: int = 0, limit: int = 20) -> List[Document]:
        """列出当前用户的回收站文档（自动清理超过30天的条目）"""
        # 自动清理
        await self._auto_purge_deleted(user_id)
        # 收集已软删除的文档（使用include_deleted=True参数）
        docs = self.store.list_user_documents(user_id, 0, 10000, include_deleted=True)
        deleted_docs = [d for d in docs if (d.status == DocumentStatus.DELETED) and ((d.metadata or {}).get("deleted_at"))]
        # 分页
        paginated = deleted_docs[skip:skip + limit]
        return [self._convert_to_document(d) for d in paginated]

    async def _auto_purge_deleted(self, user_id: str) -> None:
        """清理超过30天未恢复的软删除文档"""
        try:
            docs = self.store.list_user_documents(user_id, 0, 10000, include_deleted=True)
            for d in docs:
                if d.status != DocumentStatus.DELETED:
                    continue
                deleted_at_str = (d.metadata or {}).get("deleted_at")
                if not deleted_at_str:
                    continue
                try:
                    deleted_at = datetime.fromisoformat(deleted_at_str)
                except Exception:
                    continue
                if (datetime.utcnow() - deleted_at).days > 30:
                    await self.purge_document(d.document_id, user_id)
        except Exception as e:
            logger.warning(f"自动清理回收站失败: {e}")

    async def list_user_documents(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 20
    ) -> List[Document]:
        """列出用户的文档（排除软删除）"""
        # 新增：列表前尝试从磁盘加载
        self._load_user_documents_from_disk(user_id)
        documents = self.store.list_user_documents(user_id, skip, limit)
        # 排除软删除
        documents = [doc for doc in documents if doc.status != DocumentStatus.DELETED and not (doc.metadata or {}).get("deleted_at")]
        # 对相同文件路径去重（优先保留先加载的条目）
        unique_docs_in_db = []
        seen_keys = set()
        for doc in documents:
            key = doc.file_path or f"__no_fp__:{doc.document_id}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_docs_in_db.append(doc)
        return [self._convert_to_document(doc) for doc in unique_docs_in_db]
    
    async def search_documents(self, search_query: SearchQuery, user_id: str) -> SearchResponse:
        """搜索文档（支持向量检索 + 知识图谱融合 + 查询缓存）"""
        start_time = datetime.utcnow()

        # ─── 查询缓存（仅缓存纯向量模式，知识图谱模式每次新鲜检索）───
        query_mode = search_query.query_mode or settings.kg_query_mode
        effective_limit = min(search_query.limit, settings.qdrant_default_limit)
        cache = get_query_cache()
        cache_key = cache.make_key(
            query=search_query.query,
            user_id=user_id,
            query_mode=query_mode,
            limit=effective_limit,
            score_threshold=search_query.score_threshold,
        )
        cached = cache.get(cache_key, user_id)
        if cached is not None:
            # 缓存命中：从 dict 重建 SearchResult 对象
            from app.models.document import SearchResult as SR
            try:
                results = [SR(**r) for r in cached["search_results"]]
                took = (datetime.utcnow() - start_time).total_seconds()
                return SearchResponse(
                    query=search_query.query,
                    results=results,
                    total=len(results),
                    took=took,
                    fused_context=cached.get("fused_context"),
                )
            except Exception as ce:
                logger.debug(f"查询缓存反序列化失败，重新检索: {ce}")
        
        try:
            # 执行向量搜索
            search_results = await self.vector_store.search_similar_documents(
                query=search_query.query,
                user_id=user_id if search_query.user_id is None else search_query.user_id,
                limit=effective_limit,
                score_threshold=search_query.score_threshold
            )
            # 排除软删除的文档（status=DELETED 或 metadata.deleted_at 存在）
            filtered_non_deleted = []
            for result in search_results:
                # 使用元数据快速检查，无需加载完整文档
                meta = self.store.get_document_metadata(result.document_id)
                if not meta:
                    # 从磁盘加载后再查一次，确保状态一致
                    self._load_user_documents_from_disk(user_id)
                    meta = self.store.get_document_metadata(result.document_id)
                # 仅当文档存在且未标记删除时保留
                if meta and not (
                    meta.get('status') == DocumentStatus.DELETED or
                    (meta.get('metadata') or {}).get("deleted_at")
                ):
                    filtered_non_deleted.append(result)
            search_results = filtered_non_deleted

            # 如果有标签过滤，进一步过滤结果
            if search_query.tags:
                filtered_results = []
                for result in search_results:
                    # 使用元数据检查标签
                    meta = self.store.get_document_metadata(result.document_id)
                    if meta and any(tag in (meta.get('tags') or []) for tag in search_query.tags):
                        filtered_results.append(result)
                search_results = filtered_results

            # ─── 知识图谱融合（当模式非 vector 且图谱可用时） ───
            fused_context = None
            if query_mode != "vector" and settings.neo4j_enabled:
                try:
                    router = get_query_mode_router()
                    fused_context = await router.route(
                        query=search_query.query,
                        user_id=user_id,
                        vector_results=search_results,
                        query_mode=query_mode,
                    )
                    if fused_context:
                        logger.info(
                            f"知识图谱融合完成: 模式={query_mode}, "
                            f"上下文长度={len(fused_context)}"
                        )
                except Exception as e:
                    logger.warning(f"知识图谱融合失败，降级到纯向量模式: {e}")
            
            end_time = datetime.utcnow()
            took = (end_time - start_time).total_seconds()
            
            response = SearchResponse(
                query=search_query.query,
                results=search_results,
                total=len(search_results),
                took=took
            )
            # 将融合上下文附加到响应的 metadata 中
            if fused_context:
                response.fused_context = fused_context

            # ─── 写入查询缓存（不阻塞，失败不影响主流程）───
            try:
                cache.set(
                    key=cache_key,
                    user_id=user_id,
                    search_results=search_results,
                    query=search_query.query,
                    query_mode=query_mode,
                )
            except Exception as ce:
                logger.debug(f"查询缓存写入失败（不影响主流程）: {ce}")

            return response
            
        except Exception as e:
            logger.error(f"搜索文档失败: {e}")
            raise e
    
    def _convert_to_document(self, document_in_db: DocumentInDB) -> Document:
        """转换为客户端文档模型（兼容旧状态映射）"""
        # 兼容旧数据：PROCESSING → PENDING, INDEXED → COMPLETED
        status = document_in_db.status
        if status == DocumentStatus.PROCESSING:
            status = DocumentStatus.PENDING
        elif status == DocumentStatus.INDEXED:
            status = DocumentStatus.COMPLETED

        return Document(
            document_id=document_in_db.document_id,
            user_id=document_in_db.user_id,
            title=document_in_db.title,
            content=document_in_db.content,
            file_type=document_in_db.file_type,
            tags=document_in_db.tags,
            metadata=document_in_db.metadata,
            file_size=document_in_db.file_size,
            status=status,
            progress=getattr(document_in_db, 'progress', 0),
            error_message=getattr(document_in_db, 'error_message', None),
            created_at=document_in_db.created_at,
            updated_at=document_in_db.updated_at
        )

    async def batch_upload_documents(
        self,
        files: List[tuple],  # List of (file_content: bytes, filename: str, title: str)
        user_id: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        max_concurrent: Optional[int] = None,
    ) -> Dict[str, Any]:
        """批量导入文档（参照 RAG-Anything batch.py Semaphore 并发控制）

        Args:
            files: [(file_content, filename, title), ...]
            user_id: 所属用户 ID
            tags: 公共标签
            metadata: 公共元数据
            max_concurrent: 最大并发数（默认取 settings.batch_max_concurrent）

        Returns:
            {
                "total": N,
                "successful": M,
                "failed": K,
                "results": [{"title": ..., "document_id": ..., "status": "success"|"failed", "error": ...}]
            }
        """
        import asyncio
        from app.models.document import DocumentCreate

        if max_concurrent is None:
            max_concurrent = getattr(settings, 'batch_max_concurrent', 3)

        semaphore = asyncio.Semaphore(max_concurrent)
        results = []

        async def _process_one(file_content: bytes, filename: str, title: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    processor = get_document_processor()
                    # 验证文件类型
                    if not processor.validate_file_type(filename):
                        return {
                            "title": title or filename,
                            "filename": filename,
                            "status": "failed",
                            "error": f"不支持的文件类型: {filename}",
                        }
                    # 验证文件大小
                    if not processor.validate_file_size(len(file_content)):
                        return {
                            "title": title or filename,
                            "filename": filename,
                            "status": "failed",
                            "error": f"文件大小超过限制: {filename}",
                        }
                    file_type = processor.detect_file_type(filename)
                    doc_create = DocumentCreate(
                        title=title or filename,
                        file_type=file_type,
                        tags=tags or [],
                        metadata={**(metadata or {}), "batch_import": True},
                    )
                    document = await self.create_document(
                        document_create=doc_create,
                        user_id=user_id,
                        file_content=file_content,
                        filename=filename,
                    )
                    return {
                        "title": document.title,
                        "filename": filename,
                        "document_id": document.document_id,
                        "status": "success",
                        "error": None,
                    }
                except Exception as e:
                    logger.error(f"批量导入单文件失败 {filename}: {e}")
                    return {
                        "title": title or filename,
                        "filename": filename,
                        "status": "failed",
                        "error": str(e)[:200],
                    }

        # 并发处理所有文件
        tasks = [
            asyncio.create_task(_process_one(fc, fn, t))
            for fc, fn, t in files
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 整理结果
        clean_results = []
        for r in results:
            if isinstance(r, Exception):
                clean_results.append({"status": "failed", "error": str(r)})
            else:
                clean_results.append(r)

        successful = sum(1 for r in clean_results if r.get("status") == "success")
        failed = len(clean_results) - successful

        logger.info(
            f"批量导入完成: 总计={len(clean_results)}, 成功={successful}, 失败={failed}"
        )
        return {
            "total": len(clean_results),
            "successful": successful,
            "failed": failed,
            "results": clean_results,
        }

    # ─── 3.12 文档智能摘要 ─────────────────────────────────────────

    async def generate_document_summary(
        self, document_id: str, user_id: str, force: bool = False
    ) -> Optional[Dict]:
        """生成文档智能摘要并写入 DB。

        Args:
            document_id: 文档 ID
            user_id: 所属用户 ID（用于权限校验）
            force: 是否强制重新生成（忽略已有缓存）

        Returns:
            摘要字典，包含 summary / key_points / keywords / entities
        """
        doc = self.store.get_document(document_id)
        if not doc:
            self._load_user_documents_from_disk(user_id)
            doc = self.store.get_document(document_id)
        if not doc or doc.user_id != user_id:
            logger.warning(f"[summary] doc={document_id} 不存在或无权限")
            return None

        # 如果已有摘要且不强制重生成，直接返回缓存
        if not force:
            existing = (doc.metadata or {}).get("ai_summary")
            if existing:
                logger.info(f"[summary] 命中缓存 doc={document_id}")
                return existing

        from app.services.document_summary import get_summary_service
        svc = get_summary_service()
        content = doc.content or ""
        summary = await svc.summarize_and_save(document_id, doc.title, content)

        # 同步到内存文档的 metadata
        meta = dict(doc.metadata or {})
        meta["ai_summary"] = summary
        self.store.update_document(document_id, {"metadata": meta})
        return summary

    def get_document_summary_cached(
        self, document_id: str, user_id: str
    ) -> Optional[Dict]:
        """从内存缓存快速返回已有摘要（不调用 LLM）。"""
        doc = self.store.get_document(document_id)
        if not doc:
            self._load_user_documents_from_disk(user_id)
            doc = self.store.get_document(document_id)
        if not doc or doc.user_id != user_id:
            return None
        return (doc.metadata or {}).get("ai_summary")

    # ─── 3.13 相关文档推荐 ──────────────────────────────────────

    async def get_related_documents(
        self,
        document_id: str,
        user_id: str,
        limit: int = 5,
    ) -> List[Dict]:
        """当前文档的相关文档推荐。

        推荐依据（按优先级）：
        1. 向量相似度（语义相关）
        2. 相同标签（人工关联）
        3. 共享实体（知识图谱关联，若可用）

        Returns:
            List of {document_id, title, similarity, reason, file_type, created_at}
        """
        doc = self.store.get_document(document_id)
        if not doc:
            self._load_user_documents_from_disk(user_id)
            doc = self.store.get_document(document_id)
        if not doc or doc.user_id != user_id:
            return []

        related: Dict[str, Dict] = {}  # document_id -> info

        # ① 向量相似度：用文档标题 + 内容前500字做查询
        try:
            query_text = doc.title + " " + (doc.content or "")[:500]
            search_results = await self.vector_store.search_similar_documents(
                query=query_text,
                user_id=user_id,
                limit=limit * 3,
                score_threshold=0.4,
            )
            for r in search_results:
                rid = r.document_id
                if rid == document_id:
                    continue
                if rid not in related:
                    rdoc = self.store.get_document(rid)
                    related[rid] = {
                        "document_id": rid,
                        "title": getattr(rdoc, "title", r.title) if rdoc else r.title,
                        "similarity": round(r.score, 4),
                        "reason": "语义相似",
                        "file_type": getattr(rdoc, "file_type", "") if rdoc else "",
                        "created_at": getattr(rdoc, "created_at", None) if rdoc else None,
                    }
        except Exception as e:
            logger.warning(f"[related] 向量相似度推荐失败: {e}")

        # ② 相同标签
        if doc.tags:
            doc_tags = set(doc.tags)
            all_docs = list(self.store.documents.values())
            for other in all_docs:
                if other.document_id == document_id:
                    continue
                if other.user_id != user_id:
                    continue
                if other.status in (DocumentStatus.DELETED,):
                    continue
                other_tags = set(getattr(other, "tags", []) or [])
                shared = doc_tags & other_tags
                if shared:
                    oid = other.document_id
                    if oid not in related:
                        related[oid] = {
                            "document_id": oid,
                            "title": other.title,
                            "similarity": 0.6,
                            "reason": f"共享标签: {', '.join(list(shared)[:3])}",
                            "file_type": str(other.file_type),
                            "created_at": other.created_at,
                        }
                    else:
                        related[oid]["reason"] += f" + 标签: {', '.join(list(shared)[:2])}"

        # ③ 知识图谱共享实体
        if settings.neo4j_enabled:
            try:
                from app.services.knowledge_graph import get_knowledge_graph_service
                kg = get_knowledge_graph_service()
                if kg.available:
                    related_ids = kg.get_related_documents(
                        document_id, user_id, limit=limit * 2
                    )
                    for rid, shared_entities in related_ids:
                        if rid == document_id:
                            continue
                        rdoc = self.store.get_document(rid)
                        if rdoc and rdoc.user_id == user_id:
                            if rid not in related:
                                related[rid] = {
                                    "document_id": rid,
                                    "title": rdoc.title,
                                    "similarity": 0.7,
                                    "reason": f"共享实体: {', '.join(shared_entities[:2])}",
                                    "file_type": str(rdoc.file_type),
                                    "created_at": rdoc.created_at,
                                }
                            else:
                                related[rid]["reason"] += f" + 实体: {', '.join(shared_entities[:1])}"
            except Exception as e:
                logger.debug(f"[related] 知识图谱推荐失败: {e}")

        # 按相似度排序，取前 N 条
        result_list = sorted(
            related.values(), key=lambda x: x["similarity"], reverse=True
        )[:limit]

        # 日期序列化
        for item in result_list:
            if item.get("created_at") and hasattr(item["created_at"], "isoformat"):
                item["created_at"] = item["created_at"].isoformat()

        return result_list


# 全局文档服务实例
_document_service = None

def get_document_service() -> DocumentService:
    """获取文档服务实例（单例模式）"""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service