"""
使用统计API - 提供用户使用情况的统计数据
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict
from datetime import datetime, timedelta
from loguru import logger
from app.core.security import get_current_active_user
from app.core.sql import get_db
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract
from app.models.db_models import DocumentORM, ConversationMessageORM, ConversationSessionORM

router = APIRouter(prefix="/stats", tags=["statistics"])


@router.get("/usage")
async def get_usage_stats(
    month: str = Query(..., description="月份，格式: YYYY-MM"),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Dict[str, int]]:
    """
    获取用户指定月份的使用统计数据
    
    返回格式:
    {
        "2025-11-01": {
            "queries": 5,
            "added": 2,
            "deleted": 1
        },
        "2025-11-02": {
            "queries": 3,
            "added": 1,
            "deleted": 0
        },
        ...
    }
    """
    user_id = current_user["user_id"]
    
    try:
        # 解析月份
        year, month_num = map(int, month.split('-'))
        logger.info(f"Stats.usage: start user_id='{user_id}' month='{month}'")
        
        # 计算月份的起止日期
        start_date = datetime(year, month_num, 1)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month_num + 1, 1)
        
        # 初始化结果字典
        stats = {}
        
        # 统计每天的文档添加数量
        # 按日期分组统计上传的文档数量
        added_docs = db.query(
            func.date(DocumentORM.created_at).label('date'),
            func.count(DocumentORM.doc_id).label('count')
        ).filter(
            and_(
                DocumentORM.user_id == user_id,
                DocumentORM.created_at >= start_date,
                DocumentORM.created_at < end_date,
                DocumentORM.is_deleted == False
            )
        ).group_by(
            func.date(DocumentORM.created_at)
        ).all()
        
        # 统计每天的文档删除数量
        # 按删除日期分组统计
        deleted_docs = db.query(
            func.date(DocumentORM.deleted_at).label('date'),
            func.count(DocumentORM.doc_id).label('count')
        ).filter(
            and_(
                DocumentORM.user_id == user_id,
                DocumentORM.deleted_at >= start_date,
                DocumentORM.deleted_at < end_date,
                DocumentORM.is_deleted == True
            )
        ).group_by(
            func.date(DocumentORM.deleted_at)
        ).all()
        
        # 统计每天的查询次数
        # 按日期分组统计聊天记录（每次对话算一次查询）
        # 需要通过session关联来过滤user_id
        queries = db.query(
            func.date(ConversationMessageORM.created_at).label('date'),
            func.count(ConversationMessageORM.message_id).label('count')
        ).join(
            ConversationSessionORM,
            ConversationMessageORM.session_id == ConversationSessionORM.session_id
        ).filter(
            and_(
                ConversationSessionORM.user_id == user_id,
                ConversationMessageORM.created_at >= start_date,
                ConversationMessageORM.created_at < end_date,
                ConversationMessageORM.role == 'user'  # 只统计用户发送的消息
            )
        ).group_by(
            func.date(ConversationMessageORM.created_at)
        ).all()
        
        # 合并统计数据
        for date_obj, count in added_docs:
            date_str = date_obj.strftime('%Y-%m-%d')
            if date_str not in stats:
                stats[date_str] = {"queries": 0, "added": 0, "deleted": 0}
            stats[date_str]["added"] = count
        
        for date_obj, count in deleted_docs:
            date_str = date_obj.strftime('%Y-%m-%d')
            if date_str not in stats:
                stats[date_str] = {"queries": 0, "added": 0, "deleted": 0}
            stats[date_str]["deleted"] = count
        
        for date_obj, count in queries:
            date_str = date_obj.strftime('%Y-%m-%d')
            if date_str not in stats:
                stats[date_str] = {"queries": 0, "added": 0, "deleted": 0}
            stats[date_str]["queries"] = count
        
        logger.info(f"Stats.usage: success days_with_activity={len(stats)}")
        return stats
        
    except ValueError as e:
        logger.error(f"Stats.usage: invalid month format month='{month}' error={e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="月份格式错误，应为 YYYY-MM"
        )
    except Exception as e:
        logger.error(f"Stats.usage: error user_id='{user_id}' error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取统计数据失败"
        )
