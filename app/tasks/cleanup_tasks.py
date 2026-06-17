"""定时清理任务"""
import asyncio
from loguru import logger
from app.services.conversation_service import get_conversation_service


async def cleanup_expired_sessions_task():
    """定时清理过期会话的后台任务"""
    while True:
        try:
            # 每天凌晨 2 点执行清理（延迟到下次凌晨2点）
            now = asyncio.get_event_loop().time()
            # 计算到明天凌晨2点的秒数
            import datetime
            current_time = datetime.datetime.now()
            next_run = current_time.replace(hour=2, minute=0, second=0, microsecond=0)
            if current_time.hour >= 2:
                # 如果已经过了今天凌晨2点，则设置为明天凌晨2点
                next_run += datetime.timedelta(days=1)
            
            wait_seconds = (next_run - current_time).total_seconds()
            logger.info(f"下次清理过期会话的时间: {next_run}, 等待 {wait_seconds/3600:.2f} 小时")
            
            await asyncio.sleep(wait_seconds)
            
            # 执行清理
            logger.info("开始清理过期会话...")
            service = get_conversation_service()
            deleted_count = service.cleanup_expired_sessions()
            logger.info(f"清理过期会话完成，共删除 {deleted_count} 个会话")
            
        except Exception as e:
            logger.error(f"清理过期会话时发生错误: {e}")
            # 出错后等待1小时再试
            await asyncio.sleep(3600)
