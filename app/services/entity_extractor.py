"""
实体-关系提取服务

在文档入库时调用 LLM 提取关键实体和关系，
然后写入 Neo4j 知识图谱。

参照方案 3.4：实体-关系提取与图谱查询
"""

import asyncio
import json
from typing import List, Optional, Dict, Any
from loguru import logger
from config.settings import settings
from app.core.resilience import async_retry


class EntityRelation:
    """实体关系数据模型"""
    def __init__(
        self,
        source: str,
        target: str,
        relation_type: str,
        description: str = "",
    ):
        self.source = source
        self.target = target
        self.relation_type = relation_type
        self.description = description


class Entity:
    """实体数据模型"""
    def __init__(
        self,
        name: str,
        entity_type: str,
        description: str = "",
    ):
        self.name = name
        self.entity_type = entity_type
        self.description = description


class ExtractionResult:
    """提取结果"""
    def __init__(self):
        self.entities: List[Entity] = []
        self.relations: List[EntityRelation] = []


# ─── 提取 Prompt ──────────────────────────────────────────────

ENTITY_EXTRACTION_PROMPT = """你是一个专业的知识图谱构建助手。请从以下文本中提取关键实体和实体间的关系。

## 输出格式

请严格按照以下 JSON 格式输出，不要输出其他内容：

```json
{{
  "entities": [
    {{"name": "实体名称", "type": "实体类型", "description": "实体的简要描述"}}
  ],
  "relations": [
    {{"source": "源实体名称", "target": "目标实体名称", "type": "关系类型", "description": "关系描述"}}
  ]
}}
```

## 实体类型参考

可选的实体类型包括但不限于：
- 概念：抽象概念、理论、方法
- 技术：具体技术、工具、框架
- 人物：人名、角色
- 组织：公司、机构、团队
- 产品：产品、服务
- 事件：事件、活动
- 位置：地点、区域
- 时间：时间点、时间段
- 数据：数据集、指标、参数

## 关系类型参考

可选的关系类型包括但不限于：
- 包含：A 包含 B
- 依赖：A 依赖 B
- 属于：A 属于 B
- 实现：A 实现 B
- 影响：A 影响 B
- 相关：A 与 B 相关
- 对比：A 与 B 对比
- 前驱：A 是 B 的前驱/前提
- 组成：A 由 B 组成

## 注意事项

1. 只提取文本中明确提及的实体和关系，不要推测
2. 实体名称应使用原文中的标准表达
3. 每个实体必须有 type 和 description
4. 关系的 source 和 target 必须是已提取的实体名称
5. 如果文本中没有明确的实体和关系，返回空列表

## 文本内容

{text}"""


