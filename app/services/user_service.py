import uuid
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import select

from app.models.user import UserCreate, UserUpdate, UserInDB, User, UserLogin, UserPhoneLogin
from app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token
from config.settings import settings
from app.core.sql import SessionLocal
from app.models.db_models import UserORM, PhoneOTPORM, EmailOTPORM
from fastapi.concurrency import run_in_threadpool
from app.core.email import get_email_service
from app.services.refresh_token_service import get_refresh_token_service

# 已移除内存存储实现，统一使用 SQLUserStore（MySQL）
class UserService:
    """用户服务"""
    
    def __init__(self):
        self.store = SQLUserStore()
    
    async def ensure_default_admin(self):
        """确保默认管理员存在（仅在启动时调用）"""
        admin_username = "admin"
        existing = await run_in_threadpool(self.store.get_user_by_username, admin_username)
        if not existing:
            admin_user = UserInDB(
                user_id=str(uuid.uuid4()),
                username=admin_username,
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            await run_in_threadpool(self.store.create_user, admin_user)
            logger.info("默认管理员用户已创建: admin/admin123")
    
    async def create_user(self, user_create: UserCreate) -> User:
        """创建新用户"""
        logger.info(f"Register: start for '{user_create.username}'")
        
        if not user_create.email or not user_create.otp_code:
            raise ValueError("邮箱和验证码为必填项")
        
        is_valid = await self.verify_email_otp(user_create.email, user_create.otp_code)
        if not is_valid:
            raise ValueError("验证码无效或已过期")

        # 构造新用户并直接写库，依赖唯一约束避免重复
        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(user_create.password)

        user_in_db = UserInDB(
            user_id=user_id,
            username=user_create.username,
            email=user_create.email,
            phone_number=user_create.phone_number,
            hashed_password=hashed_password,
            is_active=user_create.is_active,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        logger.info("Register: writing to DB")
        try:
            created_user = await asyncio.wait_for(
                run_in_threadpool(self.store.create_user, user_in_db),
                timeout=5
            )
        except asyncio.TimeoutError:
            logger.warning("Register: timeout during create_user")
            raise ValueError("数据库写入超时，请稍后再试")

        logger.info(f"Register: success user_id={created_user.user_id}")
        return User(
            user_id=created_user.user_id,
            username=created_user.username,
            email=created_user.email,
            phone_number=created_user.phone_number,
            is_active=created_user.is_active,
            created_at=created_user.created_at,
            updated_at=created_user.updated_at
        )
    
    async def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        """用户认证(支持用户名或邮箱或手机号)"""
        logger.info(f"Auth: fetching user '{username}'")
        # 先尝试用户名
        user = await run_in_threadpool(self.store.get_user_by_username, username)
        # 如果用户名找不到,尝试邮箱
        if not user:
            logger.info("Auth: try by email")
            user = await run_in_threadpool(self.store.get_user_by_email, username)
        # 如果邮箱找不到,尝试手机号
        if not user:
            logger.info("Auth: try by phone")
            user = await run_in_threadpool(self.store.get_user_by_phone, username)
        
        if not user:
            logger.info("Auth: user not found")
            return None
        
        logger.info("Auth: verifying password")
        if not verify_password(password, user.hashed_password):
            logger.info("Auth: password mismatch")
            return None
        
        if not user.is_active:
            logger.info("Auth: user inactive")
            return None
        
        logger.info("Auth: success")
        return user

    async def authenticate_user_by_phone(self, phone_number: str, password: str) -> Optional[UserInDB]:
        """手机号+密码认证"""
        logger.info(f"Auth: fetching user by phone '{phone_number}'")
        user = await run_in_threadpool(self.store.get_user_by_phone, phone_number)
        if not user:
            logger.info("Auth: user by phone not found")
            return None
        logger.info("Auth: verifying password")
        if not verify_password(password, user.hashed_password):
            logger.info("Auth: password mismatch")
            return None
        if not user.is_active:
            logger.info("Auth: user inactive")
            return None
        logger.info("Auth: success")
        return user

    async def login_by_phone(
        self, 
        phone_login: UserPhoneLogin,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """手机号密码登录"""
        logger.info(f"Login(phone): start for '{phone_login.phone_number}'")
        user = await self.authenticate_user_by_phone(phone_login.phone_number, phone_login.password)
        if not user:
            raise ValueError("手机号或密码错误")
        
        # 创建 access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.user_id},
            expires_delta=access_token_expires
        )
        
        # 创建 refresh token
        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": user.user_id}
        )
        
        # 保存 refresh_token 到数据库
        refresh_token_service = get_refresh_token_service()
        await run_in_threadpool(
            refresh_token_service.create_refresh_token_record,
            user.user_id,
            refresh_token,
            device_info,
            ip_address
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "user": User(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                phone_number=user.phone_number,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
        }

    async def send_email_otp(self, email: str, for_login: bool = False) -> None:
        """
        发送邮箱验证码（生成并写库，真实发送邮件）
        
        Args:
            email: 邮箱地址
            for_login: 是否用于登录场景，如果为True，会检查邮箱是否已注册
        """
        # 如果是登录场景，先检查邮箱是否已注册
        if for_login:
            user = await run_in_threadpool(self.store.get_user_by_email, email)
            if not user:
                raise ValueError("该邮箱未注册，请先注册")
        
        import random
        code = f"{random.randint(100000, 999999)}"
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        await run_in_threadpool(self.store.create_email_otp, email, code, expires_at)
        
        # 发送邮件
        email_service = get_email_service()
        
        if email_service.smtp_host and email_service.smtp_username and email_service.smtp_password:
            success = email_service.send_otp_email(email, code, expires_minutes=5)
            if success:
                logger.info(f"OTP邮件发送成功: {email}")
            else:
                logger.error(f"OTP邮件发送失败: {email}")
                logger.warning(f"[调试用] OTP for {email}: {code} (expires in 5 minutes)")
        else:
            logger.info(f"OTP for {email}: {code} (expires in 5 minutes) - 邮件服务未配置，输出到日志")

    async def verify_email_otp(self, email: str, code: str, consume: bool = False) -> bool:
        """验证邮箱验证码(不消耗,可用于注册验证)"""
        return await run_in_threadpool(self.store.verify_email_otp, email, code, consume=consume)

    async def send_phone_otp(self, phone_number: str) -> None:
        """发送手机号验证码（生成并写库，模拟发送：日志输出）"""
        import random
        code = f"{random.randint(100000, 999999)}"
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        await run_in_threadpool(self.store.create_phone_otp, phone_number, code, expires_at)
        logger.info(f"OTP for {phone_number}: {code} (expires in 5 minutes)")

    async def verify_phone_otp(self, phone_number: str, code: str) -> bool:
        """验证手机号验证码(不消耗,可用于注册验证)"""
        return await run_in_threadpool(self.store.verify_phone_otp, phone_number, code, consume=False)

    async def login_by_otp(
        self,
        phone_number: str,
        code: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """通过手机号验证码登录"""
        valid = await run_in_threadpool(self.store.verify_phone_otp, phone_number, code)
        if not valid:
            raise ValueError("验证码无效或已过期")
        # 必须已有用户
        user = await run_in_threadpool(self.store.get_user_by_phone, phone_number)
        if not user:
            raise ValueError("用户不存在，请先注册")
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.user_id},
            expires_delta=access_token_expires
        )
        
        # 创建 refresh token
        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": user.user_id}
        )
        
        # 保存 refresh_token 到数据库
        refresh_token_service = get_refresh_token_service()
        await run_in_threadpool(
            refresh_token_service.create_refresh_token_record,
            user.user_id,
            refresh_token,
            device_info,
            ip_address
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "user": User(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                phone_number=user.phone_number,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
        }

    async def login_by_email_otp(
        self,
        email: str,
        code: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """通过邮箱验证码登录"""
        valid = await run_in_threadpool(self.store.verify_email_otp, email, code)
        if not valid:
            raise ValueError("验证码无效或已过期")
        # 必须已有用户
        user = await run_in_threadpool(self.store.get_user_by_email, email)
        if not user:
            raise ValueError("用户不存在，请先注册")
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.user_id},
            expires_delta=access_token_expires
        )
        
        # 创建 refresh token
        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": user.user_id}
        )
        
        # 保存 refresh_token 到数据库
        refresh_token_service = get_refresh_token_service()
        await run_in_threadpool(
            refresh_token_service.create_refresh_token_record,
            user.user_id,
            refresh_token,
            device_info,
            ip_address
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "user": User(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                phone_number=user.phone_number,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
        }

    async def login(
        self,
        user_login: UserLogin,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """用户登录(支持用户名或手机号)"""
        logger.info(f"Login: start for '{user_login.username}'")
        user = await self.authenticate_user(user_login.username, user_login.password)
        if not user:
            raise ValueError("用户名/手机号或密码错误")
        
        # 创建访问令牌
        logger.info("Login: creating access token")
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.user_id},
            expires_delta=access_token_expires
        )
        
        # 创建 refresh token
        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": user.user_id}
        )
        
        # 保存 refresh_token 到数据库
        refresh_token_service = get_refresh_token_service()
        await run_in_threadpool(
            refresh_token_service.create_refresh_token_record,
            user.user_id,
            refresh_token,
            device_info,
            ip_address
        )
        
        logger.info("Login: success")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "user": User(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                phone_number=user.phone_number,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
        }
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        user = await run_in_threadpool(self.store.get_user_by_id, user_id)
        if not user:
            return None
        
        return User(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            phone_number=user.phone_number,
            is_active=user.is_active,
            avatar_url=user.avatar_url,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        user = await run_in_threadpool(self.store.get_user_by_username, username)
        if not user:
            return None
        
        return User(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            phone_number=user.phone_number,
            is_active=user.is_active,
            avatar_url=user.avatar_url,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    
    async def update_user(self, user_id: str, user_update: UserUpdate) -> Optional[User]:
        """更新用户信息"""
        update_data = user_update.dict(exclude_unset=True)
        
        # 如果更新密码，需要加密
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        
        updated_user = await run_in_threadpool(self.store.update_user, user_id, update_data)
        if not updated_user:
            return None
        
        return User(
            user_id=updated_user.user_id,
            username=updated_user.username,
            email=updated_user.email,
            phone_number=updated_user.phone_number,
            is_active=updated_user.is_active,
            avatar_url=updated_user.avatar_url,
            created_at=updated_user.created_at,
            updated_at=updated_user.updated_at
        )
    
    async def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        return await run_in_threadpool(self.store.delete_user, user_id)
    
    async def list_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """列出用户"""
        users_in_db = await run_in_threadpool(self.store.list_users, skip, limit)
        return [
            User(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                phone_number=user.phone_number,
                is_active=user.is_active,
                avatar_url=user.avatar_url,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
            for user in users_in_db
        ]

# 全局用户服务实例
_user_service = None

def get_user_service() -> UserService:
    """获取用户服务实例（单例模式）"""
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service


class SQLUserStore:
    """基于MySQL的用户存储实现（SQLAlchemy）"""

    def _to_user_in_db(self, orm: UserORM) -> UserInDB:
        return UserInDB(
            user_id=orm.user_id,
            username=orm.username,
            email=orm.email,
            phone_number=orm.phone_number,
            hashed_password=orm.hashed_password,
            is_active=orm.is_active,
            avatar_url=orm.avatar_url,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def create_user(self, user_data: UserInDB) -> UserInDB:
        from sqlalchemy.exc import IntegrityError
        with SessionLocal() as db:
            orm = UserORM(
                user_id=user_data.user_id,
                username=user_data.username,
                email=user_data.email,
                phone_number=user_data.phone_number,
                hashed_password=user_data.hashed_password,
                is_active=user_data.is_active,
                created_at=user_data.created_at,
                updated_at=user_data.updated_at,
            )
            db.add(orm)
            try:
                db.commit()
            except IntegrityError as exc:
                db.rollback()
                # 统一错误提示，避免额外查询
                raise ValueError("用户名或邮箱已存在") from exc
            db.refresh(orm)
            return self._to_user_in_db(orm)

    def get_user_by_id(self, user_id: str) -> Optional[UserInDB]:
        with SessionLocal() as db:
            orm = db.execute(select(UserORM).where(UserORM.user_id == user_id)).scalar_one_or_none()
            return self._to_user_in_db(orm) if orm else None

    def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        with SessionLocal() as db:
            orm = db.execute(select(UserORM).where(UserORM.email == email)).scalar_one_or_none()
            return self._to_user_in_db(orm) if orm else None

    def get_user_by_username(self, username: str) -> Optional[UserInDB]:
        with SessionLocal() as db:
            orm = db.execute(select(UserORM).where(UserORM.username == username)).scalar_one_or_none()
            return self._to_user_in_db(orm) if orm else None

    def get_user_by_phone(self, phone_number: str) -> Optional[UserInDB]:
        with SessionLocal() as db:
            orm = db.execute(select(UserORM).where(UserORM.phone_number == phone_number)).scalar_one_or_none()
            return self._to_user_in_db(orm) if orm else None

    def create_phone_otp(self, phone_number: str, code: str, expires_at: datetime) -> None:
        """创建手机号验证码记录"""
        with SessionLocal() as db:
            otp = PhoneOTPORM(
                otp_id=str(uuid.uuid4()),
                phone_number=phone_number,
                code=code,
                expires_at=expires_at,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                used=False,
                attempts=0,
            )
            db.add(otp)
            db.commit()

    def verify_phone_otp(self, phone_number: str, code: str, consume: bool = True) -> bool:
        """验证验证码是否有效；有效且consume=True则标记为已使用"""
        with SessionLocal() as db:
            now = datetime.utcnow()
            result = db.execute(
                select(PhoneOTPORM)
                .where(
                    PhoneOTPORM.phone_number == phone_number,
                    PhoneOTPORM.code == code,
                    PhoneOTPORM.used == False,  # noqa: E712
                    PhoneOTPORM.expires_at > now,
                )
                .order_by(PhoneOTPORM.created_at.desc())
            )
            otp = result.scalars().first()
            if not otp:
                return False
            if consume:
                otp.used = True
                otp.updated_at = now
                db.commit()
            return True

    def create_email_otp(self, email: str, code: str, expires_at: datetime) -> None:
        """创建邮箱验证码记录"""
        with SessionLocal() as db:
            otp = EmailOTPORM(
                otp_id=str(uuid.uuid4()),
                email=email,
                code=code,
                expires_at=expires_at,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                used=False,
                attempts=0,
            )
            db.add(otp)
            db.commit()

    def verify_email_otp(self, email: str, code: str, consume: bool = True) -> bool:
        """验证邮箱验证码是否有效；有效且consume=True则标记为已使用"""
        with SessionLocal() as db:
            now = datetime.utcnow()
            result = db.execute(
                select(EmailOTPORM)
                .where(
                    EmailOTPORM.email == email,
                    EmailOTPORM.code == code,
                    EmailOTPORM.used == False,  # noqa: E712
                    EmailOTPORM.expires_at > now,
                )
                .order_by(EmailOTPORM.created_at.desc())
            )
            otp = result.scalars().first()
            if not otp:
                return False
            if consume:
                otp.used = True
                otp.updated_at = now
                db.commit()
            return True

    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Optional[UserInDB]:
        with SessionLocal() as db:
            orm = db.execute(select(UserORM).where(UserORM.user_id == user_id)).scalar_one_or_none()
            if not orm:
                return None
            if "username" in update_data and update_data["username"] != orm.username:
                if db.execute(select(UserORM).where(UserORM.username == update_data["username"])) .scalar_one_or_none():
                    raise ValueError(f"用户名 '{update_data['username']}' 已存在")
                orm.username = update_data["username"]
            if "email" in update_data and update_data["email"] != orm.email:
                if db.execute(select(UserORM).where(UserORM.email == update_data["email"])) .scalar_one_or_none():
                    raise ValueError(f"邮箱 '{update_data['email']}' 已存在")
                orm.email = update_data["email"]
            if "phone_number" in update_data:
                # 允许清空手机号
                new_phone = update_data["phone_number"]
                if new_phone and new_phone != orm.phone_number:
                    # 检查手机号是否已被其他用户使用
                    existing = db.execute(select(UserORM).where(UserORM.phone_number == new_phone)).scalar_one_or_none()
                    if existing and existing.user_id != user_id:
                        raise ValueError(f"手机号 '{new_phone}' 已存在")
                orm.phone_number = new_phone
            if "is_active" in update_data:
                orm.is_active = update_data["is_active"]
            if "hashed_password" in update_data:
                orm.hashed_password = update_data["hashed_password"]
            if "avatar_url" in update_data:
                orm.avatar_url = update_data["avatar_url"]
            orm.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(orm)
            return self._to_user_in_db(orm)

    def delete_user(self, user_id: str) -> bool:
        with SessionLocal() as db:
            orm = db.execute(select(UserORM).where(UserORM.user_id == user_id)).scalar_one_or_none()
            if not orm:
                return False
            db.delete(orm)
            db.commit()
            return True

    def list_users(self, skip: int = 0, limit: int = 100) -> List[UserInDB]:
        with SessionLocal() as db:
            result = db.execute(select(UserORM).order_by(UserORM.created_at.desc()).offset(skip).limit(limit))
            return [self._to_user_in_db(orm) for orm in result.scalars().all()]