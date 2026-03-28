from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class OpenSessionRequest(BaseModel):
    mode: str = Field(..., description="模式：query 或 organize")


class CloseSessionRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    mode: Optional[str] = Field(None, description="模式：query 或 organize（可选）")


class SaveMessageRequest(BaseModel):
    mode: str = Field(..., description="模式：query 或 organize")
    session_id: str = Field(..., description="会话ID")
    role: str = Field(..., description="角色：user 或 bot")
    content: str = Field(..., description="消息内容")


class ConversationSession(BaseModel):
    session_id: str
    user_id: str
    mode: str
    is_active: bool
    started_at: datetime
    ended_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # 过期时间
    created_at: datetime
    updated_at: datetime


class ConversationMessage(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    created_at: datetime
    updated_at: datetime


class ConversationHistoryResponse(BaseModel):
    session: ConversationSession
    messages: List[ConversationMessage]


# 会话列表与摘要
class ConversationSessionSummary(BaseModel):
    session_id: str
    mode: str
    is_active: bool
    started_at: datetime
    updated_at: datetime
    preview: Optional[str] = Field(None, description="首条用户问题的约20字摘要")


class ListSessionsResponse(BaseModel):
    sessions: List[ConversationSessionSummary]


class ActivateSessionRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    mode: Optional[str] = Field('query', description="模式：query 或 organize")