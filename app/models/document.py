from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from config.settings import settings

class DocumentType(str, Enum):
    """文档类型枚举"""
    TEXT = "text"
    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "markdown"
    OTHER = "other"

class DocumentStatus(str, Enum):
    """文档状态枚举"""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    # 新增：软删除状态，用于回收站
    DELETED = "deleted"

class DocumentBase(BaseModel):
    """文档基础模型"""
    title: str = Field(..., min_length=1, max_length=200, description="文档标题")
    content: Optional[str] = Field(None, description="文档内容")
    file_type: DocumentType = Field(..., description="文档类型")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")

class DocumentCreate(DocumentBase):
    """创建文档模型"""
    pass

class DocumentUpdate(BaseModel):
    """更新文档模型"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class DocumentInDB(DocumentBase):
    """数据库中的文档模型"""
    document_id: str = Field(..., description="文档ID")
    user_id: str = Field(..., description="所属用户ID")
    file_path: Optional[str] = Field(None, description="文件路径")
    file_size: Optional[int] = Field(None, description="文件大小（字节）")
    status: DocumentStatus = Field(DocumentStatus.UPLOADING, description="文档状态")
    vector_id: Optional[str] = Field(None, description="向量ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

class Document(DocumentBase):
    """返回给客户端的文档模型"""
    document_id: str = Field(..., description="文档ID")
    user_id: str = Field(..., description="所属用户ID")
    file_size: Optional[int] = Field(None, description="文件大小（字节）")
    status: DocumentStatus = Field(..., description="文档状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

class DocumentChunk(BaseModel):
    """文档分块模型"""
    chunk_id: str = Field(..., description="分块ID")
    document_id: str = Field(..., description="文档ID")
    content: str = Field(..., description="分块内容")
    chunk_index: int = Field(..., description="分块索引")
    start_pos: int = Field(..., description="开始位置")
    end_pos: int = Field(..., description="结束位置")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="分块元数据")

class SearchQuery(BaseModel):
    """搜索查询模型"""
    query: str = Field(..., min_length=1, max_length=40000, description="搜索查询（支持知识整理模式的长文本）")
    limit: int = Field(settings.qdrant_default_limit, ge=1, le=100, description="返回结果数量")
    score_threshold: float = Field(0.7, ge=0.0, le=1.0, description="相似度阈值")
    user_id: Optional[str] = Field(None, description="用户ID过滤")
    tags: Optional[List[str]] = Field(None, description="标签过滤")

class SearchResult(BaseModel):
    """搜索结果模型"""
    document_id: str = Field(..., description="文档ID")
    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="匹配的内容片段")
    score: float = Field(..., description="相似度分数")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(..., description="创建时间")

class SearchAnswerResponse(BaseModel):
    """知识整理输出响应模型"""
    query: str = Field(..., description="搜索查询")
    answer: str = Field(..., description="LLM整理后的答案")
    results: List[SearchResult] = Field(..., description="原始搜索结果列表")
    total: int = Field(..., description="总结果数")
    took: float = Field(..., description="总耗时（秒）")

class SearchResponse(BaseModel):
    """搜索响应模型"""
    query: str = Field(..., description="搜索查询")
    results: List[SearchResult] = Field(..., description="搜索结果列表")
    total: int = Field(..., description="总结果数")
    took: float = Field(..., description="搜索耗时（秒）")

class DocumentListResponse(BaseModel):
    """文档列表响应模型（包含总数）"""
    documents: List[Document] = Field(..., description="文档列表")
    total: int = Field(..., description="文档总数（未删除的）")
    skip: int = Field(..., description="跳过的数量")
    limit: int = Field(..., description="返回的数量")