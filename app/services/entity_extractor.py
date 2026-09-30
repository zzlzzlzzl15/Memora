"""
实体-关系提取服务

在文档入库时调用 LLM 提取关键实体和关系，
然后写入 Neo4j 知识图谱。

参照方案 3.4：实体-关系提取与图谱查询
"""

import asyncio
import json
import os
import hashlib
from pathlib import Path
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
        source_chunk_id: Optional[str] = None,
        source_snippet: str = "",
    ):
        self.name = name
        self.entity_type = entity_type
        self.description = description
        # P2-8: chunk 级溯源，用于在图谱上建立 APPEARS_IN 的 chunk 关联
        self.source_chunk_id = source_chunk_id
        self.source_snippet = source_snippet


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


# ─── P2-9: 实体类型归一化（48 类自由文本 → ~9 类规范类型）───
# LLM 输出的 type 字段高度发散（data/Data/数据/数据集…），归一化后
# 既减少 Neo4j 上 entity_type 的基数，也让同名同类型实体更易合并去重。
_ENTITY_TYPE_MAP = {
    "概念": "概念", "理论": "概念", "方法": "概念", "方法论": "概念",
    "concept": "概念", "theory": "概念", "method": "概念",
    "技术": "技术", "工具": "技术", "框架": "技术", "算法": "技术",
    "technology": "技术", "tech": "技术", "tool": "技术", "framework": "技术",
    "人物": "人物", "人名": "人物", "角色": "人物", "专家": "人物",
    "person": "人物", "people": "人物", "human": "人物",
    "组织": "组织", "公司": "组织", "机构": "组织", "团队": "组织", "部门": "组织",
    "organization": "组织", "org": "组织", "company": "组织", "team": "组织",
    "产品": "产品", "服务": "产品", "系统": "产品", "平台": "产品",
    "product": "产品", "service": "产品", "system": "产品", "platform": "产品",
    "事件": "事件", "活动": "事件", "会议": "事件", "event": "事件",
    "位置": "位置", "地点": "位置", "区域": "位置", "城市": "位置",
    "location": "位置", "place": "位置", "region": "位置",
    "时间": "时间", "时间点": "时间", "时间段": "时间", "日期": "时间",
    "date": "时间", "time": "时间", "period": "时间",
    "数据": "数据", "数据集": "数据", "指标": "数据", "参数": "数据", "字段": "数据",
    "data": "数据", "dataset": "数据", "metric": "数据", "parameter": "数据",
}


def normalize_entity_type(raw_type: str) -> str:
    """将发散的实体类型归一化到 ~9 类规范类型；未知类型回退为“概念”。"""
    if not raw_type:
        return "概念"
    key = raw_type.strip().lower()
    if key in _ENTITY_TYPE_MAP:
        return _ENTITY_TYPE_MAP[key]
    # 原文（未 lower）再查一次，兼容中文大小写无关
    stripped = raw_type.strip()
    if stripped in _ENTITY_TYPE_MAP:
        return _ENTITY_TYPE_MAP[stripped]
    return "概念"


