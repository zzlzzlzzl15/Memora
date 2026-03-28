from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
import json
from uuid import UUID

from app.models.document import (
    DocumentCreate, DocumentUpdate, Document, SearchQuery, SearchResponse, DocumentType, DocumentListResponse
)
from app.models.document import SearchAnswerResponse
from app.models.llm import TextSummarizeRequest
from app.services.document_service import get_document_service
from app.services.document_processor import get_document_processor
from app.core.security import get_current_active_user
from config.settings import settings
from app.core.logging import get_request_logger
from app.services.llm_service import get_llm_service

router = APIRouter(prefix="/documents", tags=["文档管理"])

@router.post("/upload", response_model=Document, summary="上传文档")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    tags: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """上传文档文件"""
    # 开始日志
    req_logger.info(f"Documents.upload: start title='{title}' filename='{file.filename}' user_id='{current_user['user_id']}'")
    try:
        # 验证文件
        processor = get_document_processor()
        
        if not processor.validate_file_type(file.filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件类型。支持的类型: {', '.join(settings.allowed_file_types)}"
            )
        
        # 读取文件内容
        file_content = await file.read()
        req_logger.info(f"Documents.upload: file read bytes={len(file_content)}")
        
        if not processor.validate_file_size(len(file_content)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件大小超过限制。最大允许: {settings.max_file_size / 1024 / 1024:.1f}MB"
            )
        
        # 解析可选参数
        tags_list = json.loads(tags) if tags else []
        metadata_dict = json.loads(metadata) if metadata else {}
        
        # 检测文件类型
        file_type = processor.detect_file_type(file.filename)
        req_logger.info(f"Documents.upload: detected type={file_type}")
        
        # 创建文档
        document_create = DocumentCreate(
            title=title,
            file_type=file_type,
            tags=tags_list,
            metadata=metadata_dict
        )
        
        document_service = get_document_service()
        document = await document_service.create_document(
            document_create=document_create,
            user_id=current_user["user_id"],
            file_content=file_content,
            filename=file.filename
        )
        req_logger.info(f"Documents.upload: success document_id='{document.document_id}'")
        return document
    except HTTPException:
        # 已有统一异常抛出
        req_logger.info("Documents.upload: http_exception")
        raise
    except json.JSONDecodeError:
        req_logger.error("Documents.upload: json_decode_error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="标签或元数据格式错误，请使用有效的JSON格式"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传文档失败: {str(e)}"
        )

