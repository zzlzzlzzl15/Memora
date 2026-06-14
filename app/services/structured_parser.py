"""
结构化文档解析服务

支持两种解析模式：
1. MinerU（优先）：高精度结构化解析，输出 content_list（含图片/表格/公式）
2. 传统解析（降级）：PyPDF2 / docx2txt 提取纯文本

MinerU 输出的 content_list 格式：
[
    {"type": "text", "text": "...", "page_idx": 0},
    {"type": "image", "img_path": "...", "caption": "...", "footnote": "...", "page_idx": 0},
    {"type": "table", "img_path": "...", "table_body": "...", "caption": "...", "footnote": "...", "page_idx": 1},
    {"type": "equation", "latex": "...", "caption": "...", "page_idx": 2},
]
"""
import os
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

from app.models.document import DocumentType
from app.services.parse_cache import get_parse_cache_service
from config.settings import settings


class StructuredContent:
    """结构化内容项"""

    TYPE_TEXT = "text"
    TYPE_IMAGE = "image"
    TYPE_TABLE = "table"
    TYPE_EQUATION = "equation"

    def __init__(
        self,
        content_type: str,
        text: str = None,
        page_idx: int = None,
        section_path: str = None,
        # 图片相关
        image_path: str = None,
        caption: str = None,
        footnote: str = None,
        neighbor_text: str = None,
        # 表格相关
        table_body: str = None,
        # 公式相关
        equation_text: str = None,
        equation_format: str = None,
    ):
        self.content_type = content_type
        self.text = text
        self.page_idx = page_idx
        self.section_path = section_path
        # 图片
        self.image_path = image_path
        self.caption = caption
        self.footnote = footnote
        self.neighbor_text = neighbor_text
        # 表格
        self.table_body = table_body
        # 公式
        self.equation_text = equation_text
        self.equation_format = equation_format

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        d = {"type": self.content_type}
        if self.text is not None:
            d["text"] = self.text
        if self.page_idx is not None:
            d["page_idx"] = self.page_idx
        if self.section_path is not None:
            d["section_path"] = self.section_path
        if self.image_path is not None:
            d["image_path"] = self.image_path
        if self.caption is not None:
            d["caption"] = self.caption
        if self.footnote is not None:
            d["footnote"] = self.footnote
        if self.neighbor_text is not None:
            d["neighbor_text"] = self.neighbor_text
        if self.table_body is not None:
            d["table_body"] = self.table_body
        if self.equation_text is not None:
            d["equation_text"] = self.equation_text
        if self.equation_format is not None:
            d["equation_format"] = self.equation_format
        return d


