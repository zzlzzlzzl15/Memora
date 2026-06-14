"""
语义分块服务

基于语义相似度的智能分块策略，替代固定字符分块。
流程：按段落/句子初步分割 → 滑动窗口计算相邻片段语义相似度 →
     相似度低于阈值时作为分块边界 → 合并过小的片段

参照方案 3.6：当 chunk_strategy=semantic 时启用，降级到固定字符分块。
"""

import re
from typing import List, Optional, Dict, Any
from loguru import logger
from config.settings import settings


class SemanticChunker:
    """基于语义相似度的文本分块器"""

    def __init__(
        self,
        embedding_service=None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        semantic_threshold: float = 0.5,
        min_chunk_size: int = 100,
    ):
        """
        Args:
            embedding_service: 嵌入服务，用于计算语义相似度
            chunk_size: 目标块大小（字符数）
            chunk_overlap: 块重叠字符数
            semantic_threshold: 语义相似度阈值，低于此值则切分
            min_chunk_size: 最小块大小，低于此值则与相邻块合并
        """
        self.embedding_service = embedding_service
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.semantic_threshold = semantic_threshold
        self.min_chunk_size = min_chunk_size

    @property
    def available(self) -> bool:
        """语义分块是否可用（需要嵌入服务）"""
        return self.embedding_service is not None

    def split_text(self, text: str) -> List[str]:
        """
        对文本执行语义分块

        Args:
            text: 原始文本

        Returns:
            分块后的文本列表
        """
        if not text or not text.strip():
            return []

        if not self.available:
            logger.warning("嵌入服务不可用，降级到固定字符分块")
            return self._fallback_split(text)

        # Step 1: 按段落/句子初步分割
        sentences = self._split_into_sentences(text)
        if len(sentences) <= 1:
            return [text] if text.strip() else []

        # Step 2: 计算相邻句子的语义相似度
        similarities = self._compute_similarities(sentences)

        # Step 3: 根据相似度确定分块边界
        chunks = self._merge_by_similarity(sentences, similarities)

        # Step 4: 合并过小的块
        chunks = self._merge_small_chunks(chunks)

        logger.info(
            f"语义分块完成: {len(sentences)} 个句子 → {len(chunks)} 个块"
        )
        return chunks

    def _split_into_sentences(self, text: str) -> List[str]:
        """
        将文本按句子分割

        支持：中英文句号、问号、感叹号、换行分段
        """
        # 按换行分段
        paragraphs = re.split(r'\n\s*\n', text)

        sentences = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # 在段落内按中英文标点分句
            # 保留分隔符
            parts = re.split(r'((?<=[。！？.!?])\s*)', para)
            # 重新拼接分隔符
            current = ""
            for part in parts:
                current += part
                # 如果当前片段以句末标点结束，作为一个句子
                if re.search(r'[。！？.!?]\s*$', current):
                    s = current.strip()
                    if s:
                        sentences.append(s)
                    current = ""
            # 剩余部分
            if current.strip():
                sentences.append(current.strip())

        return sentences

    def _compute_similarities(self, sentences: List[str]) -> List[float]:
        """
        计算相邻句子间的语义相似度

        Returns:
            相似度列表，长度 = len(sentences) - 1
        """
        import asyncio
        import numpy as np

        similarities = []
        # 批量编码所有句子
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在异步上下文中，创建任务
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    embeddings = loop.run_in_executor(
                        executor,
                        lambda: asyncio.run(self.embedding_service.encode_texts(sentences))
                    )
                    embeddings = asyncio.get_event_loop().run_until_complete(embeddings)
            else:
                embeddings = asyncio.run(self.embedding_service.encode_texts(sentences))
        except RuntimeError:
            # 无法获取事件循环，同步方式
            embeddings = asyncio.run(self.embedding_service.encode_texts(sentences))

        if not embeddings or len(embeddings) != len(sentences):
            # 编码失败，返回均匀相似度（即不做语义切分）
            return [1.0] * (len(sentences) - 1)

        # 计算余弦相似度
        emb_array = np.array(embeddings)
        norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        normalized = emb_array / norms

        for i in range(len(sentences) - 1):
            sim = float(np.dot(normalized[i], normalized[i + 1]))
            similarities.append(sim)

        return similarities

    def _merge_by_similarity(
        self, sentences: List[str], similarities: List[float]
    ) -> List[str]:
        """
        根据语义相似度确定分块边界并合并句子

        相似度低于阈值的地方是分块边界
        """
        chunks = []
        current_sentences = [sentences[0]]
        current_length = len(sentences[0])

        for i, sim in enumerate(similarities):
            next_sentence = sentences[i + 1]
            next_length = len(next_sentence)

            # 判断是否需要切分：相似度低于阈值 或 当前块已超过目标大小
            should_split = (
                sim < self.semantic_threshold
                or current_length + next_length > self.chunk_size * 1.5
            )

            if should_split and current_length >= self.min_chunk_size:
                # 切分
                chunks.append(" ".join(current_sentences))
                current_sentences = [next_sentence]
                current_length = next_length
            else:
                # 合并
                current_sentences.append(next_sentence)
                current_length += next_length

        # 添加最后一块
        if current_sentences:
            chunks.append(" ".join(current_sentences))

        return chunks

    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """
        合并过小的块，确保每个块至少达到 min_chunk_size
        """
        if not chunks:
            return chunks

        merged = []
        i = 0
        while i < len(chunks):
            current = chunks[i]
            # 如果当前块太小，尝试与下一块合并
            while (
                i + 1 < len(chunks)
                and len(current) < self.min_chunk_size
                and len(current) + len(chunks[i + 1]) <= self.chunk_size * 1.5
            ):
                i += 1
                current = current + " " + chunks[i]
            merged.append(current)
            i += 1

        return merged

    def _fallback_split(self, text: str) -> List[str]:
        """
        降级策略：固定字符分块

        当嵌入服务不可用时使用
        """
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - self.chunk_overlap
        return chunks


def get_semantic_chunker(embedding_service=None) -> SemanticChunker:
    """获取语义分块器实例"""
    return SemanticChunker(
        embedding_service=embedding_service,
        chunk_size=getattr(settings, 'chunk_size', 500),
        chunk_overlap=getattr(settings, 'chunk_overlap', 50),
        semantic_threshold=getattr(settings, 'semantic_threshold', 0.5),
        min_chunk_size=getattr(settings, 'min_chunk_size', 100),
    )
