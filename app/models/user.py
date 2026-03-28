from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    phone_number: Optional[str] = Field(None, max_length=20, description="手机号")
    is_active: bool = Field(True, description="是否激活")

class UserCreate(UserBase):
    """创建用户模型"""
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    otp_code: Optional[str] = Field(None, description="邮箱验证码")

class UserUpdate(BaseModel):
    """更新用户模型"""
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="用户名")
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=20, description="手机号")
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6, max_length=100)
    avatar_url: Optional[str] = Field(None, description="头像URL")

class UserInDB(UserBase):
    """数据库中的用户模型"""
    user_id: str = Field(..., description="用户ID")
    hashed_password: str = Field(..., description="加密后的密码")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

class User(BaseModel):
    """返回给客户端的用户模型"""
    user_id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    phone_number: Optional[str] = Field(None, description="手机号")
    is_active: bool = Field(True, description="是否激活")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

class UserLogin(BaseModel):
    """用户登录模型"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")

class Token(BaseModel):
    """令牌模型"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field("bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")
    refresh_token: Optional[str] = Field(None, description="刷新令牌（用于换取新的 access_token）")

class UserPhoneLogin(BaseModel):
    """手机号密码登录模型"""
    phone_number: str = Field(..., description="手机号")
    password: str = Field(..., description="密码")

class PhoneOTPRequest(BaseModel):
    """手机号验证码请求/验证模型"""
    phone_number: str = Field(..., description="手机号")
    code: Optional[str] = Field(None, description="验证码，用于校验时传入")

class EmailOTPRequest(BaseModel):
    """邮箱验证码请求/验证模型"""
    email: str = Field(..., description="邮箱地址")
    code: Optional[str] = Field(None, description="验证码，用于校验时传入")
    for_login: bool = Field(False, description="是否用于登录场景，如果为True，会检查邮箱是否已注册")

class EmailOTPLoginRequest(BaseModel):
    """邮箱验证码登录请求模型"""
    email: str = Field(..., description="邮箱地址")
    code: str = Field(..., description="验证码")