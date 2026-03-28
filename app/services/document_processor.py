import os
import uuid
from typing import List, Dict, Any, Optional
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
    
    async def extract_text_from_file(self, file_path: str, file_type: DocumentType) -> str:
        """从文件中提取文本内容"""
        try:
            if file_type == DocumentType.TEXT or file_type == DocumentType.MARKDOWN:
                return await self._extract_text_from_txt(file_path)
            elif file_type == DocumentType.PDF:
                return await self._extract_text_from_pdf(file_path)
            elif file_type == DocumentType.DOCX:
                return await self._extract_text_from_docx(file_path)
            else:
                raise ValueError(f"不支持的文件类型: {file_type}")
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
    
    def split_text_into_chunks(self, text: str, document_id: str) -> List[DocumentChunk]:
        """将文本分割成块（使用LangChain Text Splitters）"""
        if not text or not text.strip():
            return []

        raw_text = text
        # 使用LangChain递归字符分片器进行分割
        parts = self.text_splitter.split_text(raw_text)

        chunks: List[DocumentChunk] = []
        cursor = 0
        chunk_index = 0

        for part in parts:
            content = part.strip()
            if not content:
                continue

            # 计算起止位置：优先从上次游标处搜索，避免重复匹配到更早位置
            start_pos = raw_text.find(content, max(0, cursor))
            if start_pos == -1:
                # 若因分隔处理导致前后空白差异，退化到全局搜索
                start_pos = raw_text.find(content)
            # 兜底：若仍未找到，则以游标位置作为近似起点
            if start_pos == -1:
                start_pos = cursor
            end_pos = start_pos + len(content)

            # 更新游标，考虑重叠，避免始终向后推进过快
            cursor = max(cursor, end_pos - self.chunk_overlap)

            chunk = DocumentChunk(
                chunk_id=f"{document_id}_chunk_{chunk_index}",
                document_id=document_id,
                content=content,
                chunk_index=chunk_index,
                start_pos=start_pos,
                end_pos=end_pos,
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

        logger.info(f"文档 {document_id} 使用LangChain分割成 {len(chunks)} 个块")
        return chunks
    
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