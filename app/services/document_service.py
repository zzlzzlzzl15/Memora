import uuid
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
    DocumentStatus, DocumentType, SearchQuery, SearchResult, SearchResponse
)
from app.services.document_processor import get_document_processor
from app.services.vector_store import get_vector_store_service
from app.services.embedding import get_embedding_service
from config.settings import settings

# 优化的内存存储（添加索引和线程安全保护）
class InMemoryDocumentStore:
    """内存文档存储（优化版：支持索引和并发安全）"""
    
    def __init__(self):
        # 主存储
        self.documents: Dict[str, DocumentInDB] = {}
        
        # 多维度索引（提升查询性能）
        self.user_documents: Dict[str, List[str]] = defaultdict(list)  # user_id -> [document_ids]
        self.status_index: Dict[str, List[str]] = defaultdict(list)    # status -> [document_ids]
        self.type_index: Dict[str, List[str]] = defaultdict(list)      # file_type -> [document_ids]
        
        # 读写锁（保证线程安全）
        self.lock = threading.RLock()
        
        logger.info("InMemoryDocumentStore初始化完成（支持并发安全和多维索引）")
    
    def create_document(self, document: DocumentInDB) -> DocumentInDB:
        """创建文档（线程安全）"""
        with self.lock:
            # 存储文档
            self.documents[document.document_id] = document
            
            # 更新多维索引
            self.user_documents[document.user_id].append(document.document_id)
            self.status_index[document.status].append(document.document_id)
            self.type_index[document.file_type].append(document.document_id)
            
            logger.debug(f"文档已创建: {document.document_id}, 用户: {document.user_id}")
            return document
    
    def get_document(self, document_id: str) -> Optional[DocumentInDB]:
        """获取文档（线程安全）"""
        with self.lock:
            return self.documents.get(document_id)
    
    def update_document(self, document_id: str, update_data: Dict[str, Any]) -> Optional[DocumentInDB]:
        """更新文档（线程安全，支持索引更新）"""
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
            
            # 如果状态或类型变更，更新索引
            if 'status' in update_data and update_data['status'] != old_status:
                self._update_status_index(document_id, old_status, document.status)
            
            if 'file_type' in update_data and update_data['file_type'] != old_type:
                self._update_type_index(document_id, old_type, document.file_type)
            
            return document
    
    def delete_document(self, document_id: str) -> bool:
        """删除文档（线程安全，清理所有索引）"""
        with self.lock:
            if document_id not in self.documents:
                return False
            
            document = self.documents[document_id]
            user_id = document.user_id
            status = document.status
            file_type = document.file_type
            
            # 从主存储删除
            del self.documents[document_id]
            
            # 从所有索引中删除
            self._remove_from_index(self.user_documents[user_id], document_id)
            self._remove_from_index(self.status_index[status], document_id)
            self._remove_from_index(self.type_index[file_type], document_id)
            
            logger.debug(f"文档已删除: {document_id}")
            return True
    
    def list_user_documents(self, user_id: str, skip: int = 0, limit: int = 100, include_deleted: bool = False) -> List[DocumentInDB]:
        """列出用户的文档（线程安全，使用索引优化）"""
        with self.lock:
            # 使用索引快速定位用户文档
            document_ids = self.user_documents.get(user_id, [])
            
            # 根据参数决定是否包含已删除的文档
            if include_deleted:
                docs = [
                    self.documents[doc_id] 
                    for doc_id in document_ids 
                    if doc_id in self.documents
                ]
            else:
                # 过滤掉已删除的文档（非DELETED状态）
                docs = [
                    self.documents[doc_id] 
                    for doc_id in document_ids 
                    if doc_id in self.documents and self.documents[doc_id].status != DocumentStatus.DELETED
                ]
            
            # 按创建时间倒序排序
            docs.sort(key=lambda x: x.created_at, reverse=True)
            
            # 分页返回
            return docs[skip:skip + limit]
    
    def count_user_documents(self, user_id: str, include_deleted: bool = False) -> int:
        """统计用户文档数量（线程安全）"""
        with self.lock:
            document_ids = self.user_documents.get(user_id, [])
            
            if include_deleted:
                return len([doc_id for doc_id in document_ids if doc_id in self.documents])
            else:
                return len([
                    doc_id for doc_id in document_ids 
                    if doc_id in self.documents and self.documents[doc_id].status != DocumentStatus.DELETED
                ])
    
    # --- 私有辅助方法 ---
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
                "total_documents": len(self.documents),
                "total_users": len(self.user_documents),
                "by_status": {status: len(docs) for status, docs in self.status_index.items()},
                "by_type": {file_type: len(docs) for file_type, docs in self.type_index.items()}
            }

