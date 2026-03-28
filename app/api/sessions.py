"""会话管理 API：管理用户的登录设备和会话"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.core.security import get_current_active_user
from app.core.logging import get_request_logger
from app.services.refresh_token_service import get_refresh_token_service, parse_device_type
from fastapi.concurrency import run_in_threadpool


router = APIRouter(prefix="/sessions", tags=["会话管理"])


class SessionInfo(BaseModel):
    """登录会话信息"""
    token_id: str
    device_type: str  # web/iphone/ipad/android/unknown
    device_info: Optional[str]
    ip_address: Optional[str]
    created_at: str
    last_used_at: Optional[str]
    expires_at: str


@router.get("/active", response_model=List[SessionInfo], summary="获取当前用户的所有活跃会话")
async def get_active_sessions(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """获取当前用户所有有效的登录设备/会话"""
    try:
        user_id = current_user["user_id"]
        req_logger.info(f"Sessions.active: fetching for user_id='{user_id}'")
        
        refresh_token_service = get_refresh_token_service()
        tokens = await run_in_threadpool(
            refresh_token_service.get_user_active_tokens,
            user_id
        )
        
        sessions = [
            SessionInfo(
                token_id=token.token_id,
                device_type=parse_device_type(token.device_info),
                device_info=token.device_info,
                ip_address=token.ip_address,
                created_at=token.created_at.isoformat(),
                last_used_at=token.last_used_at.isoformat() if token.last_used_at else None,
                expires_at=token.expires_at.isoformat()
            )
            for token in tokens
        ]
        
        req_logger.info(f"Sessions.active: found {len(sessions)} active sessions")
        return sessions
    except Exception as e:
        req_logger.exception(f"Sessions.active: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取会话列表失败"
        )


@router.delete("/{token_id}", summary="撤销指定会话（单设备退出登录）")
async def revoke_session(
    token_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """撤销指定的 refresh token，实现单设备退出登录"""
    try:
        user_id = current_user["user_id"]
        req_logger.info(f"Sessions.revoke: user_id='{user_id}', token_id='{token_id}'")
        
        refresh_token_service = get_refresh_token_service()
        
        # 验证 token 是否属于当前用户
        tokens = await run_in_threadpool(
            refresh_token_service.get_user_active_tokens,
            user_id
        )
        
        token_ids = [t.token_id for t in tokens]
        if token_id not in token_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在或不属于当前用户"
            )
        
        # 撤销 token
        success = await run_in_threadpool(
            refresh_token_service.revoke_token_by_id,
            token_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="撤销会话失败"
            )
        
        req_logger.info(f"Sessions.revoke: success")
        return {"message": "会话已撤销", "token_id": token_id}
    except HTTPException:
        raise
    except Exception as e:
        req_logger.exception(f"Sessions.revoke: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="撤销会话失败"
        )


@router.delete("/", summary="撤销所有会话（全设备退出登录）")
async def revoke_all_sessions(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """撤销用户的所有 refresh token，实现全设备退出登录"""
    try:
        user_id = current_user["user_id"]
        req_logger.info(f"Sessions.revoke_all: user_id='{user_id}'")
        
        refresh_token_service = get_refresh_token_service()
        count = await run_in_threadpool(
            refresh_token_service.revoke_all_user_tokens,
            user_id
        )
        
        req_logger.info(f"Sessions.revoke_all: revoked {count} sessions")
        return {"message": f"已撤销 {count} 个会话", "count": count}
    except Exception as e:
        req_logger.exception(f"Sessions.revoke_all: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="撤销所有会话失败"
        )
