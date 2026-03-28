from typing import List, Optional, AsyncGenerator
import asyncio
import httpx
import json
from loguru import logger
from config.settings import settings
from app.models.document import SearchResult

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

    def _build_messages(self, query: str, results: List[SearchResult]) -> list:
        # 构建上下文（限制每条内容长度，避免超长）
        def clip(text: str, max_len: int = 600) -> str:
            return text[:max_len] + ("..." if len(text) > max_len else "")
        context_lines = []
        for i, r in enumerate(results, 1):
            title = getattr(r, "title", f"片段{i}")
            context_lines.append(f"[来源{i}] 标题: {title}\n内容: {clip(r.content)}\n得分: {getattr(r, 'score', 0):.4f}")
        context_text = "\n\n".join(context_lines) if context_lines else "(无检索上下文)"

        system_prompt = (
            "你是专业的中文知识整理助手。你需要:\n"
            "1) 根据检索到的上下文进行聚合、去重与结构化总结;\n"
            "2) 若信息不足，请明确指出不确定或建议补充;\n"
            "3) 输出使用中文，优先给出直接答案，其后给出要点列表与参考来源编号;\n"
            "4) 避免编造信息，并使用严谨语气。\n"
            "5)你只输出针对用户问题的最终结论。仅基于提供的检索上下文回答;\n"
            "6)不提供来源、引用、链接或编号;不展示推理过程或背景;不复述或改写问题。\n"
            "7)若问题包含多个子问题，逐条分行给出结论;信息不足则回答‘无法确定’，并用最少字指出缺失的关键信息。\n"
            "8)使用中文，避免客套和身份说明。\n"
        )
        user_prompt = (
            f"用户问题: {query}\n\n"
            f"检索上下文如下（可能包含多个片段）:\n{context_text}\n\n"
            f"请仅输出结论，不提供来源或过程。"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _build_messages_for_text(self, text: str, title: Optional[str] = None, source_url: Optional[str] = None) -> list:
        # 对超长文本进行裁剪，避免超过提供商限制
        def clip(text: str, max_len: int = 8000) -> str:  # 增加长度限制，支持更长上下文
            return text[:max_len] + ("..." if len(text) > max_len else "")
        meta = []
        if title:
            meta.append(f"标题: {title}")
        if source_url:
            meta.append(f"来源: {source_url}")
        meta_text = ("\n".join(meta)).strip()
        system_prompt = (
            "你是专业的中文知识整理与汇总助手。你的任务是：\n"
            "1) 以用户当前提供的主要内容（问题或文档）为核心，进行全面、详细的知识整理；\n"
            "2) 利用历史对话上下文理解背景和前后关联，但不要让历史内容喊宾夺主；\n"
            "3) 输出应当结构化、分层次，包含：\n"
            "   - 总体概述：简要总结主题和背景\n"
            "   - 详细内容：针对当前主要内容进行充分展开，保留重要细节\n"
            "   - 关键要点：以列表形式归纳核心知识点\n"
            "   - 总结与建议：给出综合结论和后续建议（如适用）\n"
            "4) 回答应当详尽充分，不要过于简略或概括，需要包含具体的信息和例子；\n"
            "5) 对于历史对话中的相关内容，可以引用和整合，但要确保与当前主题相关；\n"
            "6) 使用中文输出，语气专业严谨，逻辑清晰；\n"
            "7) 如果信息不足，请明确指出不确定之处并给出补充建议。"
        )
        user_prompt = (
            (f"元信息: {meta_text}\n\n" if meta_text else "") +
            f"{clip(text)}\n\n"
            f"请对上述内容进行详细的知识整理，以前面的主要内容为核心，结合后面的历史上下文（如有）理解背景。"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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
            client = await self._ensure_client()
            system_prompt = (
                "你是中文标题生成助手。根据给出的正文，生成一个简洁、准确的标题，\n"
                "要求：\n"
                "1) 仅输出标题文本；\n"
                "2) 不含标点中的非法文件名字符(\\/:*?\"<>|)；\n"
                "3) 不超过60个字符；\n"
                "4) 不要包含引号或括号中的来源链接。"
            )
            def clip(s: str, n: int = 400):
                return s[:n] + ("..." if len(s) > n else "")
            user_prompt = f"正文如下，生成标题：\n{clip(text)}"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 128,
                "stream": False,
            }
            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
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

    async def summarize_results(self, query: str, results: List[SearchResult]) -> str:
        """对检索结果进行知识整理，返回答案文本。"""
        # 无API Key，执行本地回退整理
        if not self.api_key:
            logger.warning("未配置LLM_API_KEY，使用本地回退整理")
            text = self._local_summarize(query, results)
            self._llm_logger.info(f"[sync] query={query}\n{text}")
            return text

        try:
            client = await self._ensure_client()
            payload = {
                "model": self.model,
                "messages": self._build_messages(query, results),
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": False,
            }
            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            self._llm_logger.info(f"[sync] query={query}\n{content}")
            return content.strip()
        except Exception as e:
            logger.error(f"LLM整理失败，回退本地摘要: {e}")
            text = self._local_summarize(query, results)
            self._llm_logger.info(f"[sync-fallback] query={query}\n{text}")
            return text

    async def summarize_results_stream(self, query: str, results: List[SearchResult]) -> AsyncGenerator[str, None]:
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
                "messages": self._build_messages(query, results),
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True,
            }
            buffer = ""
            async with client.stream("POST", "/chat/completions", json=payload) as resp:
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
            client = await self._ensure_client()
            payload = {
                "model": self.model,
                "messages": self._build_messages_for_text(text, title=title, source_url=source_url),
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": False,
            }
            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            self._llm_logger.info(f"[sync] text_len={len(text)}\n{content}")
            return content.strip()
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

# 全局实例
_llm_service: Optional[LLMService] = None

def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service