class DocumentService:
    """文档服务"""
    
    def __init__(self):
        self.store = InMemoryDocumentStore()
        self.processor = get_document_processor()
        self.vector_store = get_vector_store_service()
        self.embedding_service = get_embedding_service()

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
                doc_orm.status = 'indexed'
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
                        status=data.get("status") or DocumentStatus.INDEXED,
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
                status=DocumentStatus.PROCESSING,
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
                
                # 提取文本内容
                extracted_text = await self.processor.extract_text_from_file(
                    file_path, document_create.file_type
                )
                
                # 如果没有提供内容，使用提取的文本
                if not document_in_db.content:
                    document_in_db.content = extracted_text
            
            # 保存到存储
            created_document = self.store.create_document(document_in_db)
            # 新增：持久化元数据
            self._persist_metadata(created_document)
            # 新增：同步到数据库
            self._sync_to_database(created_document)
            
            # 异步处理向量化（在后台进行）
            await self._process_document_vectors(created_document)
            
            return self._convert_to_document(created_document)
            
        except Exception as e:
            logger.error(f"创建文档失败: {e}")
            # 更新文档状态为失败
            if 'document_in_db' in locals():
                self.store.update_document(document_id, {"status": DocumentStatus.FAILED})
            raise e

    async def _process_document_vectors(self, document: DocumentInDB):
        """处理文档向量化"""
        try:
            if not document.content:
                logger.warning(f"文档 {document.document_id} 没有内容，跳过向量化")
                return
            
            # 分割文档为块
            chunks = self.processor.split_text_into_chunks(
                document.content, document.document_id
            )
            
            if chunks:
                # 添加到向量数据库，传入文档标题
                vector_ids = await self.vector_store.add_document_chunks(
                    chunks, document.user_id, document.title
                )
                
                # 更新文档状态
                self.store.update_document(document.document_id, {
                    "status": DocumentStatus.INDEXED,
                    "vector_id": ",".join(vector_ids) if vector_ids else None
                })
                # 更新持久化
                updated = self.store.get_document(document.document_id)
                if updated:
                    self._persist_metadata(updated)
                    # 同步到数据库
                    self._sync_to_database(updated)
                
                logger.info(f"文档 {document.document_id} 向量化完成")
            else:
                logger.warning(f"文档 {document.document_id} 分块失败")
                self.store.update_document(document.document_id, {
                    "status": DocumentStatus.FAILED
                })
                updated = self.store.get_document(document.document_id)
                if updated:
                    self._persist_metadata(updated)
                    # 同步到数据库
                    self._sync_to_database(updated)
                
        except Exception as e:
            logger.error(f"文档向量化失败: {e}")
            self.store.update_document(document.document_id, {
                "status": DocumentStatus.FAILED
            })
            updated = self.store.get_document(document.document_id)
            if updated:
                self._persist_metadata(updated)
                # 同步到数据库
                self._sync_to_database(updated)
    
    async def get_document(self, document_id: str, user_id: str) -> Optional[Document]:
        """获取文档"""
        document = self.store.get_document(document_id)
        if not document or document.user_id != user_id:
            self._load_user_documents_from_disk(user_id)
            document = self.store.get_document(document_id)
            if not document or document.user_id != user_id:
                return None
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
    
    async def update_document(
        self, 
        document_id: str, 
        user_id: str, 
        document_update: DocumentUpdate
    ) -> Optional[Document]:
        """更新文档"""
        document = self.store.get_document(document_id)
        if not document or document.user_id != user_id:
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
            
            # 更新状态为处理中
            self.store.update_document(document_id, {"status": DocumentStatus.PROCESSING})
            updated2 = self.store.get_document(document_id)
            if updated2:
                self._persist_metadata(updated2)
            
            # 重新向量化
            await self._process_document_vectors(updated_document)
        
        return self._convert_to_document(updated_document)
    
    async def delete_document(self, document_id: str, user_id: str) -> bool:
        """删除文档"""
        document = self.store.get_document(document_id)
        if not document or document.user_id != user_id:
            return False
        
        try:
            # 删除向量数据
            await self.vector_store.delete_document_vectors(document_id, user_id)
            
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
            return ok
            
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False

    async def soft_delete_document(self, document_id: str, user_id: str) -> bool:
        """软删除文档：
        - 立即从向量库移除
        - 清空 vector_id 字段（保持数据一致性）
        - 标记状态为 DELETED
        - 写入 metadata.deleted_at（ISO8601）
        - 保留文件与元数据，便于回收站中恢复
        """
        document = self.store.get_document(document_id)
        if not document or document.user_id != user_id:
            return False
        try:
            # 移除向量数据（若不存在则忽略）
            await self.vector_store.delete_document_vectors(document_id, user_id)
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
                return True
            return False
        except Exception as e:
            logger.error(f"软删除文档失败: {e}")
            return False

    async def restore_document(self, document_id: str, user_id: str) -> Optional[Document]:
        """从回收站恢复文档（仅限30天内）"""
        document = self.store.get_document(document_id)
        if not document or document.user_id != user_id:
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
                "status": DocumentStatus.PROCESSING,
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
        """彻底删除文档：删除文件、元数据及内存记录（向量已在软删除时移除）"""
        document = self.store.get_document(document_id)
        if not document or document.user_id != user_id:
            return False
        try:
            # 双保险：再次尝试删除向量
            await self.vector_store.delete_document_vectors(document_id, user_id)
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
        """搜索文档"""
        start_time = datetime.utcnow()
        
        try:
            # 强制限制返回数量为配置的默认值
            effective_limit = min(search_query.limit, settings.qdrant_default_limit)
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
                doc = self.store.get_document(result.document_id)
                if not doc:
                    # 从磁盘加载后再查一次，确保状态一致
                    self._load_user_documents_from_disk(user_id)
                    doc = self.store.get_document(result.document_id)
                # 仅当文档存在且未标记删除时保留
                if doc and not (
                    getattr(doc, "status", None) == DocumentStatus.DELETED or
                    (doc.metadata or {}).get("deleted_at")
                ):
                    filtered_non_deleted.append(result)
            search_results = filtered_non_deleted

            # 如果有标签过滤，进一步过滤结果
            if search_query.tags:
                filtered_results = []
                for result in search_results:
                    document = self.store.get_document(result.document_id)
                    if document and any(tag in document.tags for tag in search_query.tags):
                        filtered_results.append(result)
                search_results = filtered_results
            
            end_time = datetime.utcnow()
            took = (end_time - start_time).total_seconds()
            
            return SearchResponse(
                query=search_query.query,
                results=search_results,
                total=len(search_results),
                took=took
            )
            
        except Exception as e:
            logger.error(f"搜索文档失败: {e}")
            raise e
    
    def _convert_to_document(self, document_in_db: DocumentInDB) -> Document:
        """转换为客户端文档模型"""
        return Document(
            document_id=document_in_db.document_id,
            user_id=document_in_db.user_id,
            title=document_in_db.title,
            content=document_in_db.content,
            file_type=document_in_db.file_type,
            tags=document_in_db.tags,
            metadata=document_in_db.metadata,
            file_size=document_in_db.file_size,
            status=document_in_db.status,
            created_at=document_in_db.created_at,
            updated_at=document_in_db.updated_at
        )

# 全局文档服务实例
_document_service = None

def get_document_service() -> DocumentService:
    """获取文档服务实例（单例模式）"""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service