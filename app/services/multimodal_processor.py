"""
多模态内容处理器

将结构化解析器输出的各类型内容（图片/表格/公式）转换为可索引的文本 chunk，
并生成对应的 Qdrant payload 元数据。

参照 RAG-Anything 的"三路存储、文本统一"设计：
- 原始二进制（图片/表格截图）保留在文件系统
- 语义信息统一转为文本后存入向量库
- 元数据（content_type, image_path, captions 等）存入 Qdrant payload

上下文感知（对标 RAG-Anything ContextExtractor）：
- 当 StructuredContent 携带 raw_content_list（MinerU 全文列表）时，
  使用 ContextExtractor page 模式提取周围文本作为 context，
  注入到 VLM/LLM 的 prompt 中，显著提升多模态内容描述质量。
"""
import os
import base64
from typing import Optional, Dict, Any, List
from loguru import logger

from app.services.structured_parser import StructuredContent
from app.services.context_extractor import get_context_extractor, ContextExtractor
from config.settings import settings


class MultimodalProcessor:
    """多模态内容处理器"""

    def __init__(self, context_extractor: ContextExtractor = None):
        self._vlm_available = None
        # 上下文提取器：未传入时从 settings 自动创建
        self._context_extractor = context_extractor

    @property
    def vlm_available(self) -> bool:
        """检查 VLM 是否可用"""
        if self._vlm_available is None:
            self._vlm_available = (
                settings.vlm_enabled
                and bool(settings.vlm_api_key or settings.vlm_api_base)
            )
            if self._vlm_available:
                logger.info("VLM 增强描述已启用")
            else:
                logger.info("VLM 未启用，多模态内容仅使用基础描述")
        return self._vlm_available

    @property
    def context_extractor(self) -> ContextExtractor:
        """懒加载上下文提取器"""
        if self._context_extractor is None:
            self._context_extractor = get_context_extractor()
        return self._context_extractor

    def _get_context_for_content(self, content: StructuredContent) -> str:
        """
        为多模态内容提取上下文文本（对标 RAG-Anything BaseModalProcessor._get_context_for_item）

        优先使用 raw_content_list + page 模式（MinerU 全文上下文），
        其次回退到 neighbor_text 字段（前一个文本块）。
        """
        # MinerU 全文上下文（page 模式）
        raw_content_list = getattr(content, "raw_content_list", None)
        if raw_content_list and content.page_idx is not None:
            item_info = {
                "page_idx": content.page_idx,
                "index": getattr(content, "list_index", 0),
            }
            ctx = self.context_extractor.extract_context(
                content_source=raw_content_list,
                current_item_info=item_info,
                content_format="minerU",
            )
            if ctx:
                return ctx

        # 降级：使用 neighbor_text（前一个文本块）
        if content.neighbor_text:
            limit = getattr(settings, "max_context_tokens", 2000)
            return content.neighbor_text[:limit]

        return ""

    async def process_content(
        self, content: StructuredContent, document_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        处理单个结构化内容项，返回 chunk 数据

        Returns:
            {
                "content": "chunk 文本内容（用于向量化和检索）",
                "content_type": "text" | "image" | "table" | "equation",
                "image_path": "图片/截图文件路径（仅图片和表格）",
                "captions": ["标题列表"],
                "section_path": "章节路径",
                "page_number": 页码,
                "metadata": {额外元数据},
            }
            或 None（如果内容为空）
        """
        if content.content_type == StructuredContent.TYPE_TEXT:
            return self._process_text(content, document_id)
        elif content.content_type == StructuredContent.TYPE_IMAGE:
            return await self._process_image(content, document_id)
        elif content.content_type == StructuredContent.TYPE_TABLE:
            return await self._process_table(content, document_id)
        elif content.content_type == StructuredContent.TYPE_EQUATION:
            return await self._process_equation(content, document_id)
        else:
            logger.warning(f"未知内容类型: {content.content_type}")
            return None

    def _process_text(
        self, content: StructuredContent, document_id: str
    ) -> Optional[Dict[str, Any]]:
        """处理文本内容"""
        text = (content.text or "").strip()
        if not text:
            return None

        return {
            "content": text,
            "content_type": "text",
            "image_path": None,
            "captions": [],
            "section_path": content.section_path,
            "page_number": content.page_idx,
            "metadata": {
                "document_id": document_id,
                "type": "text",
            },
        }

    async def _process_image(
        self, content: StructuredContent, document_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        处理图片内容

        图片 chunk 格式（参照 RAG-Anything image_chunk 模板）：
        Image Content Analysis:
        - Section Path: ...
        - Neighbor Text: ...
        Image Path: ...
        Captions: ...
        Footnotes: ...
        Visual Analysis: [VLM 生成的描述]
        """
        image_path = content.image_path
        if not image_path or not os.path.exists(image_path):
            logger.warning(f"图片文件不存在: {image_path}")
            # 仍然生成一个基础描述
            return self._build_image_chunk_without_vlm(content, document_id)

        # ---- 上下文提取（对标 RAG-Anything ContextExtractor）----
        context = self._get_context_for_content(content)

        # 生成 VLM 描述
        enhanced_caption = ""
        if self.vlm_available:
            enhanced_caption = await self._generate_vlm_description(
                image_path,
                content.caption or "",
                context or content.neighbor_text or "",
            )

        if not enhanced_caption:
            enhanced_caption = f"[图片描述不可用] 标题: {content.caption or '无标题'}"

        # 组装 image_chunk 文本
        chunk_text_parts = ["Image Content Analysis:"]
        if content.section_path:
            chunk_text_parts.append(f"- Section Path: {content.section_path}")
        # 优先使用 page 模式上下文，其次 neighbor_text
        display_context = context or content.neighbor_text or ""
        if display_context:
            neighbor_preview = display_context[:200]
            chunk_text_parts.append(f"- Neighbor Text: {neighbor_preview}")
        chunk_text_parts.append(f"Image Path: {image_path}")
        chunk_text_parts.append(f"Captions: {content.caption or '无标题'}")
        if content.footnote:
            chunk_text_parts.append(f"Footnotes: {content.footnote}")
        chunk_text_parts.append(f"Visual Analysis: {enhanced_caption}")

        chunk_text = "\n".join(chunk_text_parts)

        return {
            "content": chunk_text,
            "content_type": "image",
            "image_path": image_path,
            "captions": [content.caption] if content.caption else [],
            "section_path": content.section_path,
            "page_number": content.page_idx,
            "metadata": {
                "document_id": document_id,
                "type": "image",
                "original_caption": content.caption or "",
                "enhanced_caption": enhanced_caption,
                "context_used": bool(context),
            },
        }

    def _build_image_chunk_without_vlm(
        self, content: StructuredContent, document_id: str
    ) -> Optional[Dict[str, Any]]:
        """在没有 VLM 的情况下构建基础图片 chunk"""
        # 上下文提取
        context = self._get_context_for_content(content)
        display_context = context or content.neighbor_text or ""

        chunk_text_parts = ["Image Content Analysis:"]
        if content.section_path:
            chunk_text_parts.append(f"- Section Path: {content.section_path}")
        if display_context:
            neighbor_preview = display_context[:200]
            chunk_text_parts.append(f"- Neighbor Text: {neighbor_preview}")
        if content.image_path:
            chunk_text_parts.append(f"Image Path: {content.image_path}")
        chunk_text_parts.append(f"Captions: {content.caption or '无标题'}")
        if content.footnote:
            chunk_text_parts.append(f"Footnotes: {content.footnote}")
        chunk_text_parts.append("Visual Analysis: [VLM 未启用，图片描述不可用]")

        chunk_text = "\n".join(chunk_text_parts)

        return {
            "content": chunk_text,
            "content_type": "image",
            "image_path": content.image_path,
            "captions": [content.caption] if content.caption else [],
            "section_path": content.section_path,
            "page_number": content.page_idx,
            "metadata": {
                "document_id": document_id,
                "type": "image",
                "vlm_skipped": True,
                "context_used": bool(context),
            },
        }

    async def _process_table(
        self, content: StructuredContent, document_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        处理表格内容

        表格 chunk 格式（参照 RAG-Anything table_chunk 模板）：
        Table Analysis:
        Image Path: ...
        Caption: ...
        Structure: [Markdown 表格]
        Footnotes: ...
        Analysis: [LLM 分析]
        """
        # ---- 上下文提取 ----
        context = self._get_context_for_content(content)

        # 生成 LLM 分析
        enhanced_analysis = ""
        table_body = content.table_body or ""

        if settings.llm_api_key and table_body:
            enhanced_analysis = await self._generate_table_analysis(
                table_body, content.caption or "", context
            )

        if not enhanced_analysis:
            enhanced_analysis = f"[表格分析不可用] 标题: {content.caption or '无标题'}"

        # 组装 table_chunk 文本
        chunk_text_parts = ["Table Analysis:"]
        if content.image_path:
            chunk_text_parts.append(f"Image Path: {content.image_path}")
        chunk_text_parts.append(f"Caption: {content.caption or '无标题'}")
        if table_body:
            chunk_text_parts.append(f"Structure: {table_body}")
        if content.footnote:
            chunk_text_parts.append(f"Footnotes: {content.footnote}")
        chunk_text_parts.append(f"Analysis: {enhanced_analysis}")

        chunk_text = "\n".join(chunk_text_parts)

        return {
            "content": chunk_text,
            "content_type": "table",
            "image_path": content.image_path,
            "captions": [content.caption] if content.caption else [],
            "section_path": content.section_path,
            "page_number": content.page_idx,
            "metadata": {
                "document_id": document_id,
                "type": "table",
                "table_body": table_body,
                "enhanced_analysis": enhanced_analysis,
                "context_used": bool(context),
            },
        }

    async def _process_equation(
        self, content: StructuredContent, document_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        处理公式内容

        公式 chunk 格式（参照 RAG-Anything equation_chunk 模板）：
        Mathematical Equation Analysis:
        Equation: [LaTeX]
        Format: latex
        Mathematical Analysis: [LLM 解释]
        """
        equation_text = content.equation_text or ""

        # ---- 上下文提取 ----
        context = self._get_context_for_content(content)

        # 生成 LLM 解释
        enhanced_explanation = ""
        if settings.llm_api_key and equation_text:
            enhanced_explanation = await self._generate_equation_explanation(
                equation_text, context
            )

        if not enhanced_explanation:
            enhanced_explanation = "[公式解释不可用]"

        # 组装 equation_chunk 文本
        chunk_text_parts = ["Mathematical Equation Analysis:"]
        chunk_text_parts.append(f"Equation: {equation_text}")
        chunk_text_parts.append(f"Format: {content.equation_format or 'latex'}")
        chunk_text_parts.append(f"Mathematical Analysis: {enhanced_explanation}")

        chunk_text = "\n".join(chunk_text_parts)

        return {
            "content": chunk_text,
            "content_type": "equation",
            "image_path": None,
            "captions": [content.caption] if content.caption else [],
            "section_path": content.section_path,
            "page_number": content.page_idx,
            "metadata": {
                "document_id": document_id,
                "type": "equation",
                "equation_text": equation_text,
                "enhanced_explanation": enhanced_explanation,
                "context_used": bool(context),
            },
        }

    # --- VLM / LLM 调用方法 ---

    async def _generate_vlm_description(
        self, image_path: str, caption: str, context: str
    ) -> str:
        """使用 VLM 生成图片描述（注入文档上下文）"""
        try:
            import httpx

            # 读取图片并编码为 base64
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # 确定图片 MIME 类型
            ext = os.path.splitext(image_path)[1].lower()
            mime_map = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}
            mime_type = f"image/{mime_map.get(ext, 'jpeg')}"

            api_base = settings.vlm_api_base or settings.llm_api_base
            api_key = settings.vlm_api_key or settings.llm_api_key

            prompt = "请详细描述这张图片的内容。"
            if caption:
                prompt += f"\n图片标题: {caption}"
            # 注入上下文（来自 ContextExtractor page 模式或 neighbor_text）
            if context:
                prompt += f"\n\n文档上下文（图片周围的文本内容，供参考）:\n{context[:500]}"

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            },
                        },
                    ],
                }
            ]

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": settings.vlm_model,
                        "messages": messages,
                        "max_tokens": 500,
                    },
                )
                response.raise_for_status()
                result = response.json()
                description = result["choices"][0]["message"]["content"]
                logger.info(f"VLM 描述生成成功: {image_path}")
                return description

        except Exception as e:
            logger.warning(f"VLM 描述生成失败: {e}")
            return ""

    async def _generate_table_analysis(
        self, table_body: str, caption: str, context: str = ""
    ) -> str:
        """使用 LLM 生成表格分析（注入文档上下文）"""
        try:
            import httpx

            api_base = settings.llm_api_base
            api_key = settings.llm_api_key

            prompt = "请分析以下表格数据，总结其关键信息和规律：\n\n"
            if caption:
                prompt += f"表格标题: {caption}\n\n"
            prompt += f"表格内容:\n{table_body}\n\n"
            # 注入上下文
            if context:
                prompt += f"文档上下文（表格周围的文本内容，供参考）:\n{context[:500]}\n\n"
            prompt += "请用简洁的中文进行分析总结。"

            messages = [{"role": "user", "content": prompt}]

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": settings.llm_model,
                        "messages": messages,
                        "max_tokens": 500,
                        "temperature": 0.3,
                    },
                )
                response.raise_for_status()
                result = response.json()
                analysis = result["choices"][0]["message"]["content"]
                logger.info("表格分析生成成功")
                return analysis

        except Exception as e:
            logger.warning(f"表格分析生成失败: {e}")
            return ""

    async def _generate_equation_explanation(
        self, equation_text: str, context: str = ""
    ) -> str:
        """使用 LLM 生成公式解释（注入文档上下文）"""
        try:
            import httpx

            api_base = settings.llm_api_base
            api_key = settings.llm_api_key

            prompt = (
                "请解释以下数学公式的含义和用途：\n\n"
                f"公式: {equation_text}\n\n"
            )
            # 注入上下文
            if context:
                prompt += f"文档上下文（公式周围的文本内容，供参考）:\n{context[:400]}\n\n"
            prompt += "请用简洁的中文进行解释。"

            messages = [{"role": "user", "content": prompt}]

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": settings.llm_model,
                        "messages": messages,
                        "max_tokens": 300,
                        "temperature": 0.3,
                    },
                )
                response.raise_for_status()
                result = response.json()
                explanation = result["choices"][0]["message"]["content"]
                logger.info("公式解释生成成功")
                return explanation

        except Exception as e:
            logger.warning(f"公式解释生成失败: {e}")
            return ""


# 全局实例
_multimodal_processor = None


def get_multimodal_processor() -> MultimodalProcessor:
    """获取多模态处理器实例（单例模式）"""
    global _multimodal_processor
    if _multimodal_processor is None:
        _multimodal_processor = MultimodalProcessor()
    return _multimodal_processor