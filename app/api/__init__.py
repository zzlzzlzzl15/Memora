from fastapi import APIRouter

from app.api import auth, documents, users

# 创建主API路由器
api_router = APIRouter(prefix="/api/v1")

# 注册各个模块的路由
#api_router.include_router(auth.router)
#api_router.include_router(documents.router)
#api_router.include_router(users.router)

__all__ = ["api_router"]