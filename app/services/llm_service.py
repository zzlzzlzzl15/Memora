from typing import List, Optional, AsyncGenerator
import asyncio
import base64
import httpx
import json
import os
from pathlib import Path
from loguru import logger
from config.settings import settings
from app.models.document import SearchResult
from app.core.resilience import async_retry, llm_circuit_breaker, CircuitBreaker
from app.core.prompts import PROMPTS

class LLMService:
    """LLM服务：使用OpenAI兼容接口（如DeepSeek）进行知识整理输出
    - 当未提供API Key时，启用本地回退整理（基于简单规则的摘要）。
    """
    def __init__(self):
        self.api_base = settings.llm_api_base
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self._client: Optional[httpx.AsyncClient] = None
        # 专用LLM日志记录器（写入 llm.log）
        self._llm_logger = logger.bind(component="llm")

    def _build_messages(self, query: str, results: List[SearchResult], fused_context: str = None) -> list:
        # 构建上下文（限制每条内容长度，避免超长）
        def clip(text: str, max_len: int = 600) -> str:
            return text[:max_len] + ("..." if len(text) > max_len else "")
        context_lines = []
        for i, r in enumerate(results, 1):
            title = getattr(r, "title", f"片段{i}")
            context_lines.append(f"[来源{i}] 标题: {title}\n内容: {clip(r.content)}\n得分: {getattr(r, 'score', 0):.4f}")
        context_text = "\n\n".join(context_lines) if context_lines else "(无检索上下文)"
    
        # 如果有知识图谱融合上下文，拼接到检索上下文后面
        if fused_context:
            context_text = f"{context_text}\n\n--- 知识图谱增强上下文 ---\n{fused_context}"
    
        return [
            {"role": "system", "content": PROMPTS["KNOWLEDGE_QUERY_SYSTEM"]},
            {"role": "user", "content": PROMPTS["KNOWLEDGE_QUERY_USER"].format(
                query=query, context=context_text
            )},
        ]

    def _build_messages_for_text(self, text: str, title: Optional[str] = None, source_url: Optional[str] = None) -> list:
        # 对超长文本进行裁剪，避免超过提供商限制
        def clip(text: str, max_len: int = 8000) -> str:
            return text[:max_len] + ("..." if len(text) > max_len else "")
        meta = []
        if title:
            meta.append(f"标题: {title}")
        if source_url:
            meta.append(f"来源: {source_url}")
        meta_text = ("\n".join(meta) + "\n\n") if meta else ""
        return [
            {"role": "system", "content": PROMPTS["TEXT_SUMMARIZE_SYSTEM"]},
            {"role": "user", "content": PROMPTS["TEXT_SUMMARIZE_USER"].format(
                meta_text=meta_text, content=clip(text)
            )},
        ]

    async def generate_title(self, text: str, max_len: int = 60) -> str:
        """从文本生成简洁标题，适合作为知识文件名。
        - 若未配置API Key，则使用本地回退规则：截取前几句，清理文件名不合法字符。
        - 输出限制：不超过max_len字符，移除换行与危险符号。
        """
        def sanitize(s: str) -> str:
            # 移除文件名不合法字符并裁剪长度
            illegal = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
            for ch in illegal:
                s = s.replace(ch, '')
            s = s.replace('\n', ' ').replace('\r', ' ').strip()
            # 压缩多余空格
            s = ' '.join(s.split())
            if len(s) > max_len:
                s = s[:max_len]
            return s or '未命名知识'

        # 本地回退
        if not self.api_key:
            logger.warning("未配置LLM_API_KEY，使用本地标题生成")
            base = (text or '').strip()
            if not base:
                return '未命名知识'
            # 尝试取第一行或前80字
            first_line = base.splitlines()[0].strip()
            candidate = first_line if first_line else base[:80]
            # 去除常见前缀
            for prefix in ['总结', '梳理', '概述', '内容整理', '请对以下网页进行知识梳理并总结，涵盖结构、关键要点、结论与建议：']:
                if candidate.startswith(prefix):
                    candidate = candidate[len(prefix):].strip()
            return sanitize(candidate)

        # 使用LLM生成
        try:
            def clip(s: str, n: int = 400):
                return s[:n] + ("..." if len(s) > n else "")
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": PROMPTS["TITLE_GENERATE_SYSTEM"]},
                    {"role": "user", "content": PROMPTS["TITLE_GENERATE_USER"].format(text=clip(text))},
                ],
                "temperature": 0.2,
                "max_tokens": 128,
                "stream": False,
            }
            data = await self._call_llm_api(payload)
            title = data["choices"][0]["message"]["content"].strip()
            self._llm_logger.info(f"[title] len={len(text)} -> {title}")
            return sanitize(title)
        except Exception as e:
            logger.error(f"LLM标题生成失败，回退本地规则: {e}")
            base = (text or '').strip()
            if not base:
                return '未命名知识'
            first_line = base.splitlines()[0].strip()
            candidate = first_line if first_line else base[:80]
            return sanitize(candidate)

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            # 设置较长的超时时间，支持流式生成长内容
            timeout = httpx.Timeout(300.0, connect=10.0)  # 总超时300秒，连接超时10秒
            self._client = httpx.AsyncClient(base_url=self.api_base, timeout=timeout, headers=headers)
        return self._client

    @async_retry(max_attempts=3, base_delay=1.0, max_delay=30.0)
    async def _call_llm_api(self, payload: dict) -> dict:
        """带重试的 LLM API 调用（非流式），断路器保护"""
        client = await self._ensure_client()
        resp = await client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()

    @async_retry(max_attempts=2, base_delay=0.5, max_delay=10.0)
    async def _call_llm_api_stream(self, payload: dict):
        """带重试的 LLM API 流式调用（返回上下文管理器）"""
        client = await self._ensure_client()
        return client.stream("POST", "/chat/completions", json=payload)

    async def summarize_results(self, query: str, results: List[SearchResult], fused_context: str = None) -> str:
        """对检索结果进行知识整理，返回答案文本。"""
        # 无API Key，执行本地回退整理
        if not self.api_key:
            logger.warning("未配置LLM_API_KEY，使用本地回退整理")
            text = self._local_summarize(query, results)
            self._llm_logger.info(f"[sync] query={query}\n{text}")
            return text

        try:
            payload = {
                "model": self.model,
                "messages": self._build_messages(query, results, fused_context=fused_context),
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": False,
            }
            data = await self._call_llm_api(payload)
            content = data["choices"][0]["message"]["content"]
            self._llm_logger.info(f"[sync] query={query}\n{content}")
            return content.strip()
        except CircuitBreaker.CircuitBreakerOpen as e:
            logger.warning(f"LLM 断路器已打开，直接降级: {e}")
            text = self._local_summarize(query, results)
            self._llm_logger.info(f"[sync-circuit-open] query={query}\n{text}")
            return text
        except Exception as e:
            logger.error(f"LLM整理失败，回退本地摘要: {e}")
            text = self._local_summarize(query, results)
            self._llm_logger.info(f"[sync-fallback] query={query}\n{text}")
            return text

    async def summarize_results_stream(self, query: str, results: List[SearchResult], fused_context: str = None) -> AsyncGenerator[str, None]:
        """对检索结果进行知识整理，按增量流式返回文本。
        - 当未提供API Key时，使用本地回退摘要并以小块流式输出。
        - 当配置了OpenAI兼容接口时，使用SSE流式解析choices[0].delta.content。
        """
        # 无API Key，执行本地回退整理并模拟流式输出
        if not self.api_key:
            logger.warning("未配置LLM_API_KEY，使用本地回退整理(流式)")
            text = self._local_summarize(query, results)
            self._llm_logger.info(f"[stream] query={query}\n{text}")
            # 以固定大小分片模拟流式输出
            chunk_size = 24
            for i in range(0, len(text), chunk_size):
                yield text[i : i + chunk_size]
                await asyncio.sleep(0.02)
            return

        # 使用OpenAI兼容接口进行真实流式输出
        try:
            client = await self._ensure_client()
            payload = {
                "model": self.model,
                "messages": self._build_messages(query, results, fused_context=fused_context),
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True,
            }
            buffer = ""
            async with client.stream("POST", "/chat/completions", json=payload) as resp:  # noqa: stream
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    # OpenAI风格SSE: 每行以"data: {json}"或"data: [DONE]"给出
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if not data_str:
                            continue
                        if data_str == "[DONE]":
                            break
                        try:
                            obj = json.loads(data_str)
                            choices = obj.get("choices") or []
                            if choices:
                                delta = (choices[0].get("delta") or {}).get("content")
                                if delta:
                                    buffer += delta
                                    self._llm_logger.debug(f"[stream-delta] {delta}")
                                    yield delta
                        except Exception as parse_err:
                            logger.debug(f"LLM流式解析失败，忽略该片段: {parse_err}")
                    else:
                        # 某些提供商可能直接返回JSON行，不带前缀
                        try:
                            obj = json.loads(line)
                            choices = obj.get("choices") or []
                            if choices:
                                delta = (choices[0].get("delta") or {}).get("content")
                                if delta:
                                    buffer += delta
                                    self._llm_logger.debug(f"[stream-delta] {delta}")
                                    yield delta
                        except Exception:
                            # 非JSON杂散行，忽略
                            continue
            # 流结束后记录最终组合文本
            if buffer:
                self._llm_logger.info(f"[stream-final] query={query}\n{buffer}")
        except Exception as e:
            logger.error(f"LLM流式整理失败，回退本地摘要(流式): {e}")
            text = self._local_summarize(query, results)
            self._llm_logger.info(f"[stream-fallback] query={query}\n{text}")
            chunk_size = 24
            for i in range(0, len(text), chunk_size):
                yield text[i : i + chunk_size]
                await asyncio.sleep(0.02)

    async def summarize_text(self, text: str, title: Optional[str] = None, source_url: Optional[str] = None) -> str:
        """对任意长文本进行总结，返回答案文本。"""
        if not self.api_key:
            logger.warning("未配置LLM_API_KEY，使用本地回退整理")
            result = self._local_summarize_text(text)
            self._llm_logger.info(f"[sync] text_len={len(text)}\n{result}")
            return result

        try:
            payload = {
                "model": self.model,
                "messages": self._build_messages_for_text(text, title=title, source_url=source_url),
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": False,
            }
            data = await self._call_llm_api(payload)
            content = data["choices"][0]["message"]["content"]
            self._llm_logger.info(f"[sync] text_len={len(text)}\n{content}")
            return content.strip()
        except CircuitBreaker.CircuitBreakerOpen as e:
            logger.warning(f"LLM 断路器已打开，直接降级: {e}")
            result = self._local_summarize_text(text)
            self._llm_logger.info(f"[sync-circuit-open] text_len={len(text)}\n{result}")
            return result
        except Exception as e:
            logger.error(f"LLM整理失败，回退本地摘要: {e}")
            result = self._local_summarize_text(text)
            self._llm_logger.info(f"[sync-fallback] text_len={len(text)}\n{result}")
            return result

    async def summarize_text_stream(self, text: str, title: Optional[str] = None, source_url: Optional[str] = None) -> AsyncGenerator[str, None]:
        """对任意长文本进行总结，按增量流式返回文本。"""
        logger.info(f"summarize_text_stream: start, api_key={'YES' if self.api_key else 'NO'}, text_len={len(text)}")
        if not self.api_key:
            logger.warning("未配置LLM_API_KEY，使用本地回退整理(流式)")
            result = self._local_summarize_text(text)
            self._llm_logger.info(f"[stream] text_len={len(text)}\n{result}")
            chunk_size = 24
            for i in range(0, len(result), chunk_size):
                yield result[i : i + chunk_size]
                await asyncio.sleep(0.02)
            return

        try:
            logger.info("summarize_text_stream: 准备调用LLM API")
            client = await self._ensure_client()
            payload = {
                "model": self.model,
                "messages": self._build_messages_for_text(text, title=title, source_url=source_url),
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True,
            }
            logger.info(f"summarize_text_stream: 请求 payload model={self.model}, max_tokens={self.max_tokens}")
            buffer = ""
            async with client.stream("POST", "/chat/completions", json=payload) as resp:
                logger.info(f"summarize_text_stream: 收到响应 status={resp.status_code}")
                if resp.status_code != 200:
                    error_text = await resp.aread()
                    logger.error(f"LLM API错误: status={resp.status_code}, body={error_text.decode('utf-8')[:500]}")
                    # 回退到本地整理
                    result = self._local_summarize_text(text)
                    chunk_size = 24
                    for i in range(0, len(result), chunk_size):
                        yield result[i : i + chunk_size]
                        await asyncio.sleep(0.02)
                    return
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    logger.debug(f"SSE line: {line[:100]}...")  # 只记录前100字符
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if not data_str:
                            continue
                        if data_str == "[DONE]":
                            break
                        try:
                            obj = json.loads(data_str)
                            choices = obj.get("choices") or []
                            if choices:
                                delta = (choices[0].get("delta") or {}).get("content")
                                if delta:
                                    buffer += delta
                                    self._llm_logger.debug(f"[stream-delta] {delta}")
                                    yield delta
                        except Exception as parse_err:
                            logger.debug(f"LLM流式解析失败，忽略该片段: {parse_err}")
                    else:
                        try:
                            obj = json.loads(line)
                            choices = obj.get("choices") or []
                            if choices:
                                delta = (choices[0].get("delta") or {}).get("content")
                                if delta:
                                    buffer += delta
                                    self._llm_logger.debug(f"[stream-delta] {delta}")
                                    yield delta
                        except Exception:
                            continue
            if buffer:
                self._llm_logger.info(f"[stream-final] text_len={len(text)}\n{buffer}")
        except Exception as e:
            logger.error(f"LLM流式整理失败，回退本地摘要(流式): {e}")
            result = self._local_summarize_text(text)
            self._llm_logger.info(f"[stream-fallback] text_len={len(text)}\n{result}")
            chunk_size = 24
            for i in range(0, len(result), chunk_size):
                yield result[i : i + chunk_size]
                await asyncio.sleep(0.02)

    def _local_summarize(self, query: str, results: List[SearchResult]) -> str:
        # 本地回退：保留换行，并输出多行要点以便前端显示
        if not results:
            return "无法确定；缺少检索上下文。"

        bullets = []
        for r in results[:3]:  # 取前3条检索结果做要点
            content = (getattr(r, "content", "") or "").strip()
            # 标准化换行
            content = content.replace("\r\n", "\n").replace("\r", "\n")
            # 优先按换行取第一行，其次按标点取首句
            first = None
            newline_idx = content.find("\n")
            if newline_idx != -1:
                first = content[:newline_idx].strip()
            else:
                for sep in ["。", "！", "？", ".", "!", "?"]:
                    idx = content.find(sep)
                    if idx != -1:
                        first = content[: idx + 1].strip()
                        break
            if not first:
                first = content[:120].strip() + ("..." if len(content) > 120 else "")
            bullets.append(f"- {first}")

        # 若只有一条结果，仍返回单条但保留原有换行（若存在）
        return "\n".join(bullets) if bullets else "无法确定；缺少检索上下文。"

    def _local_summarize_text(self, text: str) -> str:
        # 简单本地整理：取前几段/句生成要点
        content = (text or "").strip().replace("\r\n", "\n").replace("\r", "\n")
        if not content:
            return "无法确定；缺少文本内容。"
        # 分段
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        bullets = []
        for p in paragraphs[:4]:
            # 每段取首句或前120字
            first = None
            for sep in ["。", "！", "？", ".", "!", "?"]:
                idx = p.find(sep)
                if idx != -1:
                    first = p[: idx + 1].strip()
                    break
            if not first:
                first = p[:120].strip() + ("..." if len(p) > 120 else "")
            bullets.append(f"- {first}")
        return "\n".join(bullets) if bullets else (content[:240] + ("..." if len(content) > 240 else ""))

    # ─── VLM 增强问答（参照 RAG-Anything aquery_vlm_enhanced）──────────────────

    @property
    def vlm_available(self) -> bool:
        """VLM 是否可用"""
        return (
            settings.vlm_enabled
            and bool(settings.vlm_api_key or settings.vlm_api_base)
        )

    def _encode_image_base64(self, image_path: str) -> Optional[str]:
        """将图片文件编码为 base64，参照 RAG-Anything _process_image_paths_for_vlm"""
        try:
            path = Path(image_path).resolve()
            upload_dir = Path(settings.upload_dir).resolve()
            if not str(path).startswith(str(upload_dir)):
                logger.warning(f"VLM: 图片路径超出安全范围: {path}")
                return None
            if not path.exists():
                return None
            if path.stat().st_size > 10 * 1024 * 1024:
                logger.warning(f"VLM: 图片过大，跳过: {path}")
                return None
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.warning(f"VLM: 图片编码失败 {image_path}: {e}")
            return None

    def _build_vlm_messages(self, query: str, results: List[SearchResult],
                            fused_context: Optional[str] = None) -> list:
        """构建 VLM 多模态 messages，参照 RAG-Anything _build_vlm_messages_with_images。
        - 文本 context 里用 [VLM_IMAGE_N] 标记图片位置
        - content_parts 按文本 + 图片 base64 交替排列
        - 若无图片，回退到纯文本 messages
        """
        import re as _re

        def clip(t, n=600):
            return t[:n] + ("..." if len(t) > n else "")

        images_b64: List[str] = []
        result_img_idx: dict = {}
        for i, r in enumerate(results):
            if getattr(r, "content_type", "text") == "image" and getattr(r, "image_path", None):
                b64 = self._encode_image_base64(r.image_path)
                if b64:
                    images_b64.append(b64)
                    result_img_idx[i] = len(images_b64)

        context_lines = []
        for i, r in enumerate(results):
            title = getattr(r, "title", f"片段{i+1}")
            line = f"[来源{i+1}] 标题: {title}\n内容: {clip(r.content)}\n得分: {getattr(r,'score',0):.4f}"
            img_num = result_img_idx.get(i)
            if img_num:
                line += f"\n[VLM_IMAGE_{img_num}]"
            context_lines.append(line)
        context_text = "\n\n".join(context_lines) if context_lines else "(无检索上下文)"
        if fused_context:
            context_text += f"\n\n--- 知识图谱增强上下文 ---\n{fused_context}"

        if not images_b64:
            return self._build_messages(query, results, fused_context)

        content_parts = []
        segments = context_text.split("[VLM_IMAGE_")
        for idx, seg in enumerate(segments):
            if idx == 0:
                if seg.strip():
                    content_parts.append({"type": "text", "text": seg})
            else:
                m = _re.match(r"(\d+)\](.*)", seg, _re.DOTALL)
                if m:
                    img_num = int(m.group(1)) - 1
                    remaining = m.group(2)
                    if 0 <= img_num < len(images_b64):
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{images_b64[img_num]}"}
                        })
                    if remaining.strip():
                        content_parts.append({"type": "text", "text": remaining})

        content_parts.append({"type": "text",
            "text": PROMPTS["VLM_USER_SUFFIX"].format(query=query)})

        return [
            {"role": "system", "content": PROMPTS["VLM_SYSTEM"]},
            {"role": "user", "content": content_parts},
        ]

    async def summarize_results_vlm(
        self, query: str, results: List[SearchResult],
        fused_context: Optional[str] = None
    ) -> str:
        """使用 VLM 多模态整理检索结果。若 VLM 不可用或无图片，自动降级到普通 LLM。"""
        if not self.vlm_available:
            return await self.summarize_results(query, results, fused_context)
        has_images = any(getattr(r, "content_type", "text") == "image"
                        and getattr(r, "image_path", None) for r in results)
        if not has_images:
            return await self.summarize_results(query, results, fused_context)
        try:
            messages = self._build_vlm_messages(query, results, fused_context)
            vlm_base = settings.vlm_api_base or self.api_base
            vlm_key = settings.vlm_api_key or self.api_key
            headers = {"Authorization": f"Bearer {vlm_key}"} if vlm_key else {}
            async with httpx.AsyncClient(
                base_url=vlm_base, timeout=httpx.Timeout(300.0, connect=10.0), headers=headers
            ) as client:
                payload = {"model": settings.vlm_model, "messages": messages,
                           "temperature": self.temperature, "max_tokens": self.max_tokens, "stream": False}
                resp = await client.post("/chat/completions", json=payload)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                self._llm_logger.info(f"[vlm-sync] query={query}\n{content}")
                return content.strip()
        except Exception as e:
            logger.error(f"VLM 整理失败，回退普通 LLM: {e}")
            return await self.summarize_results(query, results, fused_context)

    async def summarize_results_vlm_stream(
        self, query: str, results: List[SearchResult],
        fused_context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """使用 VLM 多模态流式整理。参照 RAG-Anything aquery_vlm_enhanced。"""
        if not self.vlm_available:
            async for chunk in self.summarize_results_stream(query, results, fused_context):
                yield chunk
            return
        has_images = any(getattr(r, "content_type", "text") == "image"
                        and getattr(r, "image_path", None) for r in results)
        if not has_images:
            async for chunk in self.summarize_results_stream(query, results, fused_context):
                yield chunk
            return
        try:
            messages = self._build_vlm_messages(query, results, fused_context)
            vlm_base = settings.vlm_api_base or self.api_base
            vlm_key = settings.vlm_api_key or self.api_key
            headers = {"Authorization": f"Bearer {vlm_key}"} if vlm_key else {}
            async with httpx.AsyncClient(
                base_url=vlm_base, timeout=httpx.Timeout(300.0, connect=10.0), headers=headers
            ) as client:
                payload = {"model": settings.vlm_model, "messages": messages,
                           "temperature": self.temperature, "max_tokens": self.max_tokens, "stream": True}
                buffer = ""
                async with client.stream("POST", "/chat/completions", json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            if not data_str:
                                continue
                            try:
                                obj = json.loads(data_str)
                                delta = ((obj.get("choices") or [{}])[0].get("delta") or {}).get("content")
                                if delta:
                                    buffer += delta
                                    yield delta
                            except Exception:
                                pass
                if buffer:
                    self._llm_logger.info(f"[vlm-stream-final] query={query}\n{buffer}")
        except Exception as e:
            logger.error(f"VLM 流式整理失败，回退普通 LLM: {e}")
            async for chunk in self.summarize_results_stream(query, results, fused_context):
                yield chunk

# 全局实例
_llm_service: Optional[LLMService] = None

def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service