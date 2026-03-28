from typing import Optional, Dict, Any
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger
import sys
import os
from fastapi.exceptions import RequestValidationError

from config.settings import settings
from app.core.security import verify_token


def setup_logging() -> None:
    """Configure global logging sinks and formats.

    - Console sink with level from settings
    - Rotating file sink to settings.log_file
    """
    try:
        logger.remove()
    except Exception:
        # In case no sinks were present
        pass

    # Ensure logs directory exists
    try:
        log_dir = os.path.dirname(settings.log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    except Exception:
        # If unable to create directory, continue with console-only logging
        pass

    # Ensure llm logs directory exists
    try:
        llm_log_dir = os.path.dirname(settings.llm_log_file)
        if llm_log_dir:
            os.makedirs(llm_log_dir, exist_ok=True)
    except Exception:
        pass

    # Console sink (stdout)
    logger.add(
        sys.stdout,
        level=settings.log_level.upper(),
        colorize=True,
        enqueue=True,
        backtrace=True,
        diagnose=settings.debug,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {message}",
    )

    # File sink (rotating)
    logger.add(
        settings.log_file,
        level=settings.log_level.upper(),
        rotation="10 MB",
        retention="10 days",
        enqueue=True,
        backtrace=True,
        diagnose=settings.debug,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
            "{file.path}:{function}:{line} | {message}"
        ),
    )

    # LLM专用文件sink：仅记录带有 component="llm" 的日志
    logger.add(
        settings.llm_log_file,
        level=settings.log_level.upper(),
        rotation="10 MB",
        retention="10 days",
        enqueue=True,
        backtrace=True,
        diagnose=settings.debug,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
            "{message}"
        ),
        filter=lambda record: (record["extra"] or {}).get("component") == "llm",
    )
    # 写入一次初始化消息，确保文件创建
    try:
        logger.bind(component="llm").debug("LLM log initialized")
    except Exception:
        pass


async def logging_middleware(request: Request, call_next):
    """HTTP middleware that logs request and response details.

    - Logs method, path, client, headers summary, optional JSON body size
    - Extracts user info from Authorization header if present
    - Adds X-Request-ID header to response
    """
    request_id = str(uuid.uuid4())
    # 将 request_id 写入 request.state，便于路由依赖获取
    try:
        request.state.request_id = request_id
    except Exception:
        pass
    # 绑定 request_id 到 logger
    bind_logger = logger.bind(request_id=request_id)

    client_host = request.client.host if request.client else "-"
    method = request.method
    path = request.url.path
    query_string = request.url.query
    content_type = request.headers.get("content-type", "")
    content_length = request.headers.get("content-length", "")

    user_ctx: Dict[str, Any] = {"user_id": None, "username": None}
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = verify_token(token)
            user_ctx["user_id"] = payload.get("user_id")
            user_ctx["username"] = payload.get("sub")
        except Exception:
            # Ignore token errors here; dedicated handlers will respond appropriately
            pass

    # Attempt to capture small JSON bodies safely (Starlette caches request.body())
    # 移除在中间件中读取请求体的逻辑，避免与路由内读取请求体产生竞争
    start_time = time.perf_counter()
    bind_logger.info(
        (
            f"REQUEST start | {method} {path}" + (f"?{query_string}" if query_string else "") +
            f" | client={client_host} | ct={content_type or '-'} | cl={content_length or '-'} | "
            f"user_id={user_ctx['user_id'] or '-'} | username={user_ctx['username'] or '-'}"
        )
    )

    try:
        handler_start = time.perf_counter()
        response = await call_next(request)
        handler_ms = int((time.perf_counter() - handler_start) * 1000)
        bind_logger.info(f"REQUEST handler | {method} {path} | took={handler_ms}ms")
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        bind_logger.exception(
            f"REQUEST error | {method} {path} | took={elapsed_ms}ms | error={type(e).__name__}: {e}"
        )
        # Re-raise to let exception handlers handle it
        raise

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    status = getattr(response, "status_code", "-")
    resp_len = response.headers.get("content-length", "-")

    bind_logger.info(
        f"RESPONSE end | {method} {path} | status={status} | took={elapsed_ms}ms | length={resp_len}"
    )

    # Propagate request id
    try:
        response.headers["X-Request-ID"] = request_id
    except Exception:
        pass
    return response


def init_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers to ensure errors are logged uniformly."""

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(getattr(request, "state", None), "request_id", None) or str(uuid.uuid4())
        logger.bind(request_id=request_id).exception(
            f"UNHANDLED exception | {request.method} {request.url.path} | error={type(exc).__name__}: {exc}"
        )
        return JSONResponse(status_code=500, content={"detail": "内部服务器错误"})

    from fastapi import HTTPException
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(getattr(request, "state", None), "request_id", None) or str(uuid.uuid4())
        logger.bind(request_id=request_id).error(
            f"HTTPException | {request.method} {request.url.path} | status={exc.status_code} | detail={exc.detail}"
        )
        headers = getattr(exc, "headers", None) or {}
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(getattr(request, "state", None), "request_id", None) or str(uuid.uuid4())
        try:
            errors = exc.errors()
            # 将errors转换为可 JSON 序列化的格式，处理 bytes 类型
            serializable_errors = []
            for error in errors:
                error_dict = dict(error)
                # 将 bytes 类型转换为字符串
                for key, value in error_dict.items():
                    if isinstance(value, bytes):
                        error_dict[key] = value.decode('utf-8', errors='replace')
                    elif isinstance(value, tuple):
                        error_dict[key] = list(value)
                serializable_errors.append(error_dict)
            errors = serializable_errors
        except Exception:
            errors = str(exc)
        logger.bind(request_id=request_id).error(
            f"RequestValidationError | {request.method} {request.url.path} | status=400 | errors={errors}"
        )
        return JSONResponse(status_code=400, content={"detail": errors})


def init_app_logging(app: FastAPI) -> None:
    """Initialize logging for the FastAPI app: sinks, middleware, handlers."""
    setup_logging()
    # Register middleware
    app.middleware("http")(logging_middleware)
    # Exception handlers
    init_exception_handlers(app)


def get_request_logger(request: Request):
    req_id = getattr(getattr(request, "state", None), "request_id", None)
    if req_id:
        return logger.bind(request_id=req_id)
    return logger