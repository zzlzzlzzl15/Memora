"""Refresh Token 服务：管理长期登录会话"""
from datetime import datetime, timedelta
from typing import Optional, List
import uuid
import re
from loguru import logger
from sqlalchemy.orm import Session

from app.models.db_models import RefreshTokenORM
from app.core.sql import get_db_session
from app.core.security import hash_token
from config.settings import settings


def parse_device_type(user_agent: Optional[str]) -> str:
    """
    从 User-Agent 中解析设备类型
    
    返回值：
    - 'web' - 网页端（Chrome, Firefox, Safari 桌面版等）
    - 'iphone' - iPhone
    - 'ipad' - iPad
    - 'android' - Android 手机/平板
    - 'unknown' - 无法识别
    """
    if not user_agent:
        return 'unknown'
    
    user_agent_lower = user_agent.lower()
    
    # iPhone 检测（注意顺序，iPhone 的 UA 也包含 Safari）
    if 'iphone' in user_agent_lower:
        return 'iphone'
    
    # iPad 检测
    if 'ipad' in user_agent_lower:
        return 'ipad'
    
    # Android 检测
    if 'android' in user_agent_lower:
        # 区分手机和平板（可选，暂时统一为 android）
        return 'android'
    
    # 桌面浏览器检测（Chrome, Firefox, Safari, Edge 等）
    if any(browser in user_agent_lower for browser in ['chrome', 'firefox', 'safari', 'edge', 'opera']):
        # 排除移动端 Safari
        if 'mobile' not in user_agent_lower:
            return 'web'
    
    return 'unknown'


