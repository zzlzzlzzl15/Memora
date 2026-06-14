"""
LLM/Embedding/Rerank API 调用韧性工具

参照 RAG-Anything resilience.py 实现，提供：
- retry / async_retry 装饰器（指数退避 + jitter）
- CircuitBreaker（断路器，防止级联故障）
- with_fallback / async_with_fallback 辅助函数

适用场景：
  LLM API 调用、Embedding API 调用、Rerank API 调用
"""

from __future__ import annotations

import asyncio
import functools
import logging
import threading
import time
import random
from typing import Any, Callable, Optional, Sequence, Type, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# ──────────────────────────────────────────────────────────
# 默认可重试异常集合（网络/上游临时故障）
# ──────────────────────────────────────────────────────────
_DEFAULT_RETRYABLE: tuple[Type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)

try:
    import httpx
    _DEFAULT_RETRYABLE = _DEFAULT_RETRYABLE + (
        httpx.ConnectError,
        httpx.ReadTimeout,
        httpx.WriteTimeout,
        httpx.PoolTimeout,
        httpx.RemoteProtocolError,
    )
except ImportError:
    pass

try:
    import openai
    _DEFAULT_RETRYABLE = _DEFAULT_RETRYABLE + (
        openai.APIConnectionError,
        openai.APITimeoutError,
        openai.RateLimitError,
        openai.InternalServerError,
    )
except ImportError:
    pass


# ──────────────────────────────────────────────────────────
# 同步 retry 装饰器
# ──────────────────────────────────────────────────────────
def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Sequence[Type[BaseException]]] = None,
    on_retry: Optional[Callable[[BaseException, int, float], None]] = None,
) -> Callable[[F], F]:
    """同步函数重试装饰器（指数退避 + jitter）

    Args:
        max_attempts: 总尝试次数（含首次调用）
        base_delay: 初始重试间隔（秒）
        max_delay: 重试间隔上限（秒）
        exponential_base: 指数退避底数
        jitter: 是否添加随机抖动（0~50% 的当前 delay）
        retryable_exceptions: 触发重试的异常类型，默认为网络/API 临时故障
        on_retry: 每次重试前的回调 (exc, attempt, delay)

    Example::
        @retry(max_attempts=3, base_delay=1.0)
        def call_api():
            ...
    """
    if retryable_exceptions is None:
        retryable_exceptions = _DEFAULT_RETRYABLE

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except tuple(retryable_exceptions) as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        logger.error(
                            "%s 连续失败 %d 次: %s",
                            func.__qualname__, max_attempts, exc
                        )
                        raise
                    delay = min(
                        base_delay * (exponential_base ** (attempt - 1)),
                        max_delay,
                    )
                    if jitter:
                        delay *= 1.0 + random.uniform(0, 0.5)
                    if on_retry is not None:
                        on_retry(exc, attempt, delay)
                    logger.warning(
                        "%s 第 %d/%d 次失败 (%s)，%.1fs 后重试…",
                        func.__qualname__, attempt, max_attempts,
                        type(exc).__name__, delay,
                    )
                    time.sleep(delay)
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator


# ──────────────────────────────────────────────────────────
# 异步 async_retry 装饰器
# ──────────────────────────────────────────────────────────
def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Sequence[Type[BaseException]]] = None,
    on_retry: Optional[Callable[[BaseException, int, float], Any]] = None,
) -> Callable[[F], F]:
    """异步函数重试装饰器（async_retry），使用 asyncio.sleep 避免阻塞事件循环

    Args:
        同 retry()

    Example::
        @async_retry(max_attempts=3, base_delay=1.0)
        async def call_llm_api(messages):
            ...
    """
    if retryable_exceptions is None:
        retryable_exceptions = _DEFAULT_RETRYABLE

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except tuple(retryable_exceptions) as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        logger.error(
                            "%s 连续失败 %d 次: %s",
                            func.__qualname__, max_attempts, exc
                        )
                        raise
                    delay = min(
                        base_delay * (exponential_base ** (attempt - 1)),
                        max_delay,
                    )
                    if jitter:
                        delay *= 1.0 + random.uniform(0, 0.5)
                    if on_retry is not None:
                        result = on_retry(exc, attempt, delay)
                        if asyncio.iscoroutine(result):
                            await result
                    logger.warning(
                        "%s 第 %d/%d 次失败 (%s)，%.1fs 后重试…",
                        func.__qualname__, attempt, max_attempts,
                        type(exc).__name__, delay,
                    )
                    await asyncio.sleep(delay)
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator


