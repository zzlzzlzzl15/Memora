"""
混合融合服务

将向量检索结果与知识图谱检索结果进行融合、去重、加权排序、Token截断。
参照 RAG-Anything/LightRAG 的查询模式设计。

支持的查询模式：
- vector: 纯向量检索（Memora 现有模式）
- local: Neo4j 实体检索 → 局部子图
- global: Neo4j 关系遍历 → 全局推理
- hybrid: 向量 + 实体 + 关系混合
- mix: hybrid + naive 全量融合（推荐，参照 LightRAG 默认模式）

参照方案 3.4：混合融合与筛选机制
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from loguru import logger
from config.settings import settings


@dataclass
class ContextCandidate:
    """上下文候选项"""
    content: str
    source_type: str       # direct_entity_match / vector_rerank_top / relation_description / graph_expansion
    weight: float          # 来源权重
    chunk_id: Optional[str] = None
    doc_id: Optional[str] = None
    entity_name: Optional[str] = None   # 仅实体类型有
    relation_type: Optional[str] = None  # 仅关系类型有


@dataclass
class GraphSearchResult:
    """图谱检索结果"""
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relations: List[Dict[str, Any]] = field(default_factory=list)
    related_chunks: List[Dict[str, Any]] = field(default_factory=list)


class HybridResultFusion:
    """参照 LightRAG 的 kg_query，实现向量+图谱结果融合"""

    SOURCE_WEIGHTS = {
        "direct_entity_match": 3.0,   # 直接匹配实体（最高权重）
        "vector_rerank_top": 2.0,     # 向量 Rerank 高分结果
        "relation_description": 1.5,  # 关系推理文本
        "graph_expansion": 1.0,       # 图谱 1~2度扩展结果
    }

    def __init__(self, max_context_tokens: int = 4000):
        """
        Args:
            max_context_tokens: LLM 上下文 Token 上限
        """
        self.max_context_tokens = max_context_tokens

    async def fuse_results(
        self,
        vector_results: List[Any],    # SearchResult 列表
        graph_results: Optional[GraphSearchResult] = None,
        query_mode: str = "vector",
    ) -> str:
        """
        融合向量检索和图谱检索结果

        Args:
            vector_results: Qdrant 向量检索结果
            graph_results: Neo4j 图谱检索结果
            query_mode: 查询模式

        Returns:
            融合后的上下文字符串，可直接拼入 LLM Prompt
        """
        candidates = []

        # ─── 路径A: 向量检索结果 ─────────────────────────────
        if query_mode in ("vector", "hybrid", "mix"):
            for r in vector_results:
                content = getattr(r, 'content', str(r))
                chunk_id = getattr(r, 'metadata', {}).get('chunk_id') if hasattr(r, 'metadata') else None
                doc_id = getattr(r, 'document_id', None)
                score = getattr(r, 'score', 0)

                # 向量结果权重根据分数调整
                base_weight = self.SOURCE_WEIGHTS["vector_rerank_top"]
                adjusted_weight = base_weight * (0.5 + score * 0.5)  # 0.5x ~ 1x 调整

                candidates.append(ContextCandidate(
                    content=content,
                    source_type="vector_rerank_top",
                    weight=adjusted_weight,
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                ))

        # ─── 路径B: 图谱检索结果 ─────────────────────────────
        if graph_results and query_mode in ("local", "global", "hybrid", "mix"):
            # 实体描述
            for entity in graph_results.entities:
                name = entity.get("entity_name", "")
                etype = entity.get("entity_type", "")
                desc = entity.get("description", "")

                content = f"[实体] {name} ({etype})"
                if desc:
                    content += f": {desc}"

                candidates.append(ContextCandidate(
                    content=content,
                    source_type="direct_entity_match",
                    weight=self.SOURCE_WEIGHTS["direct_entity_match"],
                    entity_name=name,
                ))

            # 关系描述
            for rel in graph_results.relations:
                source = rel.get("source", "")
                target = rel.get("target", "")
                rtype = rel.get("relation_type", "")
                desc = rel.get("description", "")

                content = f"[关系] {source} ←{rtype}→ {target}"
                if desc:
                    content += f": {desc}"

                candidates.append(ContextCandidate(
                    content=content,
                    source_type="relation_description",
                    weight=self.SOURCE_WEIGHTS["relation_description"],
                    relation_type=rtype,
                ))

            # 图谱关联文档块
            for chunk in graph_results.related_chunks:
                content = chunk.get("content", "")
                if content:
                    candidates.append(ContextCandidate(
                        content=content,
                        source_type="graph_expansion",
                        weight=self.SOURCE_WEIGHTS["graph_expansion"],
                        chunk_id=chunk.get("chunk_id"),
                        doc_id=chunk.get("doc_id"),
                    ))

        if not candidates:
            return ""

        # ─── Step 2: 去重 ──────────────────────────────────────
        deduped = self._deduplicate(candidates)

        # ─── Step 3: 按加权分数排序 ─────────────────────────────
        deduped.sort(key=lambda c: c.weight, reverse=True)

        # ─── Step 4: Token 截断拼接 ─────────────────────────────
        context = self._truncate_and_join(deduped)

        logger.info(
            f"融合完成: 模式={query_mode}, "
            f"候选={len(candidates)}, 去重后={len(deduped)}, "
            f"上下文长度={len(context)} 字符"
        )
        return context

    def _deduplicate(self, candidates: List[ContextCandidate]) -> List[ContextCandidate]:
        """
        去重：按 chunk_id + content 去重，保留权重最高的版本
        """
        seen: Dict[str, ContextCandidate] = {}

        for c in candidates:
            # 去重键：chunk_id 或 content 摘要
            key = c.chunk_id if c.chunk_id else self._content_fingerprint(c.content)
            if key in seen:
                if c.weight > seen[key].weight:
                    seen[key] = c
            else:
                seen[key] = c

        return list(seen.values())

    @staticmethod
    def _content_fingerprint(content: str) -> str:
        """内容指纹（用于去重）"""
        import hashlib
        # 标准化：去空白后取 hash
        normalized = content.strip().replace("\n", " ").replace("  ", " ")
        return hashlib.md5(normalized.encode()).hexdigest()[:16]

    def _truncate_and_join(self, candidates: List[ContextCandidate]) -> str:
        """
        Token 截断拼接

        简化估算：1 中文 token ≈ 1.5 字符，1 英文 token ≈ 4 字符
        取平均 2.5 字符/token
        """
        chars_per_token = 2.5
        max_chars = int(self.max_context_tokens * chars_per_token)

        context_parts = []
        total_chars = 0

        for c in candidates:
            # 构建带来源标记的内容
            source_label = {
                "direct_entity_match": "图谱-实体",
                "vector_rerank_top": "向量",
                "relation_description": "图谱-关系",
                "graph_expansion": "图谱-扩展",
            }.get(c.source_type, c.source_type)

            part = f"{c.content} [来源:{source_label}]\n"
            part_chars = len(part)

            if total_chars + part_chars > max_chars:
                # 截断到句子边界
                remaining = max_chars - total_chars
                truncated = self._truncate_at_sentence_boundary(c.content, remaining)
                if truncated:
                    context_parts.append(f"{truncated} [来源:{source_label}]\n")
                break

            context_parts.append(part)
            total_chars += part_chars

        return "".join(context_parts)

    @staticmethod
    def _truncate_at_sentence_boundary(text: str, max_length: int) -> str:
        """在句子边界处截断"""
        if len(text) <= max_length:
            return text

        truncated = text[:max_length]
        # 查找最后一个句子结束位置
        import re
        sentence_end = re.search(r'[。！？.!?\n][^。！？.!?\n]*$', truncated)
        if sentence_end:
            return truncated[:sentence_end.end() - (len(truncated) - sentence_end.start())]

        return truncated


# ─── 查询模式路由 ───────────────────────────────────────────────

class QueryModeRouter:
    """
    根据查询模式，路由到不同的检索策略

    vector → 纯 Qdrant
    local  → Neo4j 实体检索
    global → Neo4j 关系遍历
    hybrid → 向量 + Neo4j
    mix    → 全量融合
    """

    def __init__(self, kg_service=None, entity_extractor=None):
        self.kg_service = kg_service
        self.entity_extractor = entity_extractor
        self.fusion = HybridResultFusion(
            max_context_tokens=getattr(settings, 'llm_max_tokens', 8192) // 2
        )

    async def route(
        self,
        query: str,
        user_id: str,
        vector_results: List[Any],
        query_mode: Optional[str] = None,
    ) -> str:
        """
        根据查询模式执行检索并融合
        
        模式说明 (参照 RAG-Anything LightRAG):
        - vector: 纯向量检索 (不使用图谱)
        - local: 实体匹配 → 局部子图
        - global: 关系遍历 → 全局推理
        - hybrid: local + global
        - mix: hybrid + vector (最全面,默认推荐)

        Args:
            query: 用户查询
            user_id: 用户 ID
            vector_results: Qdrant 向量检索结果
            query_mode: 查询模式，默认使用配置中的 kg_query_mode

        Returns:
            融合后的上下文
        """
        mode = query_mode or settings.kg_query_mode

        # 纯向量模式，直接返回向量结果
        if mode == "vector":
            return await self.fusion.fuse_results(
                vector_results=vector_results,
                graph_results=None,
                query_mode="vector",
            )

        # 图谱模式需要 Neo4j 可用
        if not self.kg_service or not self.kg_service.available:
            logger.info(f"知识图谱不可用，降级到 vector 模式 (请求模式={mode})")
            return await self.fusion.fuse_results(
                vector_results=vector_results,
                graph_results=None,
                query_mode="vector",
            )

        # Step 1: 从查询中提取实体
        query_entities = await self._extract_query_entities(query)
        if not query_entities:
            logger.warning(f"未提取到实体,降级到 vector 模式")
            return await self.fusion.fuse_results(
                vector_results=vector_results,
                graph_results=None,
                query_mode="vector",
            )

        # Step 2: 根据模式执行图谱查询
        graph_results = GraphSearchResult()

        if mode == "local":
            graph_results = await self._execute_local_query(query, query_entities, user_id)
        elif mode == "global":
            graph_results = await self._execute_global_query(query, query_entities, user_id)
        elif mode == "hybrid":
            local_result = await self._execute_local_query(query, query_entities, user_id)
            global_result = await self._execute_global_query(query, query_entities, user_id)
            # 合并 local 和 global 结果
            graph_results.entities = local_result.entities + global_result.entities
            graph_results.relations = local_result.relations + global_result.relations
            graph_results.related_chunks = local_result.related_chunks + global_result.related_chunks
        elif mode == "mix":
            # mix = hybrid + vector (全量融合)
            local_result = await self._execute_local_query(query, query_entities, user_id)
            global_result = await self._execute_global_query(query, query_entities, user_id)
            graph_results.entities = local_result.entities + global_result.entities
            graph_results.relations = local_result.relations + global_result.relations
            graph_results.related_chunks = local_result.related_chunks + global_result.related_chunks
        else:
            logger.warning(f"未知查询模式: {mode}, 回退到 vector 模式")
            return await self.fusion.fuse_results(
                vector_results=vector_results,
                graph_results=None,
                query_mode="vector",
            )

        # Step 3: 融合
        return await self.fusion.fuse_results(
            vector_results=vector_results,
            graph_results=graph_results,
            query_mode=mode,
        )

    async def _execute_local_query(
        self,
        query: str,
        entities: List[str],
        user_id: str,
    ) -> GraphSearchResult:
        """
        Local 模式: 实体匹配 → 获取实体描述 + 关联文本块
        
        参照 RAG-Anything LightRAG local mode
        """
        if not self.kg_service or not self.kg_service.available:
            return GraphSearchResult(entities=[], relations=[], related_chunks=[])
        
        result = GraphSearchResult(entities=[], relations=[], related_chunks=[])
        
        for entity_name in entities:
            try:
                # 1. 匹配实体节点
                matched_entities = self.kg_service.search_entities(entity_name, limit=5)
                
                for entity in matched_entities:
                    result.entities.append({
                        "entity_id": entity.get("entity_id"),
                        "entity_name": entity.get("entity_name", entity_name),
                        "entity_type": entity.get("entity_type", "概念"),
                        "description": entity.get("description", ""),
                    })
                    
                    # 2. 获取实体的直接关系 (1度)
                    local_context = self.kg_service.get_local_context([entity_name], user_id)
                    result.relations.extend(local_context.get("relations", []))
                    
                    # 3. 获取实体关联的文档块 (如果有实现)
                    # TODO: 如果 knowledge_graph 有 get_entity_related_chunks 方法,可以调用
                    
            except Exception as e:
                logger.warning(f"Local 查询实体 {entity_name} 失败: {e}")
                continue
        
        return result

    async def _execute_global_query(
        self,
        query: str,
        entities: List[str],
        user_id: str,
    ) -> GraphSearchResult:
        """
        Global 模式: 关系遍历 → 子图抽取 → 全局推理
        
        参照 RAG-Anything LightRAG global mode
        """
        if not self.kg_service or not self.kg_service.available:
            return GraphSearchResult(entities=[], relations=[], related_chunks=[])
        
        result = GraphSearchResult(entities=[], relations=[], related_chunks=[])
        
        # 1. 从种子实体出发,进行 2~3 度关系遍历
        for entity_name in entities:
            try:
                # 获取 2 度关系子图
                global_context = self.kg_service.get_global_context([entity_name], user_id)
                
                for node in global_context.get("entities", []):
                    result.entities.append(node)
                
                for rel in global_context.get("relations", []):
                    result.relations.append(rel)
                    
            except Exception as e:
                logger.warning(f"Global 查询实体 {entity_name} 失败: {e}")
                continue
        
        return result

    async def _extract_query_entities(self, query: str) -> List[str]:
        """从查询中提取实体名称（简化版：关键词提取）"""
        if not self.entity_extractor or not self.entity_extractor.available:
            # 降级：简单按空格和标点分割
            import re
            words = re.split(r'[\s，。、；：！？,.;:!?]+', query)
            return [w for w in words if len(w) >= 2][:5]

        try:
            result = await self.entity_extractor.extract(query)
            return [e.name for e in result.entities]
        except Exception as e:
            logger.warning(f"查询实体提取失败: {e}")
            import re
            words = re.split(r'[\s，。、；：！？,.;:!?]+', query)
            return [w for w in words if len(w) >= 2][:5]


# ─── 单例管理 ───────────────────────────────────────────────────

_fusion: Optional[HybridResultFusion] = None
_router: Optional[QueryModeRouter] = None


def get_hybrid_fusion() -> HybridResultFusion:
    """获取混合融合服务单例"""
    global _fusion
    if _fusion is None:
        _fusion = HybridResultFusion()
    return _fusion


def get_query_mode_router(kg_service=None, entity_extractor=None) -> QueryModeRouter:
    """获取查询模式路由器单例"""
    global _router
    if _router is None:
        from app.services.knowledge_graph import get_knowledge_graph_service
        from app.services.entity_extractor import get_entity_extractor
        _router = QueryModeRouter(
            kg_service=kg_service or get_knowledge_graph_service(),
            entity_extractor=entity_extractor or get_entity_extractor(),
        )
    return _router
