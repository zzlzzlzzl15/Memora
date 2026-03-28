from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from typing import List
import os
import uuid
from pathlib import Path

from app.models.user import User, UserUpdate
from app.services.user_service import get_user_service
from app.core.security import get_current_active_user
from app.core.logging import get_request_logger
from config.settings import settings

router = APIRouter(prefix="/users", tags=["用户管理"])

@router.get("/profile", response_model=User, summary="获取用户资料")
async def get_user_profile(current_user: dict = Depends(get_current_active_user), req_logger = Depends(get_request_logger)):
    """获取当前用户的详细资料"""
    req_logger.info(f"Users.profile.get: start user_id='{current_user['user_id']}'")
    try:
        user_service = get_user_service()
        user = await user_service.get_user_by_id(current_user["user_id"])
        if not user:
            req_logger.info("Users.profile.get: not_found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        req_logger.info(f"Users.profile.get: success user_id='{user.user_id}'")
        return user
    except HTTPException:
        req_logger.info("Users.profile.get: http_exception")
        raise
    except Exception as e:
        req_logger.exception(f"Users.profile.get: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户资料失败"
        )

@router.post("/avatar", response_model=User, summary="上传用户头像")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """上传用户头像"""
    req_logger.info(f"Users.avatar.upload: start user_id='{current_user['user_id']}' filename='{file.filename}'")
    try:
        # 验证文件类型
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件类型: {file.content_type}。请上传 JPEG, PNG, GIF 或 WebP 格式的图片"
            )
        
        # 验证文件大小 (5MB)
        content = await file.read()
        file_size = len(content)
        if file_size > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="头像文件大小不能超过 5MB"
            )
        
        # 创建头像存储目录（基于项目根目录的static/avatars）
        project_root = Path(__file__).parent.parent.parent
        avatars_dir = project_root / "static" / "avatars"
        avatars_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成唯一文件名
        file_ext = Path(file.filename).suffix.lower()
        if not file_ext:
            # 根据 content_type 推断扩展名
            ext_map = {
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "image/webp": ".webp"
            }
            file_ext = ext_map.get(file.content_type, ".jpg")
        
        filename = f"{current_user['user_id']}_{uuid.uuid4().hex[:8]}{file_ext}"
        file_path = avatars_dir / filename
        
        # 删除用户的旧头像
        user_service = get_user_service()
        user = await user_service.get_user_by_id(current_user["user_id"])
        if user and user.avatar_url:
            # 提取旧头像文件名
            old_filename = user.avatar_url.split("/")[-1]
            old_file_path = avatars_dir / old_filename
            if old_file_path.exists():
                try:
                    old_file_path.unlink()
                    req_logger.info(f"Users.avatar.upload: deleted old avatar '{old_filename}'")
                except Exception as e:
                    req_logger.warning(f"Users.avatar.upload: failed to delete old avatar: {e}")
        
        # 保存新头像
        with open(file_path, "wb") as f:
            f.write(content)
        
        req_logger.info(f"Users.avatar.upload: saved to '{file_path}'")
        
        # 更新用户avatar_url
        avatar_url = f"/static/avatars/{filename}"
        from app.models.user import UserUpdate
        update_model = UserUpdate()
        update_model.avatar_url = avatar_url
        
        req_logger.info(f"Users.avatar.upload: updating user with avatar_url='{avatar_url}'")
        req_logger.info(f"Users.avatar.upload: update_model dict={update_model.dict(exclude_unset=True)}")
        
        updated_user = await user_service.update_user(
            user_id=current_user["user_id"],
            user_update=update_model
        )
        
        req_logger.info(f"Users.avatar.upload: updated_user.avatar_url='{updated_user.avatar_url if updated_user else None}'")
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        req_logger.info(f"Users.avatar.upload: success avatar_url='{avatar_url}'")
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        req_logger.exception(f"Users.avatar.upload: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="上传头像失败"
        )

