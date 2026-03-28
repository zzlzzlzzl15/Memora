from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.engine import make_url
from typing import Generator
from contextlib import contextmanager

from config.settings import settings
from loguru import logger


def ensure_mysql_database():
    """确保目标数据库存在，不存在则创建。"""
    url = make_url(settings.database_url)
    database = url.database

    # 规范化主机，避免 localhost 与 127.0.0.1 的账号差异
    host = url.host
    if host in (None, "localhost", "::1"):
        host = "127.0.0.1"

    # 构造不带数据库名的连接URL
    server_url = url.set(database=None, host=host)
    server_engine = create_engine(server_url, pool_pre_ping=True, future=True)
    with server_engine.connect() as conn:
        conn.execute(text(
            f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))
        conn.commit()
        logger.info(f"确保数据库存在: {database}")
    server_engine.dispose()

# 创建SQLAlchemy引擎（强制使用MySQL）


def _create_engine_with_fallback():
    url = make_url(settings.database_url)
    try:
        if str(url.drivername).startswith("mysql"):
            # 规范化主机，避免 localhost 与 127.0.0.1 的账号差异
            host = url.host
            if host in (None, "localhost", "::1"):
                host = "127.0.0.1"

            # 确保数据库存在
            server_url = url.set(database=None, host=host)
            server_engine = create_engine(server_url, pool_pre_ping=True, future=True, connect_args={"connect_timeout": 3, "read_timeout": 5, "write_timeout": 5})
            try:
                with server_engine.connect() as conn:
                    conn.execute(text(
                        f"CREATE DATABASE IF NOT EXISTS `{url.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    ))
                    conn.commit()
                    logger.info(f"确保数据库存在: {url.database}")
            finally:
                server_engine.dispose()

            # 使用规范化后的 host 创建主引擎
            engine_url = url.set(host=host)
            engine = create_engine(
                engine_url,
                echo=settings.database_echo,
                pool_pre_ping=True,
                pool_recycle=3600,
                future=True,
                pool_size=10,
                max_overflow=20,
                connect_args={"connect_timeout": 3, "read_timeout": 5, "write_timeout": 5},
            )

            # 连接可用性检测；失败直接抛出
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        else:
            # 强制使用MySQL：若当前配置不是MySQL，直接报错以防回退或误用
            raise ValueError(f"必须使用MySQL作为数据库，当前配置为: {url.drivername}")
        logger.info(f"数据库引擎已创建: {engine.url}")
        return engine
    except Exception as e:
        logger.error(f"创建数据库引擎失败: {e}")
        raise


engine = _create_engine_with_fallback()

# Session工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

# 声明式基类
Base = declarative_base()




def get_db() -> Generator:
    """从 FastAPI 依赖中使用的 Session 生成器"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """上下文管理器方式的数据库会话（用于同步代码）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



def init_mysql_tables():
    """初始化数据库表结构（如果不存在则创建）。"""
    try:
        # 如果当前引擎是MySQL，再次保障数据库存在（短超时）
        cur_url = make_url(str(engine.url))
        if str(cur_url.drivername).startswith("mysql"):
            try:
                # 规范化主机，避免 localhost 与 127.0.0.1 的账号差异
                host = cur_url.host
                if host in (None, "localhost", "::1"):
                    host = "127.0.0.1"
                server_url = cur_url.set(database=None, host=host)
                server_engine = create_engine(server_url, pool_pre_ping=True, future=True, connect_args={"connect_timeout": 3, "read_timeout": 5, "write_timeout": 5})
                with server_engine.connect() as conn:
                    conn.execute(text(
                        f"CREATE DATABASE IF NOT EXISTS `{cur_url.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    ))
                    conn.commit()
                server_engine.dispose()
            except Exception as e:
                logger.warning(f"确保MySQL数据库存在失败: {e}")
        from app.models.db_models import Base as ModelBase  # 延迟导入避免循环
        ModelBase.metadata.create_all(bind=engine)
        # 轻量迁移：确保 users 表存在 phone_number 字段，删除 full_name 字段
        try:
            with engine.connect() as conn:
                # 检查列是否存在
                cur_url = make_url(str(engine.url))
                dbname = cur_url.database
                # 1. 检查 phone_number 字段
                phone_exists = conn.execute(text(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA=:db AND TABLE_NAME='users' AND COLUMN_NAME='phone_number'
                    """
                ), {"db": dbname}).scalar()
                if not phone_exists:
                    conn.execute(text("ALTER TABLE users ADD COLUMN phone_number VARCHAR(20) NULL"))
                    # 尝试添加唯一索引
                    try:
                        conn.execute(text("CREATE UNIQUE INDEX idx_users_phone ON users(phone_number)"))
                    except Exception:
                        pass
                # 2. 检查并删除 full_name 字段
                full_name_exists = conn.execute(text(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA=:db AND TABLE_NAME='users' AND COLUMN_NAME='full_name'
                    """
                ), {"db": dbname}).scalar()
                if full_name_exists:
                    conn.execute(text("ALTER TABLE users DROP COLUMN full_name"))
                    logger.info("已删除 users.full_name 字段")
                conn.commit()
        except Exception as e:
            logger.warning(f"轻量迁移users表失败或已存在: {e}")
        logger.info("数据库表结构已初始化")
    except Exception as e:
        logger.error(f"初始化数据库表结构失败: {e}")
        raise