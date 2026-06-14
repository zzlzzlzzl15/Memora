from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse, FileResponse
from typing import List, Optional
import json
import os
from pathlib import Path
from uuid import UUID
from io import BytesIO

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

@router.post("/batch_upload", summary="批量上传文档")
async def batch_upload_documents(
    files: List[UploadFile] = File(..., description="批量上传的文件列表"),
    tags: Optional[str] = Form(None, description="公共标签（JSON数组字符串）"),
    metadata: Optional[str] = Form(None, description="公共元数据（JSON对象字符串）"),
    max_concurrent: Optional[int] = Form(None, description="最大并发处理数，默认3"),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """批量上传文档

    支持同时上传多个文件，后端使用 Semaphore 控制并发处理数（默认3）。
    每个文件独立走完整的解析→分块→向量化入库流程。

    返回：
    - total: 总文件数
    - successful: 成功数
    - failed: 失败数
    - results: 每个文件的处理结果详情
    """
    req_logger.info(
        f"Documents.batch_upload: start files={len(files)} user_id='{current_user['user_id']}'"
    )
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未上传任何文件")

    if len(files) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="单次批量上传最多支持50个文件"
        )

    try:
        tags_list = json.loads(tags) if tags else []
        metadata_dict = json.loads(metadata) if metadata else {}
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tags或metadata格式错误，请使用有效的JSON格式"
        )

    # 读取所有文件内容（先在IO层读完，避免后续异步并发中重复读取导致错误）
    file_tuples = []
    processor = get_document_processor()
    for uf in files:
        try:
            content = await uf.read()
            # 用原始文件名（去掉路径）作为 title
            raw_title = Path(uf.filename).stem if uf.filename else "未命名文档"
            file_tuples.append((content, uf.filename or "unknown", raw_title))
        except Exception as e:
            req_logger.warning(f"读取文件失败 {uf.filename}: {e}")
            file_tuples.append((b"", uf.filename or "unknown", uf.filename or "未命名"))

    try:
        document_service = get_document_service()
        result = await document_service.batch_upload_documents(
            files=file_tuples,
            user_id=current_user["user_id"],
            tags=tags_list,
            metadata=metadata_dict,
            max_concurrent=max_concurrent,
        )
        req_logger.info(
            f"Documents.batch_upload: done total={result['total']} "
            f"ok={result['successful']} fail={result['failed']}"
        )
        return result
    except Exception as e:
        req_logger.exception(f"Documents.batch_upload: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量上传失败: {str(e)}"
        )

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