@router.put("/profile", response_model=User, summary="更新用户资料")
async def update_user_profile(
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """更新当前用户的资料"""
    req_logger.info(f"Users.profile.update: start user_id='{current_user['user_id']}'")
    try:
        user_service = get_user_service()
        user = await user_service.update_user(
            user_id=current_user["user_id"],
            user_update=user_update
        )
        
        if not user:
            req_logger.info("Users.profile.update: not_found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        return user
    except HTTPException:
        req_logger.info("Users.profile.update: http_exception")
        raise
    except ValueError as e:
        req_logger.info(f"Users.profile.update: value_error detail='{str(e)}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        req_logger.exception(f"Users.profile.update: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户资料失败"
        )

@router.put("/profile/email", response_model=User, summary="更新用户邮箱")
async def update_user_email(
    email_update: dict,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """更新当前用户的邮箱"""
    req_logger.info(f"Users.profile.update_email: start user_id='{current_user['user_id']}'")
    try:
        user_service = get_user_service()
        
        # 获取请求参数
        new_email = email_update.get("email")
        old_email = email_update.get("old_email")
        old_email_otp = email_update.get("old_email_otp")
        new_email_otp = email_update.get("new_email_otp")
        
        # 验证参数
        if not new_email or not new_email_otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少必要参数"
            )
        
        # 只验证新邮箱的验证码
        new_valid = await user_service.verify_email_otp(new_email, new_email_otp, consume=False)
        if not new_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="新邮箱验证码错误或已过期"
            )
        
        # 消耗验证码
        await user_service.verify_email_otp(new_email, new_email_otp, consume=True)
        
        # 更新用户邮箱
        from app.models.user import UserUpdate
        user_update = UserUpdate(email=new_email)
        user = await user_service.update_user(
            user_id=current_user["user_id"],
            user_update=user_update
        )
        
        if not user:
            req_logger.info("Users.profile.update_email: not_found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        return user
    except HTTPException:
        req_logger.info("Users.profile.update_email: http_exception")
        raise
    except ValueError as e:
        req_logger.info(f"Users.profile.update_email: value_error detail='{str(e)}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        req_logger.exception(f"Users.profile.update_email: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户邮箱失败"
        )

@router.put("/profile/password", response_model=User, summary="修改用户密码")
async def update_user_password(
    password_update: dict,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """修改当前用户的密码（需要验证旧密码）"""
    req_logger.info(f"Users.profile.update_password: start user_id='{current_user['user_id']}'")
    try:
        user_service = get_user_service()
        
        # 获取请求参数
        old_password = password_update.get("old_password")
        new_password = password_update.get("new_password")
        
        # 验证参数
        if not old_password or not new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少必要参数"
            )
        
        if len(new_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码长度至少6位"
            )
        
        if old_password == new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="新密码不能与旧密码相同"
            )
        
        # 获取用户信息并验证旧密码（需要获取包含密码哈希的完整用户对象）
        user_in_db = await run_in_threadpool(user_service.store.get_user_by_id, current_user["user_id"])
        if not user_in_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 验证旧密码
        from app.core.security import verify_password
        if not verify_password(old_password, user_in_db.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="旧密码错误"
            )
        
        # 更新密码
        from app.models.user import UserUpdate
        user_update = UserUpdate(password=new_password)
        updated_user = await user_service.update_user(
            user_id=current_user["user_id"],
            user_update=user_update
        )
        
        if not updated_user:
            req_logger.info("Users.profile.update_password: not_found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        req_logger.info("Users.profile.update_password: success")
        return updated_user
    except HTTPException:
        req_logger.info("Users.profile.update_password: http_exception")
        raise
    except ValueError as e:
        req_logger.info(f"Users.profile.update_password: value_error detail='{str(e)}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        req_logger.exception(f"Users.profile.update_password: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="修改密码失败"
        )

@router.delete("/profile", summary="删除用户账户")
async def delete_user_account(current_user: dict = Depends(get_current_active_user), req_logger = Depends(get_request_logger)):
    """删除当前用户账户（注意：这将删除所有相关数据）"""
    req_logger.info(f"Users.profile.delete: start user_id='{current_user['user_id']}'")
    try:
        user_service = get_user_service()
        
        # 首先删除用户的所有文档
        from app.services.document_service import get_document_service
        document_service = get_document_service()
        
        # 获取用户的所有文档
        documents = await document_service.list_user_documents(
            user_id=current_user["user_id"],
            skip=0,
            limit=1000  # 假设用户不会有超过1000个文档
        )
        
        # 删除所有文档
        for document in documents:
            await document_service.delete_document(
                document_id=document.document_id,
                user_id=current_user["user_id"]
            )
        
        # 删除用户账户
        success = await user_service.delete_user(current_user["user_id"])
        
        if not success:
            req_logger.info("Users.profile.delete: not_found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        return {"message": "用户账户已删除"}
    except HTTPException:
        req_logger.info("Users.profile.delete: http_exception")
        raise
    except Exception as e:
        req_logger.exception(f"Users.profile.delete: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除用户账户失败"
        )

@router.get("/", response_model=List[User], summary="获取用户列表")
async def list_users(
    skip: int = Query(0, ge=0, description="跳过的用户数量"),
    limit: int = Query(20, ge=1, le=100, description="返回的用户数量"),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """获取用户列表（管理员功能）"""
    req_logger.info(f"Users.list: start skip={skip} limit={limit} by='{current_user.get('sub')}'")
    try:
        # 简单的权限检查：只有admin用户可以查看用户列表
        if current_user.get("sub") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足"
            )
        
        user_service = get_user_service()
        users = await user_service.list_users(skip=skip, limit=limit)
        req_logger.info(f"Users.list: success count={len(users)}")
        return users
    except HTTPException:
        req_logger.info("Users.list: http_exception")
        raise
    except Exception as e:
        req_logger.exception(f"Users.list: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户列表失败"
        )

@router.get("/{user_id}", response_model=User, summary="获取指定用户信息")
async def get_user_by_id(
    user_id: str,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """获取指定用户的信息（管理员功能或查看自己）"""
    req_logger.info(f"Users.get: start user_id='{user_id}' by='{current_user.get('sub')}'")
    try:
        # 权限检查：只能查看自己的信息，或者管理员可以查看任何用户
        if current_user["user_id"] != user_id and current_user.get("sub") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足"
            )
        
        user_service = get_user_service()
        user = await user_service.get_user_by_id(user_id)
        
        if not user:
            req_logger.info("Users.get: not_found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        return user
    except HTTPException:
        req_logger.info("Users.get: http_exception")
        raise
    except Exception as e:
        req_logger.exception(f"Users.get: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息失败"
        )

@router.put("/{user_id}", response_model=User, summary="更新指定用户信息")
async def update_user_by_id(
    user_id: str,
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """更新指定用户的信息（管理员功能）"""
    req_logger.info(f"Users.update: start user_id='{user_id}' by='{current_user.get('sub')}'")
    try:
        # 权限检查：只有管理员可以更新其他用户信息
        if current_user.get("sub") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足"
            )
        
        user_service = get_user_service()
        user = await user_service.update_user(
            user_id=user_id,
            user_update=user_update
        )
        
        if not user:
            req_logger.info("Users.update: not_found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        return user
    except HTTPException:
        req_logger.info("Users.update: http_exception")
        raise
    except ValueError as e:
        req_logger.info(f"Users.update: value_error detail='{str(e)}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        req_logger.exception(f"Users.update: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户信息失败"
        )

@router.delete("/{user_id}", summary="删除指定用户")
async def delete_user_by_id(
    user_id: str,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """删除指定用户（管理员功能）"""
    req_logger.info(f"Users.delete: start user_id='{user_id}' by='{current_user.get('sub')}'")
    try:
        # 权限检查：只有管理员可以删除用户
        if current_user.get("sub") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足"
            )
        
        # 不能删除自己
        if current_user["user_id"] == user_id:
            req_logger.info("Users.delete: try_delete_self")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能删除自己的账户"
            )
        
        user_service = get_user_service()
        success = await user_service.delete_user(user_id)
        
        if not success:
            req_logger.info("Users.delete: not_found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        return {"message": "用户已删除"}
    except HTTPException:
        req_logger.info("Users.delete: http_exception")
        raise
    except Exception as e:
        req_logger.exception(f"Users.delete: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除用户失败"
        )