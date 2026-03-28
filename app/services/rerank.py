from typing import List, Tuple
from loguru import logger
from functools import lru_cache
import dashscope
from http import HTTPStatus
from config.settings import settings

class RerankService:
    """Rerank服务 - 使用通义千问Rerank API对检索结果进行重排序"""
    
    def __init__(self):
        self.model_name = "qwen3-rerank"
        self.api_key = settings.dashscope_api_key or settings.openai_api_key
        if self.api_key:
            dashscope.api_key = self.api_key
            logger.info(f"Rerank服务初始化完成，使用模型: {self.model_name}")
        else:
            logger.warning("未配置DASHSCOPE_API_KEY，Rerank功能将使用降级策略")
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        使用通义千问Rerank API对文档列表进行重排序
        
        Args:
            query: 查询文本
            documents: 候选文档列表
            top_k: 返回top K个结果
        
        Returns:
            List of (原始索引, rerank分数) 元组,按分数降序排列
        """
        if not documents:
            return []
        
        if not self.api_key:
            logger.warning("未配置API Key，使用原始顺序")
            return [(i, 1.0) for i in range(min(top_k, len(documents)))]
        
        try:
            # 调用通义千问Rerank API
            resp = dashscope.TextReRank.call(
                model=self.model_name,
                query=query,
                documents=documents,
                top_n=min(top_k, len(documents)),
                return_documents=False  # 只返回索引和分数
            )
            
            if resp.status_code == HTTPStatus.OK:
                results = resp.output.results
                # 提取(原始索引, 分数)对
                indexed_scores = [
                    (result.index, float(result.relevance_score)) 
                    for result in results
                ]
                
                logger.info(f"Rerank完成: 从{len(documents)}个文档中选出top {len(indexed_scores)}个")
                logger.debug(f"Top rerank scores: {[s for _, s in indexed_scores[:3]]}")
                
                return indexed_scores
            else:
                logger.error(f"Rerank API调用失败: {resp.code} - {resp.message}")
                # 降级为返回原始顺序
                return [(i, 1.0) for i in range(min(top_k, len(documents)))]
            
        except Exception as e:
            logger.error(f"Rerank调用异常: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            # 降级为返回原始顺序
            return [(i, 1.0) for i in range(min(top_k, len(documents)))]


# 全局rerank服务实例
_rerank_service = None

@lru_cache(maxsize=1)
def get_rerank_service() -> RerankService:
    """获取Rerank服务实例（单例模式）"""
    global _rerank_service
    if _rerank_service is None:
        _rerank_service = RerankService()
    return _rerank_service