class EntityExtractor:
    """实体-关系提取器"""

    def __init__(self):
        self._llm_api_base = settings.llm_api_base
        self._llm_api_key = settings.llm_api_key
        self._llm_model = settings.llm_model
        # content-hash 缓存（reprocess 未变内容可跳过 LLM 重跑）
        self._cache_enabled = bool(getattr(settings, "entity_extraction_cache_enabled", True))
        self._cache_dir = None
        if self._cache_enabled:
            try:
                self._cache_dir = Path(settings.upload_dir) / ".extraction_cache"
                self._cache_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"实体提取缓存目录初始化失败，禁用缓存: {e}")
                self._cache_enabled = False

    @property
    def available(self) -> bool:
        """提取器是否可用（需要 LLM API Key）"""
        return bool(self._llm_api_key and self._llm_api_base)

    # ─── content-hash 缓存 ────────────────────────────────

    def _cache_key(self, text: str) -> str:
        """缓存键：模型 + prompt 版本 + 文本内容的 md5"""
        return hashlib.md5(f"{self._llm_model}|v1|{text}".encode("utf-8")).hexdigest()

    def _cache_get(self, text: str) -> Optional[ExtractionResult]:
        if not self._cache_enabled or self._cache_dir is None:
            return None
        try:
            cf = self._cache_dir / f"{self._cache_key(text)}.json"
            if not cf.exists():
                return None
            with open(cf, "r", encoding="utf-8") as f:
                data = json.load(f)
            result = ExtractionResult()
            for e in data.get("entities", []):
                result.entities.append(Entity(
                    name=e.get("name", ""),
                    entity_type=e.get("type", "概念"),
                    description=e.get("description", ""),
                ))
            for r in data.get("relations", []):
                result.relations.append(EntityRelation(
                    source=r.get("source", ""),
                    target=r.get("target", ""),
                    relation_type=r.get("type", "相关"),
                    description=r.get("description", ""),
                ))
            return result
        except Exception as e:
            logger.debug(f"读取实体提取缓存失败: {e}")
            return None

    def _cache_set(self, text: str, result: ExtractionResult) -> None:
        if not self._cache_enabled or self._cache_dir is None:
            return
        # 空结果不缓存（避免把失败态固化）
        if not result.entities and not result.relations:
            return
        try:
            cf = self._cache_dir / f"{self._cache_key(text)}.json"
            data = {
                "entities": [
                    {"name": e.name, "type": e.entity_type, "description": e.description}
                    for e in result.entities
                ],
                "relations": [
                    {"source": r.source, "target": r.target, "type": r.relation_type, "description": r.description}
                    for r in result.relations
                ],
            }
            with open(cf, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"写入实体提取缓存失败: {e}")

    async def extract(self, text: str) -> ExtractionResult:
        """
        从文本中提取实体和关系

        网络类异常（DNS 抖动/超时）经 _call_llm 内部 async_retry 重试耗尽后向上抛，
        由调用方统计失败；解析类错误仍就地降级为空结果。
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

        # content-hash 缓存命中则直接返回，跳过 LLM
        cached = self._cache_get(text)
        if cached is not None:
            logger.debug(
                f"实体提取缓存命中: {len(cached.entities)} 实体 / {len(cached.relations)} 关系"
            )
            return cached

        # _call_llm 内部已带 async_retry；不再在此处吞掉网络异常（否则重试永不触发）
        extraction = await self._call_llm(text)
        logger.debug(f"LLM返回内容前200字符: {extraction[:200] if extraction else 'None'}")
        if extraction:
            try:
                result = self._parse_extraction(extraction)
            except Exception as e:
                logger.warning(f"实体提取解析失败: {e}")
            logger.debug(
                f"解析结果: {len(result.entities)} entities, {len(result.relations)} relations"
            )
            self._cache_set(text, result)

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
        max_parallel = getattr(settings, "kg_entity_max_parallel", 8)
        semaphore = asyncio.Semaphore(max_parallel)

        # 注意：重试已下沉到 _call_llm（真正抛异常处）；此处不再叠加 @async_retry。
        # 旧装饰器因 extract() 吞掉异常而从未触发（死代码），现 extract() 会将网络异常上抛至此。
        async def _extract_single_chunk(chunk: Dict[str, Any], index: int):
            """并发提取单个块的实体和关系"""
            async with semaphore:
                try:
                    content = chunk.get("content", "")
                    if not content or len(content.strip()) < 20:
                        return None
                    
                    result = await self.extract(content)
                    # P2-8: 为本抽取单元的实体附上 chunk 溯源（id + 内容片段）
                    cid = chunk.get("chunk_id", f"chunk_{index}")
                    snippet = content[:500]
                    for ent in result.entities:
                        ent.source_chunk_id = cid
                        ent.source_snippet = snippet
                    return {
                        "chunk_id": cid,
                        "entities": result.entities,
                        "relations": result.relations
                    }
                except Exception as e:
                    logger.warning(f"块 {chunk.get('chunk_id', index)} 提取失败（已重试）: {e}")
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
                    # 合并描述（保留首次出现的 chunk 溯源）
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

    @async_retry(
        max_attempts=getattr(settings, "llm_retry_max_attempts", 3),
        base_delay=getattr(settings, "llm_retry_base_delay", 1.0),
    )
    async def _call_llm(self, text: str) -> Optional[str]:
        """调用 LLM 进行实体提取（指数退避重试下沉至此：网络/DNS 抖动可自愈）"""
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
                    "max_tokens": getattr(settings, "llm_extraction_max_tokens", 3000),
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    @staticmethod
    def _extract_json_block(text: str) -> str:
        """从可能包裹 ```json ... ``` 的文本中提取 JSON 片段；缺失闭合 fence 时不抛异常。"""
        marker = "```json"
        start = text.find(marker)
        if start != -1:
            start += len(marker)
        else:
            fence = text.find("```")
            if fence != -1:
                start = fence + 3
            else:
                return text.strip()
        # 查找闭合 fence；找不到（被 max_tokens 截断）则取到结尾
        end = text.find("```", start)
        if end == -1:
            return text[start:].strip()
        return text[start:end].strip()

    @staticmethod
    def _load_truncated_json(candidate: str):
        """尽力修复被 max_tokens 截断的 JSON：闭合未完成的字符串与括号。"""
        def _repair(frag: str):
            stack = []
            in_str = False
            esc = False
            for ch in frag:
                if in_str:
                    if esc:
                        esc = False
                    elif ch == '\\':
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch in '[{':
                    stack.append(ch)
                elif ch in ']}':
                    if stack:
                        stack.pop()
            repaired = frag + ('"' if in_str else '')
            repaired = repaired.rstrip()
            while repaired.endswith(','):
                repaired = repaired[:-1].rstrip()
            for open_ch in reversed(stack):
                repaired += ']' if open_ch == '[' else '}'
            return repaired

        last_brace = candidate.rfind('}')
        fragments = [candidate]
        if last_brace != -1:
            fragments.append(candidate[:last_brace + 1])
        for frag in fragments:
            try:
                return json.loads(_repair(frag))
            except (json.JSONDecodeError, ValueError):
                continue
        return None

    def _parse_extraction(self, text: str) -> ExtractionResult:
        """解析 LLM 返回的 JSON 提取结果（对截断 / 缺失闭合 fence 健壮，不再抛 ValueError）"""
        result = ExtractionResult()
        if not text:
            return result

        json_text = self._extract_json_block(text)

        data = None
        # 1) 直接解析
        try:
            data = json.loads(json_text)
        except (json.JSONDecodeError, ValueError):
            data = None

        # 2) 正则兜底：截取最外层 { ... }
        if not isinstance(data, dict):
            import re
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                candidate = match.group()
                try:
                    data = json.loads(candidate)
                except (json.JSONDecodeError, ValueError):
                    # 3) 截断修复：补齐未闭合的字符串与括号
                    data = self._load_truncated_json(candidate)

        if not isinstance(data, dict):
            logger.warning(f"无法解析实体提取结果，前200字符: {text[:200]}")
            return result

        # 解析实体
        for e in data.get("entities", []) or []:
            if not isinstance(e, dict):
                continue
            name = (e.get("name") or "").strip()
            etype = normalize_entity_type((e.get("type") or "概念").strip())
            desc = (e.get("description") or "").strip()
            if name:
                result.entities.append(Entity(name=name, entity_type=etype, description=desc))

        # 解析关系
        for r in data.get("relations", []) or []:
            if not isinstance(r, dict):
                continue
            source = (r.get("source") or "").strip()
            target = (r.get("target") or "").strip()
            rtype = (r.get("type") or "相关").strip()
            desc = (r.get("description") or "").strip()
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
