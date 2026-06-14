#!/usr/bin/env python3
"""
为已有文档重新构建知识图谱

使用方法:
    docker exec -it memora-app python rebuild_kg_for_existing_docs.py
"""

import asyncio
import sys
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, '/app')

async def rebuild_knowledge_graphs():
    """为所有已有文档重新构建知识图谱"""
    from app.services.document_service import get_document_service
    from app.core.sql import get_db
    from app.models.db_models import DocumentORM
    
    logger.info("=" * 60)
    logger.info("开始为已有文档重建知识图谱")
    logger.info("=" * 60)
    
    # 获取数据库会话
    db = next(get_db())
    
    # 查询所有未删除且状态为completed的文档
    documents = db.query(DocumentORM).filter(
        DocumentORM.is_deleted == False,
        DocumentORM.status.in_(['completed', 'indexed'])
    ).all()
    
    if not documents:
        logger.warning("没有找到需要处理的文档")
        return
    
    logger.info(f"找到 {len(documents)} 个文档需要处理\n")
    
    document_service = get_document_service()
    success_count = 0
    failed_count = 0
    
    for i, doc_orm in enumerate(documents, 1):
        try:
            logger.info(f"[{i}/{len(documents)}] 处理文档: {doc_orm.title}")
            logger.info(f"  doc_id: {doc_orm.doc_id}")
            
            # 从内存存储获取文档对象
            doc_in_memory = document_service.store.get_document(doc_orm.doc_id)
            
            if not doc_in_memory:
                logger.warning(f"  ⚠️ 文档不在内存中,跳过")
                failed_count += 1
                continue
            
            # 检查是否有内容
            if not doc_in_memory.content or len(doc_in_memory.content) < 100:
                logger.warning(f"  ⚠️ 文档内容不足,跳过")
                failed_count += 1
                continue
            
            # 对文档内容进行分块
            from app.services.document_processor import get_document_processor
            processor = get_document_processor()
            
            chunks = processor.chunk_text(
                text=doc_in_memory.content,
                doc_id=doc_orm.doc_id,
                chunk_size=512,
                chunk_overlap=50
            )
            
            if not chunks:
                logger.warning(f"  ⚠️ 分块失败,跳过")
                failed_count += 1
                continue
            
            logger.info(f"  📝 分块完成: {len(chunks)} 个chunks")
            
            # 触发知识图谱构建
            await document_service._build_knowledge_graph(doc_in_memory, chunks)
            
            logger.info(f"  ✅ 成功")
            success_count += 1
            
        except Exception as e:
            logger.error(f"  ❌ 失败: {e}")
            failed_count += 1
            import traceback
            logger.debug(traceback.format_exc())
        
        logger.info("")  # 空行分隔
    
    logger.info("=" * 60)
    logger.info(f"处理完成!")
    logger.info(f"  总计: {len(documents)}")
    logger.info(f"  成功: {success_count}")
    logger.info(f"  失败: {failed_count}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(rebuild_knowledge_graphs())