# ──────────────────────────────────────────────────────────
# CircuitBreaker（断路器）
# ──────────────────────────────────────────────────────────
class CircuitBreaker:
    """防止级联故障的断路器

    状态机：
      closed（关闭，正常放行）→ open（打开，快速失败）→ half-open（半开，允许一次试探）

    Args:
        failure_threshold: 在 reset_timeout 时间窗口内的失败次数阈值，超过则打开断路器
        reset_timeout: 断路器打开后等待多少秒进入 half-open 状态
        name: 断路器名称（用于日志）
        failure_exceptions: 计入失败统计的异常类型，默认与 retry 保持一致
    """

    class CircuitBreakerOpen(Exception):
        """断路器打开时抛出"""
        pass

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        name: str = "default",
        failure_exceptions: Optional[Sequence[Type[BaseException]]] = None,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.name = name
        self._failure_exceptions: tuple[Type[BaseException], ...] = tuple(
            failure_exceptions or _DEFAULT_RETRYABLE
        )
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._state: str = "closed"
        self._lock = threading.Lock()
        self._trial_in_flight: bool = False

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == "open":
                if time.time() - self._last_failure_time >= self.reset_timeout:
                    self._state = "half-open"
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = "closed"
            self._trial_in_flight = False

    def record_failure(self) -> None:
        with self._lock:
            now = time.time()
            if self._state == "half-open":
                self._failure_count = self.failure_threshold
            else:
                if (
                    self._last_failure_time
                    and now - self._last_failure_time >= self.reset_timeout
                ):
                    self._failure_count = 0
                self._failure_count += 1
            self._last_failure_time = now
            if self._failure_count >= self.failure_threshold:
                self._state = "open"
                self._trial_in_flight = False
                logger.warning(
                    "断路器 '%s' 已打开（累计失败 %d 次）",
                    self.name, self._failure_count
                )

    def _acquire_permission(self) -> None:
        with self._lock:
            if self._state == "open":
                if time.time() - self._last_failure_time >= self.reset_timeout:
                    self._state = "half-open"
            if self._state == "open":
                raise self.CircuitBreakerOpen(
                    f"断路器 '{self.name}' 已打开，请求被拒绝"
                )
            if self._state == "half-open":
                if self._trial_in_flight:
                    raise self.CircuitBreakerOpen(
                        f"断路器 '{self.name}' 半开中，试探请求已在途"
                    )
                self._trial_in_flight = True

    def __call__(self, func: F) -> F:
        """用作同步函数装饰器"""
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self._acquire_permission()
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except tuple(self._failure_exceptions):
                self.record_failure()
                raise
            except Exception:
                with self._lock:
                    if self._state == "half-open":
                        self._trial_in_flight = False
                raise
        return wrapper  # type: ignore[return-value]

    def async_call(self, func: F) -> F:
        """用作异步函数装饰器"""
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            self._acquire_permission()
            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except tuple(self._failure_exceptions):
                self.record_failure()
                raise
            except Exception:
                with self._lock:
                    if self._state == "half-open":
                        self._trial_in_flight = False
                raise
        return wrapper  # type: ignore[return-value]


# ──────────────────────────────────────────────────────────
# with_fallback 辅助函数
# ──────────────────────────────────────────────────────────
async def async_with_fallback(
    primary_func: Callable[[], Any],
    fallback_func: Callable[[], Any],
    fallback_exceptions: Optional[Sequence[Type[BaseException]]] = None,
    label: str = "operation",
) -> Any:
    """异步调用 primary_func，失败时降级到 fallback_func

    Args:
        primary_func: 主调用（async callable）
        fallback_func: 降级调用（async callable）
        fallback_exceptions: 触发降级的异常类型（默认所有 Exception）
        label: 用于日志标识

    Example::
        result = await async_with_fallback(
            primary_func=lambda: call_llm_api(messages),
            fallback_func=lambda: local_summarize(results),
            label="LLM summarize"
        )
    """
    exc_types = tuple(fallback_exceptions) if fallback_exceptions else (Exception,)
    try:
        return await primary_func()
    except exc_types as e:
        logger.warning("'%s' 主调用失败 (%s)，启用降级", label, type(e).__name__)
        return await fallback_func()


def with_fallback(
    primary_func: Callable[[], Any],
    fallback_func: Callable[[], Any],
    fallback_exceptions: Optional[Sequence[Type[BaseException]]] = None,
    label: str = "operation",
) -> Any:
    """同步版 with_fallback"""
    exc_types = tuple(fallback_exceptions) if fallback_exceptions else (Exception,)
    try:
        return primary_func()
    except exc_types as e:
        logger.warning("'%s' 主调用失败 (%s)，启用降级", label, type(e).__name__)
        return fallback_func()


# ──────────────────────────────────────────────────────────
# 预配置断路器实例（全局单例，供各服务复用）
# ──────────────────────────────────────────────────────────
llm_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    reset_timeout=60.0,
    name="llm_api",
)

embedding_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    reset_timeout=60.0,
    name="embedding_api",
)

rerank_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    reset_timeout=30.0,
    name="rerank_api",
)
