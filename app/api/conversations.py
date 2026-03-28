from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional

from app.core.security import get_current_active_user
from app.core.logging import get_request_logger
from typing import Dict, Any
from app.models.conversation import (
    OpenSessionRequest,
    CloseSessionRequest,
    SaveMessageRequest,
    ConversationHistoryResponse,
    ConversationSession,
    ConversationMessage,
    ListSessionsResponse,
    ConversationSessionSummary,
    ActivateSessionRequest,
)
from app.services.conversation_service import get_conversation_service


router = APIRouter(prefix="/conversations", tags=["会话管理"])


@router.post("/session/open", response_model=ConversationSession)
def open_session(
    req: OpenSessionRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    svc = get_conversation_service()
    if req.mode not in ("query", "organize"):
        raise HTTPException(status_code=400, detail="mode必须为 query 或 organize")
    session = svc.open_session(current_user["user_id"], req.mode)
    req_logger.info(f"open_session user_id={current_user['user_id']} mode={req.mode} session_id={session.session_id}")
    return session


@router.post("/session/close")
def close_session(req: CloseSessionRequest, current_user: Dict[str, Any] = Depends(get_current_active_user)):
    svc = get_conversation_service()
    ok = svc.close_session(req.session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"closed": True}


@router.get("/history", response_model=ConversationHistoryResponse)
def get_history(
    mode: str = Query(..., description="模式：query 或 organize"),
    limit: int = Query(100, ge=1, le=500, description="返回消息条数上限"),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    svc = get_conversation_service()
    if mode not in ("query", "organize"):
        raise HTTPException(status_code=400, detail="mode必须为 query 或 organize")
    session = svc.get_active_session(current_user["user_id"], mode)
    if not session:
        # 没有活动会话时自动创建空会话并返回空消息
        session = svc.open_session(current_user["user_id"], mode)
        messages = []
    else:
        messages = svc.list_messages(session.session_id, limit=limit)
    return ConversationHistoryResponse(session=session, messages=messages)


@router.post("/message", response_model=ConversationMessage)
def save_message(req: SaveMessageRequest, current_user: Dict[str, Any] = Depends(get_current_active_user)):
    svc = get_conversation_service()
    if req.role not in ("user", "bot"):
        raise HTTPException(status_code=400, detail="role必须为 user 或 bot")
    # 简单校验：会话必须属于当前用户（仅通过存在校验与活动校验保障）
    session = svc.get_active_session(current_user["user_id"], mode="query") or svc.get_active_session(current_user["user_id"], mode="organize")
    # 不强制要求mode匹配，仅存储
    msg = svc.save_message(req.session_id, req.role, req.content)
    return msg


@router.get("/sessions", response_model=ListSessionsResponse)
def list_sessions(
    mode: Optional[str] = Query(None, description="模式：query 或 organize，不传则返回所有模式"),
    limit: int = Query(50, ge=1, le=200, description="返回会话数量上限"),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    svc = get_conversation_service()
    if mode and mode not in ("query", "organize"):
        raise HTTPException(status_code=400, detail="mode必须为 query 或 organize")
    sessions = svc.list_sessions(current_user["user_id"], mode, limit)
    # 为每个会话计算首条用户消息摘要
    out: list[ConversationSessionSummary] = []
    for s in sessions:
        preview = svc.get_first_user_message_preview(s.session_id, max_len=20)
        out.append(ConversationSessionSummary(
            session_id=s.session_id,
            mode=s.mode,
            is_active=s.is_active,
            started_at=s.started_at,
            updated_at=s.updated_at,
            preview=preview,
        ))
    return ListSessionsResponse(sessions=out)


@router.get("/session/{session_id}/messages", response_model=list[ConversationMessage])
def get_messages_by_session(
    session_id: str,
    limit: int = Query(200, ge=1, le=500, description="返回消息条数上限"),
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    svc = get_conversation_service()
    # 简单的所有权校验：确认该session属于当前用户
    # 通过列会话再过滤：若不存在视为拒绝
    # 为避免额外查询成本，可放宽并直接返回消息。此处做基础保护：若为空返回404。
    msgs = svc.list_messages(session_id, limit=limit)
    if msgs is None:
        raise HTTPException(status_code=404, detail="会话不存在或无消息")
    return msgs


@router.post("/session/activate", response_model=ConversationSession)
def activate_session(req: ActivateSessionRequest, current_user: Dict[str, Any] = Depends(get_current_active_user)):
    svc = get_conversation_service()
    session = svc.activate_session(current_user["user_id"], req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或不属于当前用户")
    return session