class RefreshTokenService:
    """Refresh Token 管理服务"""

    def __init__(self):
        pass

    def create_refresh_token_record(
        self,
        user_id: str,
        refresh_token: str,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """
        保存 refresh token 到数据库
        
        逻辑：
        1. 解析设备类型（web/iphone/ipad/android）
        2. 删除同一用户的同一设备类型的旧 token 记录
        3. 创建新 token
        
        Args:
            user_id: 用户ID
            refresh_token: JWT refresh token 字符串
            device_info: 设备信息（User-Agent）
            ip_address: 客户端IP地址
            
        Returns:
            token_id: 生成的 token_id
        """
        with get_db_session() as db:
            # 解析设备类型
            device_type = parse_device_type(device_info)
            
            # 删除同一用户同一设备类型的旧 token
            if device_type != 'unknown':
                # 查找同一用户的所有有效 token
                old_tokens = db.query(RefreshTokenORM).filter(
                    RefreshTokenORM.user_id == user_id,
                    RefreshTokenORM.is_revoked == False
                ).all()
                
                # 删除同一设备类型的旧 token
                deleted_count = 0
                for old_token in old_tokens:
                    old_device_type = parse_device_type(old_token.device_info)
                    if old_device_type == device_type:
                        db.delete(old_token)
                        deleted_count += 1
                
                if deleted_count > 0:
                    logger.info(f"RefreshToken: 删除用户 {user_id} 的 {device_type} 设备旧 token，数量: {deleted_count}")
            
            # 创建新 token
            token_id = str(uuid.uuid4())
            token_hash = hash_token(refresh_token)
            expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
            
            token_record = RefreshTokenORM(
                token_id=token_id,
                user_id=user_id,
                token_hash=token_hash,
                device_info=device_info,
                ip_address=ip_address,
                expires_at=expires_at,
                is_revoked=False
            )
            
            db.add(token_record)
            db.commit()
            
            logger.info(f"RefreshToken created: token_id={token_id}, user_id={user_id}, device_type={device_type}")
            return token_id

    def verify_refresh_token(self, refresh_token: str) -> Optional[RefreshTokenORM]:
        """
        验证 refresh token 是否有效（未撤销、未过期）
        
        Args:
            refresh_token: JWT refresh token 字符串
            
        Returns:
            RefreshTokenORM 或 None（如果无效）
        """
        with get_db_session() as db:
            token_hash = hash_token(refresh_token)
            
            token_record = db.query(RefreshTokenORM).filter(
                RefreshTokenORM.token_hash == token_hash
            ).first()
            
            if not token_record:
                logger.warning("RefreshToken not found in database")
                return None
            
            # 检查是否已撤销
            if token_record.is_revoked:
                logger.warning(f"RefreshToken revoked: token_id={token_record.token_id}")
                return None
            
            # 检查是否过期
            if token_record.expires_at < datetime.utcnow():
                logger.warning(f"RefreshToken expired: token_id={token_record.token_id}")
                return None
            
            # 更新最后使用时间
            token_record.last_used_at = datetime.utcnow()
            db.commit()
            
            return token_record

    def revoke_token_by_id(self, token_id: str) -> bool:
        """
        撤销指定的 refresh token（单设备退出登录）
        
        Args:
            token_id: token ID
            
        Returns:
            是否成功撤销
        """
        with get_db_session() as db:
            token_record = db.query(RefreshTokenORM).filter(
                RefreshTokenORM.token_id == token_id
            ).first()
            
            if not token_record:
                logger.warning(f"RefreshToken not found: token_id={token_id}")
                return False
            
            token_record.is_revoked = True
            token_record.revoked_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"RefreshToken revoked: token_id={token_id}")
            return True

    def revoke_all_user_tokens(self, user_id: str) -> int:
        """
        撤销用户的所有 refresh token（全设备退出登录）
        
        Args:
            user_id: 用户ID
            
        Returns:
            撤销的 token 数量
        """
        with get_db_session() as db:
            tokens = db.query(RefreshTokenORM).filter(
                RefreshTokenORM.user_id == user_id,
                RefreshTokenORM.is_revoked == False
            ).all()
            
            count = 0
            for token in tokens:
                token.is_revoked = True
                token.revoked_at = datetime.utcnow()
                count += 1
            
            db.commit()
            logger.info(f"Revoked {count} tokens for user_id={user_id}")
            return count

    def get_user_active_tokens(self, user_id: str) -> List[RefreshTokenORM]:
        """
        获取用户所有有效的 refresh token 列表（用于显示登录设备）
        
        Args:
            user_id: 用户ID
            
        Returns:
            RefreshTokenORM 列表
        """
        with get_db_session() as db:
            tokens = db.query(RefreshTokenORM).filter(
                RefreshTokenORM.user_id == user_id,
                RefreshTokenORM.is_revoked == False,
                RefreshTokenORM.expires_at > datetime.utcnow()
            ).order_by(RefreshTokenORM.created_at.desc()).all()
            
            return tokens

    def cleanup_expired_tokens(self) -> int:
        """
        清理过期和已撤销的 refresh token（定时任务调用）
        
        Returns:
            清理的 token 数量
        """
        with get_db_session() as db:
            # 清理过期的 token
            expired_count = db.query(RefreshTokenORM).filter(
                RefreshTokenORM.expires_at < datetime.utcnow()
            ).delete()
            
            # 清理已撤销的 token（撤销超过 7 天的）
            revoked_threshold = datetime.utcnow() - timedelta(days=7)
            revoked_count = db.query(RefreshTokenORM).filter(
                RefreshTokenORM.is_revoked == True,
                RefreshTokenORM.revoked_at < revoked_threshold
            ).delete()
            
            total_count = expired_count + revoked_count
            
            db.commit()
            logger.info(f"Cleaned up {total_count} refresh tokens (expired: {expired_count}, revoked: {revoked_count})")
            return total_count


# 全局单例
_refresh_token_service = None


def get_refresh_token_service() -> RefreshTokenService:
    """获取 RefreshTokenService 单例"""
    global _refresh_token_service
    if _refresh_token_service is None:
        _refresh_token_service = RefreshTokenService()
    return _refresh_token_service
