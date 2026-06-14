import os
import uuid
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import aiofiles
from loguru import logger

# 文档解析库
import PyPDF2
import docx2txt
import pandas as pd
from io import BytesIO
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.models.document import DocumentType, DocumentChunk
from app.services.parse_cache import get_parse_cache_service
from app.services.semantic_chunker import get_semantic_chunker
from app.services.context_extractor import get_context_extractor, ContextExtractor
from config.settings import settings

class DocumentProcessor:
    """文档处理服务"""
    
    def __init__(self):
        # 读取配置的分块参数（可通过环境变量覆盖）
        self.chunk_size = settings.text_chunk_size
        self.chunk_overlap = settings.text_chunk_overlap
        # 统一使用LangChain的递归字符分片器，兼容中英文与常见分隔符
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "，", "；", "：", " ", ""]
        )
        # 解析缓存服务
        self.parse_cache = get_parse_cache_service()
        # 语义分块策略：fixed 或 semantic
        self.chunk_strategy = getattr(settings, 'chunk_strategy', 'fixed')
        # 语义分块器（延迟初始化，需要 embedding_service）
        self._semantic_chunker = None
        # 上下文提取器（延迟初始化）
        self._context_extractor: Optional[ContextExtractor] = None
    
    async def save_uploaded_file(self, file_content: bytes, filename: str, user_id: str) -> str:
        """保存上传的文件"""
        try:
            # 创建用户专属目录
            user_dir = Path(settings.upload_dir) / user_id
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成唯一文件名
            file_extension = Path(filename).suffix
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = user_dir / unique_filename
            
            # 异步保存文件
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
            
            logger.info(f"文件保存成功: {file_path}")
            return str(file_path)
        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            raise e
    
    async def extract_text_from_file(self, file_path: str, file_type: DocumentType, use_cache: bool = True) -> str:
        """从文件中提取文本内容（支持解析缓存）"""
        try:
            # 尝试从缓存获取
            if use_cache:
                parse_config = {"chunk_size": self.chunk_size, "chunk_overlap": self.chunk_overlap}
                cached = self.parse_cache.get(file_path, parse_config)
                if cached and "extracted_text" in cached:
                    logger.info(f"解析缓存命中: {file_path}")
                    return cached["extracted_text"]

            if file_type == DocumentType.TEXT or file_type == DocumentType.MARKDOWN:
                text = await self._extract_text_from_txt(file_path)
            elif file_type == DocumentType.PDF:
                text = await self._extract_text_from_pdf(file_path)
            elif file_type == DocumentType.DOCX:
                text = await self._extract_text_from_docx(file_path)
            else:
                raise ValueError(f"不支持的文件类型: {file_type}")

            # 保存到缓存
            if use_cache and text:
                parse_config = {"chunk_size": self.chunk_size, "chunk_overlap": self.chunk_overlap}
                self.parse_cache.set(file_path, {"extracted_text": text}, parse_config)

            return text
        except Exception as e:
            logger.error(f"提取文本失败: {e}")
            raise e
    
    async def _extract_text_from_txt(self, file_path: str) -> str:
        """从文本文件提取内容"""
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
        return content
    
    async def _extract_text_from_pdf(self, file_path: str) -> str:
        """从PDF文件提取文本"""
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    async def _extract_text_from_docx(self, file_path: str) -> str:
        """从DOCX文件提取文本"""
        text = docx2txt.process(file_path)
        return text
    
    def split_text_into_chunks(self, text: str, document_id: str, embedding_service=None) -> List[DocumentChunk]:
        """将文本分割成块（支持固定/语义分块 + 上下文感知）"""
        if not text or not text.strip():
            return []

        raw_text = text
        # 提取章节结构信息
        section_map = self._extract_section_map(raw_text)

        # 根据策略选择分块方式
        if self.chunk_strategy == 'semantic' and embedding_service is not None:
            parts = self._semantic_split(raw_text, embedding_service)
        else:
            # 默认：固定字符分块
            parts = self.text_splitter.split_text(raw_text)

        chunks: List[DocumentChunk] = []
        cursor = 0
        chunk_index = 0

        for part in parts:
            content = part.strip()
            if not content:
                continue

            # 计算起止位置
            start_pos = raw_text.find(content, max(0, cursor))
            if start_pos == -1:
                start_pos = raw_text.find(content)
            if start_pos == -1:
                start_pos = cursor
            end_pos = start_pos + len(content)

            # 更新游标
            cursor = max(cursor, end_pos - self.chunk_overlap)

            # 识别该块所在的章节
            section_path, section_title = self._find_section_for_position(
                section_map, start_pos
            )

            chunk = DocumentChunk(
                chunk_id=f"{document_id}_chunk_{chunk_index}",
                document_id=document_id,
                content=content,
                chunk_index=chunk_index,
                start_pos=start_pos,
                end_pos=end_pos,
                section_path=section_path,
                section_title=section_title,
                metadata={
                    "length": len(content),
                    "word_count": len(content.split()),
                    "splitter": "RecursiveCharacterTextSplitter",
                    "chunk_size": self.chunk_size,
                    "chunk_overlap": self.chunk_overlap,
                }
            )
            chunks.append(chunk)
            chunk_index += 1

        # 填充上下文信息（context_before/context_after/total_chunks）
        # 使用 ContextExtractor chunk 模式，遵从 settings 中的 context_window 配置
        total = len(chunks)
        if self._context_extractor is None:
            self._context_extractor = get_context_extractor(context_mode="chunk")

        # 直接提取 chunk 内容列表，供 ContextExtractor 使用
        chunk_contents = [c.content for c in chunks]

        for i, chunk in enumerate(chunks):
            chunk.total_chunks = total
            item_info = {"index": i}

            # 使用 ContextExtractor 提取相邻 chunk 上下文
            ctx_raw = self._context_extractor.extract_context(
                content_source=chunk_contents,
                current_item_info=item_info,
                content_format="text_chunks",
            )

            # 兼容原有字段格式：context_before = 前块末尾，context_after = 后块开头
            context_window = getattr(settings, "context_window", 1)
            # 取前一个块的末尾
            if i > 0:
                prev_content = chunks[i - 1].content
                limit = getattr(settings, "max_context_tokens", 2000)
                chunk.context_before = prev_content[-limit:] if len(prev_content) > limit else prev_content
            # 取后一个块的开头
            if i < total - 1:
                nxt_content = chunks[i + 1].content
                limit = getattr(settings, "max_context_tokens", 2000)
                chunk.context_after = nxt_content[:limit] if len(nxt_content) > limit else nxt_content

        logger.info(f"文档 {document_id} 使用LangChain分割成 {total} 个块（含上下文信息）")
        return chunks

    def _extract_section_map(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本中提取章节结构
        
        识别 Markdown 风格的标题（# / ## / ###）和数字编号标题（1. / 1.1 / 1.1.1），
        返回 [{title, level, path, position}, ...]
        """
        import re
        sections = []
        # 当前层级栈，用于构建路径
        stack = []  # [(level, title), ...]

        for line_match in re.finditer(r'^(#{1,6})\s+(.+)$', text, re.MULTILINE):
            level = len(line_match.group(1))
            title = line_match.group(2).strip()
            position = line_match.start()
            # 更新层级栈
            stack = [(l, t) for l, t in stack if l < level]
            stack.append((level, title))
            # 构建路径
            path = " > ".join(t for _, t in stack)
            sections.append({
                "title": title,
                "level": level,
                "path": path,
                "position": position,
            })

        # 也识别数字编号标题（如 "1. xxx", "1.1 xxx", "1.1.1 xxx"）
        for line_match in re.finditer(r'^(\d+(?:\.\d+)*)\s+(.+)$', text, re.MULTILINE):
            numbering = line_match.group(1)
            title = line_match.group(2).strip()
            position = line_match.start()
            level = numbering.count('.') + 1
            stack = [(l, t) for l, t in stack if l < level]
            stack.append((level, f"{numbering} {title}"))
            path = " > ".join(t for _, t in stack)
            sections.append({
                "title": f"{numbering} {title}",
                "level": level,
                "path": path,
                "position": position,
            })

        # 按位置排序
        sections.sort(key=lambda s: s["position"])
        return sections

    def _find_section_for_position(
        self, section_map: List[Dict[str, Any]], position: int
    ) -> tuple:
        """
        根据文本位置查找所属章节
        
        Returns:
            (section_path, section_title) 或 (None, None)
        """
        current_path = None
        current_title = None
        for section in section_map:
            if section["position"] <= position:
                current_path = section["path"]
                current_title = section["title"]
            else:
                break
        return current_path, current_title

    def _semantic_split(self, text: str, embedding_service) -> List[str]:
        """
        使用语义分块策略分割文本

        Args:
            text: 原始文本
            embedding_service: 嵌入服务实例

        Returns:
            分块后的文本列表
        """
        try:
            if self._semantic_chunker is None:
                self._semantic_chunker = get_semantic_chunker(embedding_service)

            # 更新 embedding_service（可能不同请求使用不同实例）
            self._semantic_chunker.embedding_service = embedding_service

            parts = self._semantic_chunker.split_text(text)
            if parts:
                logger.info(
                    f"语义分块生成 {len(parts)} 个块 "
                    f"(阈值={self._semantic_chunker.semantic_threshold})"
                )
                return parts
            else:
                logger.warning("语义分块返回空结果，降级到固定字符分块")
                return self.text_splitter.split_text(text)
        except Exception as e:
            logger.warning(f"语义分块失败，降级到固定字符分块: {e}")
            return self.text_splitter.split_text(text)

    def detect_file_type(self, filename: str) -> DocumentType:
        """根据文件扩展名检测文件类型"""
        extension = Path(filename).suffix.lower()
        
        type_mapping = {
            '.txt': DocumentType.TEXT,
            '.md': DocumentType.MARKDOWN,
            '.pdf': DocumentType.PDF,
            '.docx': DocumentType.DOCX,
            '.doc': DocumentType.DOCX,
        }
        
        return type_mapping.get(extension, DocumentType.OTHER)
    
    def validate_file_type(self, filename: str) -> bool:
        """验证文件类型是否支持"""
        extension = Path(filename).suffix.lower()
        return extension in settings.allowed_file_types
    
    def validate_file_size(self, file_size: int) -> bool:
        """验证文件大小"""
        return file_size <= settings.max_file_size
    
    async def delete_file(self, file_path: str) -> bool:
        """删除文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"文件删除成功: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False
    
    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """获取文件元数据"""
        try:
            file_stat = os.stat(file_path)
            return {
                "file_size": file_stat.st_size,
                "created_time": file_stat.st_ctime,
                "modified_time": file_stat.st_mtime,
                "file_extension": Path(file_path).suffix.lower()
            }
        except Exception as e:
            logger.error(f"获取文件元数据失败: {e}")
            return {}

# 全局文档处理器实例
_document_processor = None

def get_document_processor() -> DocumentProcessor:
    """获取文档处理器实例（单例模式）"""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor