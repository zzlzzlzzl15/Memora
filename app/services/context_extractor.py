"""
上下文提取服务

参照 RAG-Anything 的 ContextExtractor 设计，适配 Memora 的架构：
- ContextConfig: 上下文提取配置（context_window / context_mode / max_context_tokens 等）
- ContextExtractor: 通用上下文提取器，支持 page / chunk 两种模式

支持的内容源格式：
1. MinerU content_list（list of dicts，含 page_idx / type / text）
2. 文本 chunk 列表（list of str）
3. 纯文本字符串
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from loguru import logger


@dataclass
class ContextConfig:
    """上下文提取配置"""

    # 上下文窗口大小（页数 or chunk 数）
    context_window: int = 1
    # 上下文模式："page"（按页边界）/ "chunk"（按块序号）
    context_mode: str = "page"
    # 最大上下文字符数（无分词器时按字符截断，与 RAG-Anything 的 max_context_tokens 对应）
    max_context_tokens: int = 2000
    # 是否在上下文中包含标题（Markdown # 风格）
    include_headers: bool = True
    # 是否在上下文中包含图片/表格标题
    include_captions: bool = True
    # 过滤的内容类型（只有在此列表中的类型才纳入上下文）
    filter_content_types: List[str] = field(default_factory=lambda: ["text"])


class ContextExtractor:
    """
    通用上下文提取器

    使用方式：
        extractor = ContextExtractor(ContextConfig(context_window=1, context_mode="page"))

        # 从 MinerU content_list 提取
        context = extractor.extract_context(
            content_source=content_list,
            current_item_info={"page_idx": 2, "index": 5},
            content_format="minerU",
        )

        # 从文本 chunk 列表提取
        context = extractor.extract_context(
            content_source=text_chunks,
            current_item_info={"index": 3},
            content_format="text_chunks",
        )
    """

    def __init__(self, config: ContextConfig = None):
        self.config = config or ContextConfig()

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def extract_context(
        self,
        content_source: Any,
        current_item_info: Dict[str, Any],
        content_format: str = "auto",
    ) -> str:
        """
        从内容源中提取当前条目的上下文文本

        Args:
            content_source: 内容源（list / str / dict）
            current_item_info: 当前条目的位置信息（page_idx, index 等）
            content_format: 格式提示
                - "minerU"：MinerU content_list（list of dicts）
                - "text_chunks"：简单文本列表（list of str）
                - "text"：纯文本字符串
                - "auto"：自动检测

        Returns:
            上下文文本字符串
        """
        if not content_source:
            return ""

        try:
            if content_format == "minerU" and isinstance(content_source, list):
                return self._extract_from_content_list(content_source, current_item_info)
            elif content_format == "text_chunks" and isinstance(content_source, list):
                return self._extract_from_text_chunks(content_source, current_item_info)
            elif content_format == "text" and isinstance(content_source, str):
                return self._truncate_context(content_source)
            else:
                # 自动检测
                if isinstance(content_source, list):
                    # 如果列表元素是 dict，认为是 MinerU 格式
                    if content_source and isinstance(content_source[0], dict):
                        return self._extract_from_content_list(
                            content_source, current_item_info
                        )
                    else:
                        return self._extract_from_text_chunks(
                            content_source, current_item_info
                        )
                elif isinstance(content_source, str):
                    return self._truncate_context(content_source)
                else:
                    logger.warning(
                        f"[ContextExtractor] 不支持的内容源类型: {type(content_source)}"
                    )
                    return ""
        except Exception as e:
            logger.error(f"[ContextExtractor] 上下文提取失败: {e}")
            return ""

    # ------------------------------------------------------------------
    # MinerU content_list 格式
    # ------------------------------------------------------------------

    def _extract_from_content_list(
        self, content_list: List[Dict], current_item_info: Dict
    ) -> str:
        """从 MinerU content_list 中提取上下文"""
        if self.config.context_mode == "chunk":
            return self._extract_chunk_context_from_list(
                content_list, current_item_info
            )
        else:
            # 默认 page 模式
            return self._extract_page_context(content_list, current_item_info)

    def _extract_page_context(
        self, content_list: List[Dict], current_item_info: Dict
    ) -> str:
        """按页边界提取上下文（RAG-Anything page 模式）"""
        current_page = current_item_info.get("page_idx", 0)
        window = self.config.context_window

        start_page = max(0, current_page - window)
        end_page = current_page + window + 1

        context_parts = []
        for item in content_list:
            item_page = item.get("page_idx", 0)
            item_type = item.get("type", "")

            if start_page <= item_page < end_page and item_type in self.config.filter_content_types:
                text = self._extract_text_from_item(item)
                if text and text.strip():
                    # 非当前页加上页码标记
                    if item_page != current_page:
                        context_parts.append(f"[Page {item_page}] {text}")
                    else:
                        context_parts.append(text)

        return self._truncate_context("\n".join(context_parts))

    def _extract_chunk_context_from_list(
        self, content_list: List[Dict], current_item_info: Dict
    ) -> str:
        """按块序号提取上下文（RAG-Anything chunk 模式）"""
        current_index = current_item_info.get("index", 0)
        window = self.config.context_window

        start_idx = max(0, current_index - window)
        end_idx = min(len(content_list), current_index + window + 1)

        context_parts = []
        for i in range(start_idx, end_idx):
            if i == current_index:
                continue
            item = content_list[i]
            item_type = item.get("type", "")
            if item_type in self.config.filter_content_types:
                text = self._extract_text_from_item(item)
                if text and text.strip():
                    context_parts.append(text)

        return self._truncate_context("\n".join(context_parts))

    def _extract_text_from_item(self, item: Dict) -> str:
        """从单个 content_list 条目中提取文本"""
        item_type = item.get("type", "")

        if item_type == "text":
            text = item.get("text", "")
            text_level = item.get("text_level", 0)
            # Markdown 标题格式化
            if self.config.include_headers and text_level and text_level > 0:
                return f"{'#' * int(text_level)} {text}"
            return text

        elif item_type == "image" and self.config.include_captions:
            captions = item.get("image_caption", item.get("img_caption", []))
            if isinstance(captions, str):
                captions = [captions]
            if captions:
                return f"[Image: {', '.join(captions)}]"

        elif item_type == "table" and self.config.include_captions:
            captions = item.get("table_caption", [])
            if isinstance(captions, str):
                captions = [captions]
            if captions:
                return f"[Table: {', '.join(captions)}]"

        return ""

    # ------------------------------------------------------------------
    # 文本 chunk 列表格式
    # ------------------------------------------------------------------

    def _extract_from_text_chunks(
        self, text_chunks: List[Any], current_item_info: Dict
    ) -> str:
        """
        从文本 chunk 列表中提取相邻 chunk 的内容作为上下文

        适用于 DocumentProcessor.split_text_into_chunks 生成的普通 chunk 列表
        """
        current_index = current_item_info.get("index", 0)
        window = self.config.context_window

        start_idx = max(0, current_index - window)
        end_idx = min(len(text_chunks), current_index + window + 1)

        context_parts = []
        for i in range(start_idx, end_idx):
            if i == current_index:
                continue
            chunk = text_chunks[i]
            # 支持 str / DocumentChunk（有 .content 属性）
            if isinstance(chunk, str):
                text = chunk.strip()
            elif hasattr(chunk, "content"):
                text = (chunk.content or "").strip()
            else:
                text = str(chunk).strip()
            if text:
                context_parts.append(text)

        return self._truncate_context("\n".join(context_parts))

    # ------------------------------------------------------------------
    # 截断逻辑
    # ------------------------------------------------------------------

    def _truncate_context(self, context: str) -> str:
        """
        将上下文截断到最大长度，尽量在句子/段落边界截断
        （RAG-Anything 使用 tokenizer 精确计数，Memora 无 tokenizer 时按字符数）
        """
        if not context:
            return ""

        limit = self.config.max_context_tokens
        if len(context) <= limit:
            return context

        truncated = context[:limit]

        # 优先在句末截断（80% 位置后出现句号/换行时）
        last_newline = truncated.rfind("\n")
        last_period = max(
            truncated.rfind("。"),
            truncated.rfind("."),
            truncated.rfind("！"),
            truncated.rfind("？"),
            truncated.rfind("!"),
            truncated.rfind("?"),
        )

        threshold = len(truncated) * 0.8
        if last_newline > threshold:
            return truncated[:last_newline]
        elif last_period > threshold:
            return truncated[: last_period + 1]
        else:
            return truncated + "..."


# ------------------------------------------------------------------
# 便捷工厂函数
# ------------------------------------------------------------------

def get_context_extractor(
    context_window: int = None,
    context_mode: str = None,
    max_context_tokens: int = None,
    include_headers: bool = None,
    include_captions: bool = None,
    filter_content_types: List[str] = None,
) -> ContextExtractor:
    """
    从 settings 读取默认值，允许局部覆盖，返回 ContextExtractor 实例

    优先使用传入参数，其次读取 settings，最后用 ContextConfig 默认值
    """
    from config.settings import settings

    config = ContextConfig(
        context_window=(
            context_window
            if context_window is not None
            else getattr(settings, "context_window", 1)
        ),
        context_mode=(
            context_mode
            if context_mode is not None
            else getattr(settings, "context_mode", "page")
        ),
        max_context_tokens=(
            max_context_tokens
            if max_context_tokens is not None
            else getattr(settings, "max_context_tokens", 2000)
        ),
        include_headers=(
            include_headers
            if include_headers is not None
            else getattr(settings, "context_include_headers", True)
        ),
        include_captions=(
            include_captions
            if include_captions is not None
            else getattr(settings, "context_include_captions", True)
        ),
        filter_content_types=(
            filter_content_types
            if filter_content_types is not None
            else [
                t.strip()
                for t in getattr(settings, "context_filter_content_types", "text").split(",")
                if t.strip()
            ]
        ),
    )
    return ContextExtractor(config)
