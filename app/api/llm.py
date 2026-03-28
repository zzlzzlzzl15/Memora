from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
import json

from app.core.security import get_current_active_user
from app.core.logging import get_request_logger
from app.models.llm import TextSummarizeRequest
from app.services.llm_service import get_llm_service

router = APIRouter(prefix="/llm", tags=["LLM"])


@router.post("/summarize", summary="对长文本进行流式总结")
async def summarize_stream(
    req: TextSummarizeRequest,
    current_user: dict = Depends(get_current_active_user),
    req_logger = Depends(get_request_logger)
):
    """对任意长文本进行知识梳理与总结，并以SSE流式推送增量文本。
    事件说明：
    - event: delta  data: { text }    持续推送模型生成的增量文本
    - event: done   data: { ok: true } 最终结束事件
    """
    # 简单日志标记长度，避免日志过长
    text_len = len(req.text or "")
    req_logger.info(f"LLM.summarize_stream: start text_len={text_len} user_id='{current_user['user_id']}'")
    try:
        llm_service = get_llm_service()

        async def event_generator():
            try:
                async for delta in llm_service.summarize_text_stream(
                    text=req.text,
                    title=req.title,
                    source_url=req.source_url,
                ):
                    payload = {"text": delta}
                    yield f"event: delta\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                yield "event: done\ndata: {\"ok\": true}\n\n"
            except Exception as stream_err:
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
        req_logger.exception(f"LLM.summarize_stream: error {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"长文本总结失败: {str(e)}"
        )