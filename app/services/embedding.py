from typing import List, Union, Dict, Any
import os
from sentence_transformers import SentenceTransformer
import numpy as np
from config.settings import settings
from loguru import logger
import asyncio
from functools import lru_cache
import hashlib

class EmbeddingService:
    """向量化服务"""
    
    def __init__(self):
        self.model = None
        self.provider = "sentence"  # sentence | openai | fallback
        self.openai_client = None
        self.use_fallback = False
        # 稀疏嵌入（BM42）
        self.sparse_model = None
        self.sparse_enabled = bool(settings.use_sparse_bm42)
        self._load_model()
        self._load_sparse_model()
    
    def _load_model(self):
        """加载向量化模型"""
        try:
            # OpenAI 模型前缀：openai/
            if settings.embedding_model.startswith("openai/"):
                # 优先使用 DASHSCOPE_API_KEY，其次 OPENAI_API_KEY
                api_key = settings.dashscope_api_key or settings.openai_api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise RuntimeError("缺少嵌入API Key (DASHSCOPE_API_KEY/OPENAI_API_KEY)")
                try:
                    from openai import OpenAI
                except Exception as e:
                    raise RuntimeError(f"未安装openai包或导入失败: {e}")
                # 使用阿里百炼兼容模式的base_url
                base_url = settings.embedding_api_base or os.getenv("EMBEDDING_API_BASE")
                self.openai_client = OpenAI(api_key=api_key, base_url=base_url)
                self.provider = "openai"
                self.model = settings.embedding_model  # 保存模型标识
                logger.info(f"成功加载OpenAI嵌入模型: {settings.embedding_model} (base_url={base_url})")
            else:
                # Sentence-Transformers 本地模型
                self.model = SentenceTransformer(settings.embedding_model)
                self.provider = "sentence"
                logger.info(f"成功加载向量化模型: {settings.embedding_model}")
        except Exception as e:
            logger.warning(f"加载向量化模型失败，启用离线回退向量化: {e}")
            self.use_fallback = True
            self.provider = "fallback"
            self.model = None

    def _load_sparse_model(self):
        """加载稀疏嵌入模型（BM42）"""
        if not self.sparse_enabled:
            return
        try:
            from fastembed import SparseTextEmbedding
        except Exception as e:
            logger.warning(f"未安装 fastembed 或导入失败，禁用稀疏嵌入: {e}")
            self.sparse_enabled = False
            return
        try:
            # 使用本地缓存，不连接HuggingFace
            # 明确设置trust_remote_code=False以避免网络连接
            self.sparse_model = SparseTextEmbedding(
                model_name=settings.sparse_embedding_model,
                cache_dir=settings.fastembed_cache_path,
                providers=["CPUExecutionProvider"],  # 仅使用CPU
                trust_remote_code=False,  # 不信任远程代码，强制使用本地缓存
                local_files_only=True  # 仅使用本地文件，不尝试下载
            )
            logger.info(f"成功加载稀疏嵌入模型: {settings.sparse_embedding_model}")
        except Exception as e:
            logger.warning(f"加载稀疏嵌入模型失败，禁用稀疏模式: {e}")
            self.sparse_enabled = False

    async def encode_text(self, text: str) -> List[float]:
        """对单个文本进行向量化"""
        if not text or not text.strip():
            raise ValueError("文本内容不能为空")
        
        try:
            # 在线程池中执行向量化，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, 
                self._encode_single_text, 
                text.strip()
            )
            return embedding.tolist()
        except Exception as e:
            logger.error(f"文本向量化失败: {e}")
            raise e

    async def encode_texts(self, texts: List[str]) -> List[List[float]]:
        """对多个文本进行批量向量化"""
        if not texts:
            return []
        
        # 过滤空文本
        valid_texts = [text.strip() for text in texts if text and text.strip()]
        if not valid_texts:
            raise ValueError("没有有效的文本内容")
        
        try:
            # 在线程池中执行批量向量化
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None, 
                self._encode_multiple_texts, 
                valid_texts
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"批量文本向量化失败: {e}")
            raise e

    async def encode_sparse_text(self, text: str) -> Dict[str, Any]:
        """对单个文本进行稀疏向量化，返回 {indices, values}"""
        if not text or not text.strip():
            raise ValueError("文本内容不能为空")
        if not self.sparse_enabled:
            raise RuntimeError("稀疏嵌入未启用或模型加载失败")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._encode_sparse_single, text.strip())
            return result
        except Exception as e:
            logger.error(f"文本稀疏向量化失败: {e}")
            raise e

    async def encode_sparse_texts(self, texts: List[str]) -> List[Dict[str, Any]]:
        """批量稀疏向量化，返回 [{indices, values}, ...]"""
        if not texts:
            return []
        if not self.sparse_enabled:
            raise RuntimeError("稀疏嵌入未启用或模型加载失败")
        valid_texts = [t.strip() for t in texts if t and t.strip()]
        if not valid_texts:
            raise ValueError("没有有效的文本内容")
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, self._encode_sparse_multiple, valid_texts)
            return results
        except Exception as e:
            logger.error(f"批量稀疏向量化失败: {e}")
            raise e
    
    def _encode_single_text(self, text: str) -> np.ndarray:
        """同步方式对单个文本进行向量化"""
        if not self.use_fallback and self.provider == "openai" and self.openai_client is not None:
            # 移除前缀，OpenAI API 仅接受裸模型名
            model_name = settings.embedding_model.replace("openai/", "")
            resp = self.openai_client.embeddings.create(
                model=model_name,
                input=text,
                dimensions=settings.vector_size,
                encoding_format="float"
            )
            vec = np.array(resp.data[0].embedding, dtype=np.float32)
            return vec
        if not self.use_fallback and self.provider == "sentence" and self.model is not None:
            return self.model.encode(text, convert_to_numpy=True)
        # 回退：使用改进的基于特征（支持中文）的本地向量化，保证维度与settings.vector_size一致
        return self._fallback_encode_text(text)

    def _encode_multiple_texts(self, texts: List[str]) -> np.ndarray:
        """同步方式对多个文本进行批量向量化"""
        if not self.use_fallback and self.provider == "openai" and self.openai_client is not None:
            model_name = settings.embedding_model.replace("openai/", "")
            # 远程提供商（如 DashScope 兼容 OpenAI）通常限制批量大小≤10
            max_batch = 10
            vectors = []
            for i in range(0, len(texts), max_batch):
                batch = texts[i:i + max_batch]
                resp = self.openai_client.embeddings.create(
                    model=model_name,
                    input=batch,
                    dimensions=settings.vector_size,
                    encoding_format="float"
                )
                vectors.extend(
                    [np.array(item.embedding, dtype=np.float32) for item in resp.data]
                )
            return np.vstack(vectors)
        if not self.use_fallback and self.provider == "sentence" and self.model is not None:
            return self.model.encode(texts, convert_to_numpy=True)
        # 回退批量
        vectors = [self._fallback_encode_text(t) for t in texts]
        return np.vstack(vectors)

    def _encode_sparse_single(self, text: str) -> Dict[str, Any]:
        """同步方式对单个文本进行稀疏向量化"""
        if self.sparse_model is None:
            raise RuntimeError("稀疏嵌入模型未加载")
        # fastembed 返回生成器，每个元素包含 indices/values
        embeddings = list(self.sparse_model.embed([text]))
        if not embeddings:
            return {"indices": [], "values": []}
        emb = embeddings[0]
        return {"indices": list(getattr(emb, "indices", [])), "values": list(getattr(emb, "values", []))}

    def _encode_sparse_multiple(self, texts: List[str]) -> List[Dict[str, Any]]:
        """同步方式对多个文本进行稀疏向量化"""
        if self.sparse_model is None:
            raise RuntimeError("稀疏嵌入模型未加载")
        results: List[Dict[str, Any]] = []
        for emb in self.sparse_model.embed(texts):
            results.append({
                "indices": list(getattr(emb, "indices", [])),
                "values": list(getattr(emb, "values", [])),
            })
        return results
    
    def _is_cjk(self, ch: str) -> bool:
        """判断字符是否为中文/CJK"""
        code = ord(ch)
        return (
            0x4E00 <= code <= 0x9FFF or    # CJK Unified Ideographs
            0x3400 <= code <= 0x4DBF or    # CJK Unified Ideographs Extension A
            0x20000 <= code <= 0x2A6DF     # CJK Unified Ideographs Extension B (partial)
        )
    
    def _extract_features(self, text: str) -> List[str]:
        """为回退向量化提取特征：
        - 英文等使用空白分词
        - 中文/无空白的连续文本使用字符3-gram滑动窗口
        """
        tokens = text.split()
        cjk_count = sum(1 for c in text if self._is_cjk(c))
        # 当包含中文或空白分词效果很差（≤1个token）时，使用字符3-gram
        if cjk_count > 0 or len(tokens) <= 1:
            chars = [c for c in text if not c.isspace()]
            n = 3
            features: List[str] = []
            if len(chars) >= n:
                for i in range(len(chars) - n + 1):
                    features.append(''.join(chars[i:i+n]))
            elif len(chars) > 0:
                # 文本过短时，退化为单特征
                features.append(''.join(chars))
            else:
                features = []
        else:
            features = tokens
        # 限制特征数量，避免过长文本导致计算过重
        return features[:1000]
    
    def _fallback_encode_text(self, text: str) -> np.ndarray:
        """离线回退嵌入：基于特征哈希的固定维度向量（支持中文）"""
        dim = settings.vector_size
        vec = np.zeros(dim, dtype=np.float32)
        features = self._extract_features(text)
        if not features:
            return vec
        for feat in features:
            # 使用MD5哈希，映射到维度索引
            h = int(hashlib.md5(feat.encode('utf-8')).hexdigest(), 16)
            idx = h % dim
            # 按特征长度累加，减少碰撞影响
            vec[idx] += 1.0 + (len(feat) % 3) * 0.1
        # 归一化
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec
    
    def get_vector_dimension(self) -> int:
        """获取向量维度"""
        return settings.vector_size
    
    async def compute_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度"""
        try:
            embedding1 = await self.encode_text(text1)
            embedding2 = await self.encode_text(text2)
            
            # 计算余弦相似度
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
        except Exception as e:
            logger.error(f"计算文本相似度失败: {e}")
            raise e

# 全局向量化服务实例
_embedding_service = None

@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """获取向量化服务实例（单例模式）"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service