class EntityExtractor:
    """实体-关系提取器"""

    def __init__(self):
        self._llm_api_base = settings.llm_api_base
        self._llm_api_key = settings.llm_api_key
        self._llm_model = settings.llm_model

    @property
    def available(self) -> bool:
        """提取器是否可用（需要 LLM API Key）"""
        return bool(self._llm_api_key and self._llm_api_base)

    async def extract(self, text: str) -> ExtractionResult:
        """
        从文本中提取实体和关系

        Args:
            text: 文档文本块

        Returns:
            ExtractionResult 包含 entities 和 relations
        """
        result = ExtractionResult()

        if not self.available:
            logger.debug("LLM API 不可用，跳过实体提取")
            return result

        if not text or len(text.strip()) < 20:
            return result

        # 截断过长的文本
        max_length = 3000
        if len(text) > max_length:
            text = text[:max_length] + "..."

        try:
            extraction = await self._call_llm(text)
            logger.debug(f"LLM返回内容前200字符: {extraction[:200] if extraction else 'None'}")
            if extraction:
                result = self._parse_extraction(extraction)
                logger.debug(f"解析结果: {len(result.entities)} entities, {len(result.relations)} relations")
        except Exception as e:
            import traceback
            logger.warning(f"实体提取失败: {e}")
            logger.warning(f"异常堆栈:\n{traceback.format_exc()}")

        return result

    async def extract_from_chunks(
        self,
        chunks: List[Dict[str, Any]],
        max_chunks: int = None,
    ) -> ExtractionResult:
        """
        从多个文档块中提取实体和关系 (并发优化版)

        参照 RAG-Anything processor.py _batch_extract_entities_lightrag_style:
        - 使用 Semaphore 控制并发数,避免 API 限速
        - 使用 asyncio.gather 并发处理多个块
        - 处理所有传入的chunk，确保完整知识图谱覆盖

        Args:
            chunks: 文档块列表，每个块包含 content 字段
            max_chunks: 最多处理的块数（默认 None 表示处理全部）

        Returns:
            合并后的 ExtractionResult
        """
        if not self.available:
            logger.debug("LLM API 不可用，跳过实体提取")
            return ExtractionResult()

        # 处理所有chunk（除非显式指定 max_chunks）
        limited_chunks = chunks[:max_chunks] if max_chunks is not None else chunks
        logger.info(f"实体提取: 处理 {len(limited_chunks)}/{len(chunks)} 个chunk")
        
        # 获取并发控制参数
        max_parallel = getattr(settings, "kg_entity_max_parallel", 3)
        semaphore = asyncio.Semaphore(max_parallel)
        
        @async_retry(
            max_attempts=getattr(settings, "llm_retry_max_attempts", 3),
            base_delay=getattr(settings, "llm_retry_base_delay", 1.0)
        )
        async def _extract_single_chunk(chunk: Dict[str, Any], index: int):
            """并发提取单个块的实体和关系"""
            async with semaphore:
                try:
                    content = chunk.get("content", "")
                    if not content or len(content.strip()) < 20:
                        return None
                    
                    result = await self.extract(content)
                    return {
                        "chunk_id": chunk.get("chunk_id", f"chunk_{index}"),
                        "entities": result.entities,
                        "relations": result.relations
                    }
                except Exception as e:
                    logger.warning(f"块 {chunk.get('chunk_id', index)} 提取失败: {e}")
                    return None
        
        # 创建并发任务
        tasks = [
            asyncio.create_task(_extract_single_chunk(chunk, i))
            for i, chunk in enumerate(limited_chunks)
        ]
        
        # 并发执行所有任务
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 汇总结果并去重
        merged = ExtractionResult()
        seen_entities = set()
        seen_relations = set()
        
        for raw in results_raw:
            if isinstance(raw, Exception) or raw is None:
                continue
            
            # 去重合并实体
            for entity in raw["entities"]:
                key = (entity.name, entity.entity_type)
                if key not in seen_entities:
                    seen_entities.add(key)
                    merged.entities.append(entity)
                else:
                    # 合并描述
                    for existing in merged.entities:
                        if (existing.name, existing.entity_type) == key:
                            if entity.description and entity.description not in existing.description:
                                existing.description += f"; {entity.description}"
                            break
            
            # 去重合并关系
            for rel in raw["relations"]:
                key = (rel.source, rel.target, rel.relation_type)
                if key not in seen_relations:
                    seen_relations.add(key)
                    merged.relations.append(rel)
        
        logger.info(
            f"实体提取完成 (并发模式): {len(merged.entities)} 个实体, "
            f"{len(merged.relations)} 个关系"
        )
        return merged

    async def _call_llm(self, text: str) -> Optional[str]:
        """调用 LLM 进行实体提取"""
        import httpx

        prompt = ENTITY_EXTRACTION_PROMPT.format(text=text)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._llm_api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._llm_model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,  # 低温度，确保稳定输出
                    "max_tokens": 2000,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _parse_extraction(self, text: str) -> ExtractionResult:
        """解析 LLM 返回的 JSON 提取结果"""
        result = ExtractionResult()

        # 尝试提取 JSON（可能包裹在 ```json ``` 中）
        json_text = text
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            json_text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            json_text = text[start:end].strip()

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            logger.warning(f"原始文本前500字符: {text[:500]}")
            logger.warning(f"提取的JSON文本前500字符: {json_text[:500]}")
            # 尝试找到 JSON 对象
            import re
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.warning(f"无法解析实体提取结果: {text[:200]}")
                    return result
            else:
                return result

        # 解析实体
        for e in data.get("entities", []):
            name = e.get("name", "").strip()
            etype = e.get("type", "概念").strip()
            desc = e.get("description", "").strip()
            if name:
                result.entities.append(Entity(name=name, entity_type=etype, description=desc))

        # 解析关系
        for r in data.get("relations", []):
            source = r.get("source", "").strip()
            target = r.get("target", "").strip()
            rtype = r.get("type", "相关").strip()
            desc = r.get("description", "").strip()
            if source and target:
                result.relations.append(
                    EntityRelation(source=source, target=target, relation_type=rtype, description=desc)
                )

        return result


# ─── 单例管理 ───────────────────────────────────────────────────

_extractor: Optional[EntityExtractor] = None


def get_entity_extractor() -> EntityExtractor:
    """获取实体提取器单例"""
    global _extractor
    if _extractor is None:
        _extractor = EntityExtractor()
    return _extractor