@router.post("/create", response_model=Document, summary="创建文本文档")
async def create_text_document(
    document_create: DocumentCreate,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """创建纯文本文档"""
    req_logger.info(f"Documents.create: start title='{document_create.title}' user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        document = await document_service.create_document(
            document_create=document_create,
            user_id=current_user["user_id"]
        )
        req_logger.info(f"Documents.create: success document_id='{document.document_id}'")
        return document
    except Exception as e:
        req_logger.exception(f"Documents.create: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建文档失败: {str(e)}"
        )

@router.get("/recent", response_model=List[Document], summary="获取最近一周的文档")
async def list_recent_documents(
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """获取当前用户最近一周内添加的文档列表"""
    req_logger.info(f"Documents.recent: start user_id='{current_user['user_id']}'")
    try:
        from app.core.sql import get_db
        from sqlalchemy import and_, or_
        from app.models.db_models import DocumentORM
        from datetime import datetime, timedelta
        import json
        
        db = next(get_db())
        
        # 计算一周前的时间（使用本地时间和UTC时间两种方式，确保兼容性）
        one_week_ago_utc = datetime.utcnow() - timedelta(days=7)
        one_week_ago_local = datetime.now() - timedelta(days=7)
        
        req_logger.info(f"Documents.recent: one_week_ago_utc={one_week_ago_utc}, one_week_ago_local={one_week_ago_local}")
        
        # 查询最近一周的文档，按创建时间倒序（使用OR条件兼容不同时区）
        documents_orm = db.query(DocumentORM).filter(
            and_(
                DocumentORM.user_id == current_user["user_id"],
                DocumentORM.is_deleted == False,
                or_(
                    DocumentORM.created_at >= one_week_ago_utc,
                    DocumentORM.created_at >= one_week_ago_local
                )
            )
        ).order_by(DocumentORM.created_at.desc()).all()
        
        req_logger.info(f"Documents.recent: found {len(documents_orm)} documents")
        
        # 转换为Document模型
        documents = []
        for doc_orm in documents_orm:
            # 解析JSON字段
            tags = json.loads(doc_orm.tags) if doc_orm.tags else []
            metadata = json.loads(doc_orm.doc_metadata) if doc_orm.doc_metadata else {}
            
            doc = Document(
                document_id=doc_orm.doc_id,
                user_id=doc_orm.user_id,
                title=doc_orm.title,
                content=doc_orm.content,
                file_type=doc_orm.doc_type,
                tags=tags,
                metadata=metadata,
                file_size=doc_orm.file_size,
                status=doc_orm.status,
                created_at=doc_orm.created_at,
                updated_at=doc_orm.updated_at
            )
            documents.append(doc)
        
        req_logger.info(f"Documents.recent: success count={len(documents)}")
        return documents
    except Exception as e:
        req_logger.exception(f"Documents.recent: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取最近文档失败: {str(e)}"
        )

@router.get("/", response_model=DocumentListResponse, summary="获取用户文档列表")
async def list_documents(
    skip: int = Query(0, ge=0, description="跳过的文档数量"),
    limit: int = Query(20, ge=1, le=100, description="返回的文档数量"),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """获取当前用户的文档列表（包含总数统计）"""
    req_logger.info(f"Documents.list: start skip={skip} limit={limit} user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        
        # 使用优化的方法：分别获取分页文档和总数
        documents = await document_service.list_user_documents(
            user_id=current_user["user_id"],
            skip=skip,
            limit=limit
        )
        
        # 使用新的计数方法（更高效）
        total = document_service.store.count_user_documents(current_user["user_id"])
        
        req_logger.info(f"Documents.list: success count={len(documents)} total={total}")
        
        return DocumentListResponse(
            documents=documents,
            total=total,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        req_logger.exception(f"Documents.list: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档列表失败: {str(e)}"
        )

 

@router.get("/{document_id:uuid}", response_model=Document, summary="获取文档详情")
async def get_document(
    document_id: UUID,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """获取指定文档的详细信息"""
    req_logger.info(f"Documents.get: start document_id='{document_id}' user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        document = await document_service.get_document(
            document_id=str(document_id),
            user_id=current_user["user_id"]
        )
        
        if not document:
            req_logger.info("Documents.get: not_found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在或无权访问"
            )
        
        return document
    except HTTPException:
        req_logger.info("Documents.get: http_exception")
        raise
    except Exception as e:
        req_logger.exception(f"Documents.get: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档失败: {str(e)}"
        )

@router.put("/{document_id:uuid}", response_model=Document, summary="更新文档")
async def update_document(
    document_id: UUID,
    document_update: DocumentUpdate,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """更新文档信息"""
    req_logger.info(f"Documents.update: start document_id='{document_id}' user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        document = await document_service.update_document(
            document_id=str(document_id),
            user_id=current_user["user_id"],
            document_update=document_update
        )
        
        if not document:
            req_logger.info("Documents.update: not_found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在或无权访问"
            )
        
        return document
    except HTTPException:
        req_logger.info("Documents.update: http_exception")
        raise
    except Exception as e:
        req_logger.exception(f"Documents.update: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新文档失败: {str(e)}"
        )

@router.delete("/{document_id:uuid}", summary="删除文档")
async def delete_document(
    document_id: UUID,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """删除指定文档（改为软删除，移入回收站）"""
    req_logger.info(f"Documents.delete: start document_id='{document_id}' user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        success = await document_service.soft_delete_document(
            document_id=str(document_id),
            user_id=current_user["user_id"]
        )
        
        if not success:
            req_logger.info("Documents.delete: not_found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在或无权访问"
            )
        
        return {"message": "文档已移至回收站"}
    except HTTPException:
        req_logger.info("Documents.delete: http_exception")
        raise
    except Exception as e:
        req_logger.exception(f"Documents.delete: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文档失败: {str(e)}"
        )

@router.post("/search", response_model=SearchResponse, summary="搜索文档")
async def search_documents(
    search_query: SearchQuery,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """在用户的文档中搜索相关内容"""
    req_logger.info(f"Documents.search: start query_len={len(search_query.query)} user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        search_response = await document_service.search_documents(
            search_query=search_query,
            user_id=current_user["user_id"]
        )
        req_logger.info(f"Documents.search: success results={len(search_response.results) if hasattr(search_response,'results') else 'n/a'}")
        return search_response
    except Exception as e:
        req_logger.exception(f"Documents.search: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
        )

@router.get("/search/quick", response_model=SearchResponse, summary="快速搜索")
async def quick_search(
    q: str = Query(..., min_length=1, max_length=500, description="搜索查询"),
    limit: int = Query(settings.qdrant_default_limit, ge=1, le=settings.qdrant_default_limit, description="返回结果数量"),
    score_threshold: float = Query(0.7, ge=0.0, le=1.0, description="相似度阈值"),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """快速搜索接口（GET方式）"""
    req_logger.info(f"Documents.quick_search: start q_len={len(q)} limit={limit} threshold={score_threshold} user_id='{current_user['user_id']}'")
    try:
        search_query = SearchQuery(
            query=q,
            limit=limit,
            score_threshold=score_threshold
        )
        document_service = get_document_service()
        search_response = await document_service.search_documents(
            search_query=search_query,
            user_id=current_user["user_id"]
        )
        req_logger.info(f"Documents.quick_search: success results={len(search_response.results) if hasattr(search_response,'results') else 'n/a'}")
        return search_response
    except Exception as e:
        req_logger.exception(f"Documents.quick_search: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
        )

@router.post("/search/answer", response_model=SearchAnswerResponse, summary="搜索并生成整理答案")
async def search_with_answer(
    search_query: SearchQuery,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """在用户文档中搜索，并使用LLM进行知识整理输出"""
    req_logger.info(f"Documents.search_answer: start query_len={len(search_query.query)} user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        search_response = await document_service.search_documents(
            search_query=search_query,
            user_id=current_user["user_id"]
        )
        llm_service = get_llm_service()
        answer = await llm_service.summarize_results(
            query=search_query.query,
            results=search_response.results
        )
        resp = SearchAnswerResponse(
            query=search_query.query,
            answer=answer,
            results=search_response.results,
            total=search_response.total,
            took=search_response.took
        )
        req_logger.info(f"Documents.search_answer: success results={len(resp.results)}")
        return resp
    except Exception as e:
        req_logger.exception(f"Documents.search_answer: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索并整理失败: {str(e)}"
        )

@router.post("/search/answer/stream", summary="搜索并流式生成整理答案")
async def search_with_answer_stream(
    search_query: SearchQuery,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """在用户文档中搜索，并以SSE流式推送LLM整理输出。
    事件说明：
    - event: sources  data: [{ title, score, content }...] 首次推送检索来源，用于前端展示
    - event: delta    data: "文本片段"  持续推送模型生成的增量文本
    - event: done     data: { total, took }  最终结束事件，包含统计信息
    """
    req_logger.info(f"Documents.search_answer_stream: start query_len={len(search_query.query)} user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        search_response = await document_service.search_documents(
            search_query=search_query,
            user_id=current_user["user_id"]
        )
        llm_service = get_llm_service()

        async def event_generator():
            try:
                # 先推送来源（最多10条，避免过长）
                limited = (search_response.results or [])[:10]
                sources_payload = [
                    {
                        "title": getattr(r, "title", "未命名"),
                        "score": getattr(r, "score", 0.0),
                        "content": (getattr(r, "content", "") or "")[:500],
                    }
                    for r in limited
                ]
                yield f"event: sources\ndata: {json.dumps(sources_payload, ensure_ascii=False)}\n\n"

                # 推送增量文本
                async for delta in llm_service.summarize_results_stream(
                    query=search_query.query,
                    results=search_response.results
                ):
                    # 以JSON对象编码，明确字段，严格保留换行与空行结构
                    payload = {"text": delta}
                    yield f"event: delta\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

                # 结束事件
                meta = {"total": search_response.total, "took": search_response.took}
                yield f"event: done\ndata: {json.dumps(meta, ensure_ascii=False)}\n\n"
            except Exception as stream_err:
                # 流式错误，用 error 事件通知前端
                err_payload = {"message": str(stream_err)}
                yield f"event: error\ndata: {json.dumps(err_payload, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        req_logger.exception(f"Documents.search_answer_stream: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索并整理失败: {str(e)}"
        )
@router.get("/deleted", response_model=List[Document], summary="获取回收站文档列表")
async def list_deleted_documents(
    skip: int = Query(0, ge=0, description="跳过的文档数量"),
    limit: int = Query(20, ge=1, le=100, description="返回的文档数量"),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    req_logger.info(f"Documents.deleted.list: start skip={skip} limit={limit} user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        documents = await document_service.list_deleted_documents(
            user_id=current_user["user_id"],
            skip=skip,
            limit=limit
        )
        req_logger.info(f"Documents.deleted.list: success count={len(documents)}")
        return documents
    except Exception as e:
        req_logger.exception(f"Documents.deleted.list: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取回收站列表失败: {str(e)}"
        )

@router.post("/{document_id:uuid}/restore", response_model=Document, summary="从回收站恢复文档")
async def restore_document(
    document_id: UUID,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    req_logger.info(f"Documents.restore: start document_id='{document_id}' user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        document = await document_service.restore_document(
            document_id=str(document_id),
            user_id=current_user["user_id"]
        )
        if not document:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文档无法恢复（可能已超过30天或状态异常）"
            )
        return document
    except HTTPException:
        req_logger.info("Documents.restore: http_exception")
        raise
    except Exception as e:
        req_logger.exception(f"Documents.restore: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"恢复文档失败: {str(e)}"
        )

@router.post("/{document_id:uuid}/purge", summary="彻底删除文档")
async def purge_document(
    document_id: UUID,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    req_logger.info(f"Documents.purge: start document_id='{document_id}' user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        success = await document_service.purge_document(
            document_id=str(document_id),
            user_id=current_user["user_id"]
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在或无权访问"
            )
        return {"message": "文档已彻底删除"}
    except HTTPException:
        req_logger.info("Documents.purge: http_exception")
        raise
    except Exception as e:
        req_logger.exception(f"Documents.purge: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"彻底删除失败: {str(e)}"
        )
@router.post("/create/auto_title", response_model=Document, summary="根据文本自动生成标题并保存文档")
async def create_document_auto_title(
    req: TextSummarizeRequest,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """根据提供的文本自动生成标题并保存为知识文档。
    - 输入使用长文本整理的请求体字段(text, 可选title, source_url)。
    - 若未提供title，则调用LLM生成简洁标题。
    - 文件类型固定为markdown，便于在前端查看。
    """
    req_logger.info(f"Documents.create_auto_title: start user_id='{current_user['user_id']}' text_len='{len(req.text)}'")
    try:
        llm = get_llm_service()
        # 优先使用请求提供的标题，否则生成
        title = (req.title or '').strip()
        if not title:
            title = await llm.generate_title(req.text)

        document_service = get_document_service()
        create = DocumentCreate(
            title=title,
            content=req.text,
            file_type=DocumentType.MARKDOWN,
            tags=[],
            metadata={
                "source_url": req.source_url,
                "generated_by": "organize_summary",
            }
        )
        document = await document_service.create_document(
            document_create=create,
            user_id=current_user["user_id"]
        )
        req_logger.info(f"Documents.create_auto_title: success document_id='{document.document_id}'")
        return document
    except Exception as e:
        req_logger.exception(f"Documents.create_auto_title: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"自动生成标题保存失败: {str(e)}"
        )