@router.get("/images/{user_id}/{filename}", summary="获取文档图片")
async def get_document_image(
    user_id: str,
    filename: str,
    size: Optional[str] = Query(None, description="缩略图尺寸: thumbnail"),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """
    获取文档中的图片文件
    
    安全控制：
    - 只允许访问 uploads/{user_id}/images/ 目录
    - 必须是文档所属用户本人
    - 支持 ?size=thumbnail 返回缩略图
    """
    # 安全检查：只能访问自己的图片
    if current_user["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该用户的图片"
        )

    # 构建安全路径
    images_dir = Path(settings.upload_dir) / user_id / "images"
    image_path = (images_dir / filename).resolve()

    # 路径遍历攻击防护
    if not str(image_path).startswith(str(images_dir.resolve())):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="非法路径"
        )

    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="图片不存在"
        )

    try:
        # 生成缩略图
        if size == "thumbnail":
            try:
                from PIL import Image
                img = Image.open(str(image_path))
                img.thumbnail((200, 200))
                buf = BytesIO()
                # 保留原始格式，默认 JPEG
                fmt = img.format or "JPEG"
                if fmt == "PNG":
                    img.save(buf, format="PNG", optimize=True)
                    media_type = "image/png"
                else:
                    img.save(buf, format="JPEG", optimize=True, quality=85)
                    media_type = "image/jpeg"
                buf.seek(0)
                return StreamingResponse(buf, media_type=media_type)
            except ImportError:
                # Pillow 不可用时返回原图
                pass
            except Exception as e:
                req_logger.warning(f"缩略图生成失败: {e}")

        # 返回原图
        suffix = image_path.suffix.lower()
        media_type_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp",
            ".gif": "image/gif",
        }
        media_type = media_type_map.get(suffix, "application/octet-stream")
        return FileResponse(str(image_path), media_type=media_type)

    except HTTPException:
        raise
    except Exception as e:
        req_logger.exception(f"获取图片失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取图片失败: {str(e)}"
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
            
            # 兼容旧状态映射
            status_str = doc_orm.status or 'pending'
            status_map = {'uploading': 'pending', 'processing': 'pending', 'indexed': 'completed'}
            mapped_status = status_map.get(status_str, status_str)
            
            doc = Document(
                document_id=doc_orm.doc_id,
                user_id=doc_orm.user_id,
                title=doc_orm.title,
                content=doc_orm.content,
                file_type=doc_orm.doc_type,
                tags=tags,
                metadata=metadata,
                file_size=doc_orm.file_size,
                status=mapped_status,
                progress=getattr(doc_orm, 'progress', 0) or 0,
                error_message=getattr(doc_orm, 'error_message', None),
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
            results=search_response.results,
            fused_context=getattr(search_response, 'fused_context', None)
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
                        "content_type": getattr(r, "content_type", "text") or "text",
                        "image_url": getattr(r, "image_url", None),
                        "thumbnail_url": getattr(r, "thumbnail_url", None),
                    }
                    for r in limited
                ]
                yield f"event: sources\ndata: {json.dumps(sources_payload, ensure_ascii=False)}\n\n"

                # 推送增量文本（当检索结果包含图片且 VLM 可用时，自动使用 VLM 多模态整理）
                async for delta in llm_service.summarize_results_vlm_stream(
                    query=search_query.query,
                    results=search_response.results,
                    fused_context=getattr(search_response, 'fused_context', None)
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
@router.get("/{document_id:uuid}/status", summary="获取文档处理状态")
async def get_document_status(
    document_id: UUID,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """获取文档处理状态和进度（供前端轮询）"""
    req_logger.info(f"Documents.status: document_id='{document_id}' user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        document = await document_service.get_document(
            document_id=str(document_id),
            user_id=current_user["user_id"]
        )
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在或无权访问"
            )
        return {
            "document_id": str(document_id),
            "status": document.status,
            "progress": document.progress,
            "error_message": document.error_message,
        }
    except HTTPException:
        raise
    except Exception as e:
        req_logger.exception(f"Documents.status: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档状态失败: {str(e)}"
        )

@router.post("/{document_id:uuid}/reprocess", response_model=Document, summary="重新处理文档")
async def reprocess_document(
    document_id: UUID,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """重新处理文档（用于配置变更后重建索引或处理失败后重试）"""
    req_logger.info(f"Documents.reprocess: document_id='{document_id}' user_id='{current_user['user_id']}'")
    try:
        document_service = get_document_service()
        # 获取文档
        document = document_service.store.get_document(str(document_id))
        if not document or document.user_id != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在或无权访问"
            )

        from app.models.document import DocumentStatus
        # 只允许对 FAILED 或 COMPLETED/INDEXED 状态的文档重新处理
        if document.status not in (
            DocumentStatus.FAILED, DocumentStatus.COMPLETED, DocumentStatus.INDEXED
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"当前状态 {document.status} 不支持重新处理"
            )

        # 删除旧向量
        await document_service.vector_store.delete_document_vectors(
            str(document_id), current_user["user_id"]
        )

        # 重置状态并重新处理
        document_service.store.update_document(str(document_id), {
            "status": DocumentStatus.PENDING,
            "progress": 0,
            "error_message": None,
            "vector_id": None,
        })
        updated_doc = document_service.store.get_document(str(document_id))
        if updated_doc:
            document_service._persist_metadata(updated_doc)
            document_service._sync_to_database(updated_doc)
            await document_service._process_document_vectors(updated_doc)

        refreshed = document_service.store.get_document(str(document_id))
        if refreshed:
            return document_service._convert_to_document(refreshed)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重新处理失败"
        )
    except HTTPException:
        raise
    except Exception as e:
        req_logger.exception(f"Documents.reprocess: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重新处理失败: {str(e)}"
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


# ─── 知识图谱 API ────────────────────────────────────────────────

@router.get("/knowledge-graph/stats", summary="获取知识图谱统计")
async def get_knowledge_graph_stats(
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """获取当前用户的知识图谱统计信息"""
    if not settings.neo4j_enabled:
        raise HTTPException(status_code=400, detail="知识图谱功能未启用")
    try:
        from app.services.knowledge_graph import get_knowledge_graph_service
        kg_service = get_knowledge_graph_service()
        if not kg_service.available:
            raise HTTPException(status_code=503, detail="知识图谱服务不可用")
        stats = kg_service.get_stats(current_user["user_id"])
        return {"stats": stats}
    except HTTPException:
        raise
    except Exception as e:
        req_logger.exception(f"KG.stats: error {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"获取图谱统计失败: {str(e)}")


@router.get("/knowledge-graph/search", summary="搜索知识图谱实体")
async def search_knowledge_graph_entities(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(10, ge=1, le=50, description="返回结果数"),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """搜索知识图谱中的实体"""
    if not settings.neo4j_enabled:
        raise HTTPException(status_code=400, detail="知识图谱功能未启用")
    try:
        from app.services.knowledge_graph import get_knowledge_graph_service
        kg_service = get_knowledge_graph_service()
        if not kg_service.available:
            raise HTTPException(status_code=503, detail="知识图谱服务不可用")
        entities = kg_service.search_entities(keyword, current_user["user_id"], limit)
        return {"entities": entities}
    except HTTPException:
        raise
    except Exception as e:
        req_logger.exception(f"KG.search: error {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"搜索图谱实体失败: {str(e)}")


@router.get("/knowledge-graph/entity/{entity_name}", summary="获取实体及其关系")
async def get_entity_relations(
    entity_name: str,
    depth: int = Query(2, ge=1, le=3, description="关系遍历深度"),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """获取指定实体及其 N 度关系"""
    if not settings.neo4j_enabled:
        raise HTTPException(status_code=400, detail="知识图谱功能未启用")
    try:
        from app.services.knowledge_graph import get_knowledge_graph_service
        kg_service = get_knowledge_graph_service()
        if not kg_service.available:
            raise HTTPException(status_code=503, detail="知识图谱服务不可用")
        result = kg_service.get_entity_with_relations(
            entity_name, current_user["user_id"], depth
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        req_logger.exception(f"KG.entity: error {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"获取实体关系失败: {str(e)}")


# ─── 3.12 文档智能摘要 API ───────────────────────────────────────────────────

@router.post("/{document_id:uuid}/summarize", summary="生成文档智能摘要")
async def generate_document_summary(
    document_id: UUID,
    force: bool = Query(False, description="是否强制重新生成（忽略已有缓存）"),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """触发 LLM 生成文档结构化摘要并持久化。

    - 首次调用时生成并缓存，后续命中缓存直接返回（无需再次调用 LLM）
    - 传入 ?force=true 可强制重新生成
    - 摘要字段：summary / key_points / keywords / entities
    """
    req_logger.info(
        f"Documents.summarize: doc={document_id} force={force} user={current_user['user_id']}"
    )
    try:
        document_service = get_document_service()
        summary = await document_service.generate_document_summary(
            document_id=str(document_id),
            user_id=current_user["user_id"],
            force=force,
        )
        if summary is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在或无权访问",
            )
        return {"document_id": str(document_id), "summary": summary}
    except HTTPException:
        raise
    except Exception as e:
        req_logger.exception(f"Documents.summarize: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成摘要失败: {str(e)}",
        )


@router.get("/{document_id:uuid}/summary", summary="获取文档摘要（缓存）")
async def get_document_summary(
    document_id: UUID,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """从内存/DB 快速读取已生成的摘要，不调用 LLM。

    若摘要尚未生成，返回 404；请先调用 POST /summarize 生成。
    """
    req_logger.info(
        f"Documents.get_summary: doc={document_id} user={current_user['user_id']}"
    )
    try:
        document_service = get_document_service()
        summary = document_service.get_document_summary_cached(
            document_id=str(document_id),
            user_id=current_user["user_id"],
        )
        if summary is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="摘要尚未生成，请先调用 POST /{document_id}/summarize",
            )
        return {"document_id": str(document_id), "summary": summary}
    except HTTPException:
        raise
    except Exception as e:
        req_logger.exception(f"Documents.get_summary: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取摘要失败: {str(e)}",
        )


# ─── 3.13 相关文档推荐 API ───────────────────────────────────────────────────

@router.get("/{document_id:uuid}/related", summary="获取相关文档推荐")
async def get_related_documents(
    document_id: UUID,
    limit: int = Query(5, ge=1, le=20, description="返回推荐数量上限"),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """基于向量相似度 + 标签 + 知识图谱三路推荐与当前文档相关的文档。

    返回列表每项字段：
    - document_id: 相关文档 ID
    - title: 标题
    - similarity: 相似度分（0-1）
    - reason: 推荐原因（语义相似 / 共享标签 / 共享实体）
    - file_type: 文件类型
    - created_at: 创建时间（ISO8601）
    """
    req_logger.info(
        f"Documents.related: doc={document_id} limit={limit} user={current_user['user_id']}"
    )
    try:
        document_service = get_document_service()
        related = await document_service.get_related_documents(
            document_id=str(document_id),
            user_id=current_user["user_id"],
            limit=limit,
        )
        return {"document_id": str(document_id), "related": related, "total": len(related)}
    except Exception as e:
        req_logger.exception(f"Documents.related: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取相关文档失败: {str(e)}",
        )


# ─── 3.14 文档导出 API ───────────────────────────────────────────────────

@router.get("/{document_id:uuid}/export", summary="导出文档")
async def export_document(
    document_id: UUID,
    fmt: str = Query("markdown", description="导出格式: markdown / html / json"),
    include_summary: bool = Query(True, description="是否包含 AI 摘要（如有）"),
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """导出文档为指定格式并直接下载。

    支持格式：
    - **markdown**：含元数据 frontmatter 的 Markdown 文件（.md）
    - **html**：带样式的完整 HTML 页面（.html）
    - **json**：包含所有字段的 JSON 对象（.json）

    ?include_summary=true 时自动将已有 AI 摘要嵌入导出内容。
    """
    req_logger.info(
        f"Documents.export: doc={document_id} fmt={fmt} include_summary={include_summary} "
        f"user={current_user['user_id']}"
    )
    try:
        document_service = get_document_service()
        document = await document_service.get_document(
            document_id=str(document_id),
            user_id=current_user["user_id"],
        )
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在或无权访问",
            )

        from app.services.document_export import get_export_service
        export_svc = get_export_service()
        content_bytes, filename, media_type = export_svc.export(
            document=document,
            fmt=fmt,
            include_summary=include_summary,
        )

        req_logger.info(
            f"Documents.export: success doc={document_id} fmt={fmt} "
            f"size={len(content_bytes)} filename='{filename}'"
        )

        return StreamingResponse(
            iter([content_bytes]),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename*=UTF-8\'\'{filename}',
                "Content-Length": str(len(content_bytes)),
            },
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        req_logger.exception(f"Documents.export: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出文档失败: {str(e)}",
        )