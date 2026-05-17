"""
安全模块 - 单用户模式版本
去掉了多用户JWT认证，改为固定单用户模式
"""
from typing import Dict, Any

# 单用户模式的固定用户ID（使用字符串以兼容 documents.user_id varchar(36) 和 uploads/<user_id>/ 路径拼接）
DEFAULT_USER_ID = "1"
DEFAULT_USERNAME = "admin"


async def get_current_active_user() -> Dict[str, Any]:
    """
    获取当前用户（单用户模式）
    不再进行JWT验证，直接返回默认用户
    """
    return {
        "user_id": DEFAULT_USER_ID,
        "sub": DEFAULT_USERNAME
    }


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码（单用户模式下不再使用）"""
    return True


def get_password_hash(password: str) -> str:
    """获取密码哈希（单用户模式下不再使用）"""
    return ""


def hash_token(token: str) -> str:
    """生成token的哈希（单用户模式下不再使用）"""
    return ""


def create_access_token(data: dict, expires_delta=None) -> str:
    """创建访问令牌（单用户模式下不再使用）"""
    return ""


def create_refresh_token(data: dict) -> str:
    """创建刷新令牌（单用户模式下不再使用）"""
    return ""


def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """验证令牌（单用户模式下不再使用）"""
    return {"user_id": DEFAULT_USER_ID, "sub": DEFAULT_USERNAME}


async def get_current_user() -> Dict[str, Any]:
    """获取当前用户（单用户模式）"""
    return {"user_id": DEFAULT_USER_ID, "sub": DEFAULT_USERNAME}
