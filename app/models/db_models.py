from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Index, Integer
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import declarative_mixin
from datetime import datetime

from app.core.sql import Base


@declarative_mixin
class TimestampMixin:
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UserORM(Base, TimestampMixin):
    __tablename__ = "users"

    # 使用字符串UUID作为主键,兼容现有user_id
    user_id = Column(String(36), primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    phone_number = Column(String(20), unique=True, nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    hashed_password = Column(String(255), nullable=False)
    avatar_url = Column(String(500), nullable=True)  # 头像URL


class RefreshTokenORM(Base, TimestampMixin):
    """Refresh Token 表：用于管理长期登录会话"""
    __tablename__ = "refresh_tokens"

    token_id = Column(String(36), primary_key=True, index=True)  # UUID
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)  # refresh_token 的 SHA256 哈希值
    device_info = Column(String(500), nullable=True)  # 设备信息（User-Agent、设备名称等）
    ip_address = Column(String(45), nullable=True)  # IP地址（支持IPv6）
    expires_at = Column(DateTime, nullable=False, index=True)  # 过期时间
    is_revoked = Column(Boolean, nullable=False, default=False, index=True)  # 是否已撤销
    revoked_at = Column(DateTime, nullable=True)  # 撤销时间
    last_used_at = Column(DateTime, nullable=True)  # 最后使用时间

    __table_args__ = (
        Index("idx_refresh_tokens_user_revoked", "user_id", "is_revoked"),
        Index("idx_refresh_tokens_expires", "expires_at"),
    )

class PhoneOTPORM(Base, TimestampMixin):
    __tablename__ = "phone_otps"

    otp_id = Column(String(36), primary_key=True, index=True)
    phone_number = Column(String(20), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    used = Column(Boolean, nullable=False, default=False, index=True)
    attempts = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_otps_phone_expires", "phone_number", "expires_at"),
        Index("idx_otps_used", "used"),
    )


class EmailOTPORM(Base, TimestampMixin):
    __tablename__ = "email_otps"

    otp_id = Column(String(36), primary_key=True, index=True)
    email = Column(String(100), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    used = Column(Boolean, nullable=False, default=False, index=True)
    attempts = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_email_otps_email_expires", "email", "expires_at"),
        Index("idx_email_otps_used", "used"),
    )


# 统一会话表：支持查询和梳理两种模式
class ConversationSessionORM(Base, TimestampMixin):
    __tablename__ = "conversation_sessions"

    session_id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    mode = Column(String(20), nullable=False, index=True)  # query 或 organize
    is_active = Column(Boolean, nullable=False, default=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)  # 过期时间，默认创建后6个月

    __table_args__ = (
        Index("idx_sessions_user_mode_active", "user_id", "mode", "is_active"),
        Index("idx_sessions_expires", "expires_at"),
    )


class ConversationMessageORM(Base, TimestampMixin):
    __tablename__ = "conversation_messages"

    message_id = Column(String(36), primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("conversation_sessions.session_id"), nullable=False, index=True)
    role = Column(String(10), nullable=False)  # user | bot
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_messages_session_created", "session_id", "created_at"),
    )


# 文档表：记录用户上传的文档
class DocumentORM(Base, TimestampMixin):
    __tablename__ = "documents"

    doc_id = Column(String(36), primary_key=True, index=True)  # UUID
    user_id = Column(String(36), nullable=False, index=True)  # 所属用户
    title = Column(String(200), nullable=False)  # 文档标题
    filename = Column(String(255), nullable=True)  # 原始文件名
    file_path = Column(String(500), nullable=True)  # 文件存储路径
    file_size = Column(Integer, nullable=True)  # 文件大小（字节）
    doc_type = Column(String(20), nullable=False, default='other')  # text, pdf, docx, markdown, other
    content = Column(LONGTEXT, nullable=True)  # 文本内容（对于纯文本文档，使用LONGTEXT支持大文档）
    status = Column(String(20), nullable=False, default='indexed')  # uploading, processing, indexed, failed, deleted
    vector_id = Column(Text, nullable=True)  # Qdrant向量ID（可能包含多个ID用逗号分隔）
    
    # 软删除字段
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)  # 是否已删除
    deleted_at = Column(DateTime, nullable=True)  # 删除时间
    
    # JSON字段（存储为文本）
    tags = Column(LONGTEXT, nullable=True)  # JSON数组字符串
    doc_metadata = Column(LONGTEXT, nullable=True)  # JSON对象字符串（避免与metadata冲突）

    __table_args__ = (
        Index("idx_documents_user_deleted", "user_id", "is_deleted"),
        Index("idx_documents_status", "status"),
        Index("idx_documents_deleted_at", "deleted_at"),
    )