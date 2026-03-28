"""
认证模块 - 已禁用
单用户模式下不再需要认证功能
所有端点已禁用，保留路由结构以避免破坏性变更
"""
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", summary="用户注册（已禁用）")
async def register():
    """单用户模式下不再需要注册功能"""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="单用户模式下不再需要注册功能"
    )


@router.post("/login", summary="用户登录（已禁用）")
async def login():
    """单用户模式下不再需要登录功能"""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="单用户模式下不再需要登录功能"
    )


@router.get("/me", summary="获取当前用户信息（已禁用）")
async def get_current_user_info():
    """单用户模式下不再需要此功能"""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="单用户模式下不再需要此功能"
    )


@router.post("/refresh", summary="刷新令牌（已禁用）")
async def refresh_token():
    """单用户模式下不再需要令牌刷新"""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="单用户模式下不再需要令牌刷新"
    )


@router.post("/login/phone", summary="手机号密码登录（已禁用）")
async def login_by_phone():
    """单用户模式下不再需要登录功能"""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="单用户模式下不再需要登录功能"
    )


@router.post("/otp/send/email", summary="发送邮箱验证码（已禁用）")
async def send_email_otp():
    """单用户模式下不再需要验证码功能"""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="单用户模式下不再需要验证码功能"
    )


@router.post("/login/email-otp", summary="邮箱验证码登录（已禁用）")
async def login_by_email_otp():
    """单用户模式下不再需要登录功能"""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="单用户模式下不再需要登录功能"
    )