class StructuredParserService:
    """结构化文档解析服务"""

    def __init__(self):
        self.parse_cache = get_parse_cache_service()
        self._mineru_available = None

    @property
    def mineru_available(self) -> bool:
        """检查 MinerU 是否可用"""
        if self._mineru_available is None:
            try:
                from magic_pdf.data.data_reader_writer import FileBasedDataReader
                self._mineru_available = True
                logger.info("MinerU 解析器可用")
            except ImportError:
                self._mineru_available = False
                logger.info("MinerU 不可用，将使用传统解析器")
        return self._mineru_available

    async def parse_document(
        self,
        file_path: str,
        file_type: DocumentType,
        user_id: str,
        use_cache: bool = True,
    ) -> List[StructuredContent]:
        """
        解析文档，返回结构化内容列表

        Args:
            file_path: 文件路径
            file_type: 文件类型
            user_id: 用户 ID（用于图片保存目录）
            use_cache: 是否使用解析缓存

        Returns:
            结构化内容列表
        """
        # 尝试缓存
        if use_cache and settings.parse_cache_enabled:
            parse_config = {"mineru": settings.use_mineru, "method": settings.mineru_method}
            cached = self.parse_cache.get(file_path, parse_config)
            if cached and "content_list" in cached:
                logger.info(f"结构化解析缓存命中: {file_path}")
                return self._deserialize_content_list(cached["content_list"])

        # 选择解析策略
        if settings.use_mineru and self.mineru_available and file_type in (
            DocumentType.PDF, DocumentType.DOCX
        ):
            content_list = await self._parse_with_mineru(file_path, user_id)
        else:
            content_list = await self._parse_with_fallback(file_path, file_type)

        # 保存缓存
        if use_cache and settings.parse_cache_enabled and content_list:
            parse_config = {"mineru": settings.use_mineru, "method": settings.mineru_method}
            serialized = [c.to_dict() for c in content_list]
            self.parse_cache.set(file_path, {"content_list": serialized}, parse_config)

        return content_list

    async def _parse_with_mineru(
        self, file_path: str, user_id: str
    ) -> List[StructuredContent]:
        """
        使用 MinerU 解析文档

        MinerU 的解析操作（PDF 渲染、OCR）是 CPU/IO 密集型同步调用，
        参照 RAG-Anything processor.py 的做法（asyncio.to_thread），
        将同步解析包装到线程池中执行，避免阻塞 FastAPI 的 asyncio 事件循环。
        """
        try:
            from magic_pdf.data.data_reader_writer import FileBasedDataReader, FileBasedDataWriter
            from magic_pdf.data.dataset import PymuDocDataset
            from magic_pdf.config.enums import SupportedPdfParseMethod
            import asyncio

            logger.info(f"使用 MinerU 解析（线程池）: {file_path}")

            # 准备输出目录
            output_dir = Path(settings.upload_dir) / user_id / "mineru_output"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_dir_str = str(output_dir)

            def _sync_parse() -> List[dict]:
                """同步 MinerU 解析，运行在线程池中"""
                reader = FileBasedDataReader("")
                pdf_bytes = reader.read(file_path)
                ds = PymuDocDataset(pdf_bytes)

                # 选择解析方法
                if settings.mineru_method == "ocr":
                    ds_result = ds.apply_ocr() if ds.class_ocr_mode() else ds.apply_chat()
                elif settings.mineru_method == "txt":
                    ds_result = ds.apply_txt()
                else:  # auto
                    ds_result = ds.apply_ocr() if ds.class_ocr_mode() else ds.apply_txt()

                # 提取 content_list
                return ds_result.get_content_list(
                    FileBasedDataWriter(output_dir_str)
                )

            # 通过 asyncio.to_thread 在线程池中执行同步解析，不阻塞事件循环
            content_list_raw = await asyncio.to_thread(_sync_parse)

            # 转换为 StructuredContent（纯 CPU 操作，不需要线程池）
            content_list = self._convert_mineru_content_list(
                content_list_raw, user_id, output_dir_str
            )

            logger.info(
                f"MinerU 解析完成: {file_path}, "
                f"共 {len(content_list)} 个内容项"
            )
            return content_list

        except Exception as e:
            logger.error(f"MinerU 解析失败: {e}, 降级到传统解析器")
            return await self._parse_with_fallback(
                file_path,
                DocumentType.PDF if file_path.endswith('.pdf') else DocumentType.DOCX
            )

    def _convert_mineru_content_list(
        self,
        content_list_raw: List[Dict],
        user_id: str,
        output_dir: str,
    ) -> List[StructuredContent]:
        """
        将 MinerU 输出的 content_list 转换为 StructuredContent 列表

        改进点（对标 RAG-Anything ContextExtractor）：
        1. 从 text_level 字段推导章节路径（section_path），回填给同页的非文本内容
        2. 保留完整 content_list 原始数据（raw_content_list 属性），
           供 MultimodalProcessor 的 ContextExtractor 使用（page 模式）
        3. 记录每个 StructuredContent 在原始列表中的全局序号（list_index 属性），
           供 ContextExtractor chunk 模式使用

        MinerU content_list 格式示例：
        [
            {"type": "text", "text": "...", "text_level": 1, "page_idx": 0},
            {"type": "image", "img_path": "xxx.jpg", "caption": "...", "page_idx": 0},
            {"type": "table", "img_path": "xxx.jpg", "table_body": "...", "page_idx": 1},
            {"type": "equation", "latex": "...", "page_idx": 2},
        ]
        """
        result = []
        images_dir = Path(settings.upload_dir) / user_id / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        prev_text = None          # 前一个文本块（作为图片的 neighbor_text）
        current_section_path = None  # 当前章节路径（从 text_level 推导）
        section_stack: List[tuple] = []  # [(level, title), ...]

        for list_index, item in enumerate(content_list_raw):
            item_type = item.get("type", "text")

            if item_type == "text":
                text = item.get("text", "").strip()
                text_level = item.get("text_level")

                # 如果是标题项（text_level > 0），更新章节路径
                if text_level and isinstance(text_level, (int, float)) and int(text_level) > 0:
                    level = int(text_level)
                    # 弹出同级及更深层级的栈帧
                    section_stack = [(l, t) for l, t in section_stack if l < level]
                    section_stack.append((level, text))
                    current_section_path = " > ".join(t for _, t in section_stack)

                if text:
                    sc = StructuredContent(
                        content_type=StructuredContent.TYPE_TEXT,
                        text=text,
                        page_idx=item.get("page_idx"),
                        section_path=current_section_path,
                    )
                    # 保留在原始列表中的序号（供 chunk 模式使用）
                    sc.list_index = list_index
                    result.append(sc)
                    prev_text = text

            elif item_type == "image":
                # 规范化图片标题字段（MinerU 有两种字段名）
                raw_captions = item.get("image_caption", item.get("img_caption", []))
                if isinstance(raw_captions, str):
                    raw_captions = [raw_captions]
                caption = ", ".join(raw_captions) if raw_captions else item.get("caption", "")

                raw_footnotes = item.get("image_footnote", item.get("img_footnote", []))
                if isinstance(raw_footnotes, str):
                    raw_footnotes = [raw_footnotes]
                footnote = ", ".join(raw_footnotes) if raw_footnotes else item.get("footnote", "")

                # 复制图片到用户 images 目录
                src_path = item.get("img_path", "")
                new_image_path = self._copy_image_to_user_dir(
                    src_path, images_dir, output_dir
                )

                sc = StructuredContent(
                    content_type=StructuredContent.TYPE_IMAGE,
                    image_path=new_image_path,
                    caption=caption,
                    footnote=footnote,
                    neighbor_text=prev_text,
                    page_idx=item.get("page_idx"),
                    section_path=current_section_path,
                )
                sc.list_index = list_index
                result.append(sc)

            elif item_type == "table":
                # 规范化表格标题字段
                raw_captions = item.get("table_caption", [])
                if isinstance(raw_captions, str):
                    raw_captions = [raw_captions]
                caption = ", ".join(raw_captions) if raw_captions else item.get("caption", "")

                raw_footnotes = item.get("table_footnote", [])
                if isinstance(raw_footnotes, str):
                    raw_footnotes = [raw_footnotes]
                footnote = ", ".join(raw_footnotes) if raw_footnotes else item.get("footnote", "")

                # 复制表格截图
                src_path = item.get("img_path", "")
                new_image_path = self._copy_image_to_user_dir(
                    src_path, images_dir, output_dir
                )

                sc = StructuredContent(
                    content_type=StructuredContent.TYPE_TABLE,
                    image_path=new_image_path,
                    table_body=item.get("table_body", ""),
                    caption=caption,
                    footnote=footnote,
                    page_idx=item.get("page_idx"),
                    section_path=current_section_path,
                )
                sc.list_index = list_index
                result.append(sc)

            elif item_type == "equation":
                sc = StructuredContent(
                    content_type=StructuredContent.TYPE_EQUATION,
                    equation_text=item.get("latex", item.get("text", "")),
                    equation_format=item.get("format", "latex"),
                    caption=item.get("caption", ""),
                    page_idx=item.get("page_idx"),
                    section_path=current_section_path,
                )
                sc.list_index = list_index
                result.append(sc)

        # 将原始 content_list 挂载到解析结果上，供后续 ContextExtractor 使用
        for sc in result:
            sc.raw_content_list = content_list_raw

        return result

    def _copy_image_to_user_dir(
        self, src_path: str, images_dir: Path, output_dir: str
    ) -> str:
        """
        将图片从 MinerU 输出目录复制到用户 images 目录

        Args:
            src_path: MinerU 输出的图片路径（可能是相对路径）
            images_dir: 用户 images 目录
            output_dir: MinerU 输出目录

        Returns:
            新的图片路径
        """
        import shutil

        if not src_path:
            return ""

        # 解析路径：MinerU 输出的路径可能是相对于 output_dir 的
        full_src = Path(src_path)
        if not full_src.is_absolute():
            full_src = Path(output_dir) / src_path

        if not full_src.exists():
            logger.warning(f"图片文件不存在: {full_src}")
            return src_path

        # 生成新文件名
        new_filename = f"{uuid.uuid4()}{full_src.suffix}"
        new_path = images_dir / new_filename

        try:
            shutil.copy2(str(full_src), str(new_path))
            return str(new_path)
        except Exception as e:
            logger.warning(f"复制图片失败: {e}")
            return src_path

    async def _parse_with_fallback(
        self, file_path: str, file_type: DocumentType
    ) -> List[StructuredContent]:
        """
        使用传统解析器降级解析（PyPDF2 / docx2txt）

        将纯文本包装为 StructuredContent 列表
        """
        import PyPDF2
        import docx2txt

        logger.info(f"使用传统解析器: {file_path} (type={file_type})")

        try:
            text = ""
            if file_type in (DocumentType.TEXT, DocumentType.MARKDOWN):
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
            elif file_type == DocumentType.PDF:
                with open(file_path, "rb") as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    for page in pdf_reader.pages:
                        text += (page.extract_text() or "") + "\n"
            elif file_type == DocumentType.DOCX:
                text = docx2txt.process(file_path) or ""
            else:
                text = ""

            if text.strip():
                return [StructuredContent(
                    content_type=StructuredContent.TYPE_TEXT,
                    text=text.strip(),
                )]
            return []

        except Exception as e:
            logger.error(f"传统解析器失败: {e}")
            return []

    def _deserialize_content_list(self, raw_list: List[Dict]) -> List[StructuredContent]:
        """从缓存反序列化 content_list"""
        result = []
        for item in raw_list:
            sc = StructuredContent(
                content_type=item.get("type", "text"),
                text=item.get("text"),
                page_idx=item.get("page_idx"),
                section_path=item.get("section_path"),
                image_path=item.get("image_path"),
                caption=item.get("caption"),
                footnote=item.get("footnote"),
                neighbor_text=item.get("neighbor_text"),
                table_body=item.get("table_body"),
                equation_text=item.get("equation_text"),
                equation_format=item.get("equation_format"),
            )
            result.append(sc)
        return result


# 全局实例
_structured_parser_service = None


def get_structured_parser_service() -> StructuredParserService:
    """获取结构化解析服务实例（单例模式）"""
    global _structured_parser_service
    if _structured_parser_service is None:
        _structured_parser_service = StructuredParserService()
    return _structured_parser_service