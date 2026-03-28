import uuid
from typing import Optional, List
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import select, desc, and_

from app.core.sql import SessionLocal
from app.models.db_models import (
    ConversationSessionORM,
    ConversationMessageORM,
)
from app.models.conversation import ConversationSession, ConversationMessage


class SQLConversationStore:
    """基于MySQL的会话与消息存储实现（统一表）"""

    # Sessions
    def open_session(self, user_id: str, mode: str) -> ConversationSession:
        with SessionLocal() as db:
            # 查找用户在该模式下的活跃会话
            existing = db.execute(
                select(ConversationSessionORM)
                .where(
                    ConversationSessionORM.user_id == user_id,
                    ConversationSessionORM.mode == mode,
                    ConversationSessionORM.is_active == True,
                )
            ).scalar_one_or_none()
            
            if existing:
                # 用户重新使用会话，延长过期时间，但不更新 updated_at
                existing.expires_at = datetime.utcnow() + timedelta(days=180)  # 6个月
                # 不更新 updated_at，只有添加消息时才更新
                db.commit()
                return self._to_session(existing)
            
            # 创建新会话前，先失活同用户同模式下的所有旧会话
            old_sessions = db.execute(
                select(ConversationSessionORM).where(
                    and_(
                        ConversationSessionORM.user_id == user_id,
                        ConversationSessionORM.mode == mode,
                        ConversationSessionORM.is_active == True,
                    )
                )
            ).scalars().all()
            
            for old in old_sessions:
                old.is_active = False
                # 不更新 updated_at，保持原有时间
            
            # 创建新会话
            sid = str(uuid.uuid4())
            orm = ConversationSessionORM(
                session_id=sid,
                user_id=user_id,
                mode=mode,
                is_active=True,
                started_at=datetime.utcnow(),
                ended_at=None,
                expires_at=datetime.utcnow() + timedelta(days=180),  # 设置6个月后过期
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(orm)
            db.commit()
            db.refresh(orm)
            return self._to_session(orm)

    def close_session(self, session_id: str) -> bool:
        with SessionLocal() as db:
            orm = db.execute(
                select(ConversationSessionORM).where(ConversationSessionORM.session_id == session_id)
            ).scalar_one_or_none()
            
            if not orm:
                return False
            
            # 检查该会话是否有任何消息
            count = db.execute(
                select(ConversationMessageORM)
                .where(ConversationMessageORM.session_id == session_id)
                .limit(1)
            ).first()
            has_messages = count is not None
            
            # 如果会话没有消息，直接删除；否则只标记为关闭
            if not has_messages:
                logger.info(f"删除空会话: session_id={session_id}, mode={orm.mode}")
                db.delete(orm)
            else:
                orm.is_active = False
                orm.ended_at = datetime.utcnow()
                orm.updated_at = datetime.utcnow()
            
            db.commit()
            return True

    def get_active_session(self, user_id: str, mode: str) -> Optional[ConversationSession]:
        with SessionLocal() as db:
            orm = db.execute(
                select(ConversationSessionORM)
                .where(
                    ConversationSessionORM.user_id == user_id,
                    ConversationSessionORM.mode == mode,
                    ConversationSessionORM.is_active == True,
                )
            ).scalar_one_or_none()
            return self._to_session(orm) if orm else None

    def list_sessions(self, user_id: str, mode: Optional[str] = None, limit: int = 50) -> List[ConversationSession]:
        """
        列出用户的会话
        mode: 如果为 None，返回所有模式的会话；否则只返回指定模式的会话
        """
        with SessionLocal() as db:
            query = select(ConversationSessionORM).where(ConversationSessionORM.user_id == user_id)
            
            if mode:
                query = query.where(ConversationSessionORM.mode == mode)
            
            result = db.execute(
                query.order_by(desc(ConversationSessionORM.updated_at)).limit(limit)
            )
            return [self._to_session(orm) for orm in result.scalars().all()]

    def get_first_user_message_preview(self, session_id: str, max_len: int = 20) -> Optional[str]:
        with SessionLocal() as db:
            orm = db.execute(
                select(ConversationMessageORM)
                .where(
                    ConversationMessageORM.session_id == session_id,
                    ConversationMessageORM.role == "user",
                )
                .order_by(ConversationMessageORM.created_at.asc())
                .limit(1)
            ).scalar_one_or_none()
            
            if not orm:
                return None
            text = orm.content or ""
            return text[:max_len]

    # Messages
    def save_message(self, session_id: str, role: str, content: str) -> ConversationMessage:
        with SessionLocal() as db:
            mid = str(uuid.uuid4())
            now = datetime.utcnow()
            
            # 检查会话是否存在
            sess = db.execute(
                select(ConversationSessionORM).where(ConversationSessionORM.session_id == session_id)
            ).scalar_one_or_none()
            
            if sess is None:
                raise ValueError("session不存在")
            
            orm = ConversationMessageORM(
                message_id=mid,
                session_id=session_id,
                role=role,
                content=content,
                created_at=now,
                updated_at=now,
            )
            db.add(orm)
            
            # 更新会话活跃时间
            sess.updated_at = now
            db.commit()
            db.refresh(orm)
            return self._to_message(orm)

    def list_messages(self, session_id: str, limit: int = 100) -> List[ConversationMessage]:
        with SessionLocal() as db:
            result = db.execute(
                select(ConversationMessageORM)
                .where(ConversationMessageORM.session_id == session_id)
                .order_by(ConversationMessageORM.created_at.asc())
                .limit(limit)
            )
            return [self._to_message(m) for m in result.scalars().all()]

    def activate_session(self, user_id: str, session_id: str) -> Optional[ConversationSession]:
        with SessionLocal() as db:
            target = db.execute(
                select(ConversationSessionORM).where(ConversationSessionORM.session_id == session_id)
            ).scalar_one_or_none()
            
            if target is None:
                return None
            
            # 所有权校验
            if target.user_id != user_id:
                return None
            
            # 失活同用户同模式的其他会话
            others = db.execute(
                select(ConversationSessionORM).where(
                    and_(
                        ConversationSessionORM.user_id == user_id,
                        ConversationSessionORM.mode == target.mode,
                        ConversationSessionORM.session_id != session_id,
                    )
                )
            ).scalars().all()
            
            for o in others:
                o.is_active = False
                # 注意：失活其他会话时不更新 updated_at，保持原有时间
            
            # 激活目标会话，延长过期时间，但不更新 updated_at
            target.is_active = True
            target.expires_at = datetime.utcnow() + timedelta(days=180)  # 用户进入会话，重置过期时间为6个月
            # 不更新 updated_at，只有添加消息时才更新
            db.commit()
            db.refresh(target)
            return self._to_session(target)

    def cleanup_expired_sessions(self) -> int:
        """清理过期的会话（expires_at 已过的会话）。返回删除的会话数量。"""
        total_deleted = 0
        now = datetime.utcnow()
        with SessionLocal() as db:
            # 查找所有过期会话
            expired = db.execute(
                select(ConversationSessionORM)
                .where(
                    ConversationSessionORM.expires_at.isnot(None),
                    ConversationSessionORM.expires_at < now
                )
            ).scalars().all()
            
            for session in expired:
                # 先删除该会话的所有消息
                db.query(ConversationMessageORM).filter(
                    ConversationMessageORM.session_id == session.session_id
                ).delete()
                # 删除会话
                db.delete(session)
                total_deleted += 1
            
            db.commit()
            
        if total_deleted > 0:
            logger.info(f"清理了 {total_deleted} 个过期会话")
        return total_deleted

    # mapping helpers
    def _to_session(self, orm) -> ConversationSession:
        return ConversationSession(
            session_id=orm.session_id,
            user_id=orm.user_id,
            mode=orm.mode,
            is_active=orm.is_active,
            started_at=orm.started_at,
            ended_at=orm.ended_at,
            expires_at=getattr(orm, 'expires_at', None),  # 支持旧数据兼容
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _to_message(self, orm) -> ConversationMessage:
        return ConversationMessage(
            message_id=orm.message_id,
            session_id=orm.session_id,
            role=orm.role,
            content=orm.content,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )


class ConversationService:
    """对外提供会话管理与历史消息功能"""

    def __init__(self):
        self.store = SQLConversationStore()

    def open_session(self, user_id: str, mode: str) -> ConversationSession:
        return self.store.open_session(user_id, mode)

    def close_session(self, session_id: str) -> bool:
        return self.store.close_session(session_id)

    def get_active_session(self, user_id: str, mode: str) -> Optional[ConversationSession]:
        return self.store.get_active_session(user_id, mode)

    def list_sessions(self, user_id: str, mode: Optional[str] = None, limit: int = 50) -> List[ConversationSession]:
        return self.store.list_sessions(user_id, mode, limit)

    def get_first_user_message_preview(self, session_id: str, max_len: int = 20) -> Optional[str]:
        return self.store.get_first_user_message_preview(session_id, max_len)

    def save_message(self, session_id: str, role: str, content: str) -> ConversationMessage:
        return self.store.save_message(session_id, role, content)

    def list_messages(self, session_id: str, limit: int = 100) -> List[ConversationMessage]:
        return self.store.list_messages(session_id, limit)

    def activate_session(self, user_id: str, session_id: str) -> Optional[ConversationSession]:
        return self.store.activate_session(user_id, session_id)

    def cleanup_expired_sessions(self) -> int:
        """清理过期的会话（过期时间已过的会话）。返回删除的会话数量。"""
        return self.store.cleanup_expired_sessions()


_service_instance: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ConversationService()
    return _service_instance
