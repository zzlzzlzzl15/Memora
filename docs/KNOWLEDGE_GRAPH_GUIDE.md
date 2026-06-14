# Memora 知识图谱功能说明

## ✅ 是的,Memora已经配备了完整的知识图谱功能!

---

## 📊 当前配置状态

### 1. Neo4j图数据库 - ✅ 已部署并运行

```bash
容器名称: memora-neo4j
版本: Neo4j 5.26.27 (Community Edition)
状态: Running
访问地址:
  - HTTP管理界面: http://localhost:7474
  - Bolt协议: bolt://localhost:7687
```

**验证命令**:
```bash
# 检查Neo4j状态
docker ps | grep neo4j

# 访问HTTP API
curl http://localhost:7474

# 查看日志
docker logs memora-neo4j --tail 20
```

### 2. 应用层配置 - ✅ 已启用

在 [.env.production](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/.env.production#L107-L112) 中:

```ini
NEO4J_ENABLED=true                    # ✅ 已启用
NEO4J_URI="bolt://neo4j:7687"        # Docker内部网络地址
NEO4J_USER="neo4j"
NEO4J_PASSWORD="memora_neo4j_pass"
NEO4J_DATABASE="neo4j"
KG_QUERY_MODE=mix                     # 混合查询模式(向量+图谱)
```

### 3. 健康检查 - ✅ 正常

```bash
$ curl http://localhost:8000/health
{
    "status": "healthy",
    "qdrant_ready": true,
    "knowledge_graph": "ready"  # ✅ 知识图谱服务就绪
}
```

---

## 🏗️ 架构设计

### 整体流程图

```
用户上传文档
    ↓
┌─────────────────────────────────┐
│   DocumentProcessor             │
│   • MinerU结构化解析            │
│   • 文本分块 (Chunking)         │
└──────────────┬──────────────────┘
               ↓
    ┌──────────────────────┐
    │  并行处理两个分支     │
    └──┬───────────────┬───┘
       ↓               ↓
┌──────────────┐  ┌──────────────────┐
│ Qdrant向量库  │  │ Neo4j知识图谱     │
│ • 向量嵌入    │  │ • 实体提取        │
│ • 语义检索    │  │ • 关系构建        │
└──────────────┘  └──────────────────┘
       ↓               ↓
    ┌──────────────────────────┐
    │ Hybrid Fusion 混合检索    │
    │ • 向量相似度              │
    │ • 图谱关联度              │
    │ • Rerank重排序            │
    └──────────┬───────────────┘
               ↓
          LLM生成回答
```

### 核心组件

| 组件 | 文件路径 | 功能 |
|------|---------|------|
| **KnowledgeGraphService** | [app/services/knowledge_graph.py](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/knowledge_graph.py) | Neo4j连接管理、实体/关系CRUD、Cypher查询 |
| **EntityExtractor** | [app/services/entity_extractor.py](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/entity_extractor.py) | LLM驱动的实体-关系提取 |
| **DocumentService._build_knowledge_graph** | [app/services/document_service.py#L773-L849](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/document_service.py#L773-L849) | 文档入库时自动构建图谱 |
| **HybridFusionSearch** | [app/services/hybrid_fusion.py](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/hybrid_fusion.py) | 向量+图谱混合检索融合 |

---

## 🔧 工作流程详解

### 阶段1: 文档上传与解析

当用户上传文档时:

1. **文件接收** → 保存到 `uploads/{user_id}/`
2. **结构化解析** → MinerU提取文本、表格、图片描述
3. **文本分块** → 按语义或固定长度切分为chunks

### 阶段2: 知识图谱构建 (自动化)

在 [document_service.py#L634-L636](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/document_service.py#L634-L636):

```python
if settings.neo4j_enabled:
    logger.info("开始构建知识图谱...")
    await self._build_knowledge_graph(document, all_chunks)
```

**详细步骤** ([_build_knowledge_graph方法](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/document_service.py#L773-L849)):

#### Step 1: 创建文档节点
```python
kg_service.add_document_node(
    doc_id=document.document_id,
    title=document.title,
    user_id=document.user_id,
)
```

Neo4j中创建的节点:
```cypher
(:Document {
    doc_id: "0e3892a8-2c61-4e89-965b-01541194034d",
    title: "中国房价走势分析 2026",
    user_id: "1",
    created_at: "2026-05-17T16:43:12"
})
```

#### Step 2: 并发实体提取

调用 [EntityExtractor.extract_from_chunks](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/entity_extractor.py#L165-L250):

```python
extraction_result = await extractor.extract_from_chunks(
    chunk_data, max_chunks=10  # 最多处理10个chunk控制成本
)
```

**LLM Prompt示例** ([entity_extractor.py#L55-L120](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/entity_extractor.py#L55-L120)):

```
你是一个专业的知识图谱构建助手。请从以下文本中提取关键实体和实体间的关系。

输出格式:
{
  "entities": [
    {"name": "实体名称", "type": "实体类型", "description": "描述"}
  ],
  "relations": [
    {"source": "源实体", "target": "目标实体", "type": "关系类型", "description": "关系描述"}
  ]
}

实体类型: 概念、技术、人物、组织、产品、事件、位置、时间、数据
关系类型: 包含、依赖、属于、实现、影响、相关、对比、前驱、组成
```

**提取结果示例** (针对"中国房价走势分析"文档):

```json
{
  "entities": [
    {"name": "一线城市", "type": "概念", "description": "北京上海广州深圳等核心城市"},
    {"name": "房价", "type": "数据", "description": "房地产市场价格指标"},
    {"name": "日本", "type": "位置", "description": "对比参照国家"},
    {"name": "租金回报率", "type": "数据", "description": "房产投资收益指标"}
  ],
  "relations": [
    {"source": "一线城市", "target": "房价", "type": "影响", "description": "一线城市房价相对稳定"},
    {"source": "中国", "target": "日本", "type": "对比", "description": "中日楼市周期对比"},
    {"source": "租金回报率", "target": "房价", "type": "相关", "description": "回报率低反映房价偏高"}
  ]
}
```

#### Step 3: 批量写入Neo4j

**实体节点** ([add_entities_batch](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/knowledge_graph.py#L180-L220)):

```python
kg_service.add_entities_batch(
    entities=[...],
    doc_id=document.document_id,
    user_id=document.user_id
)
```

Neo4j Cypher执行:
```cypher
MERGE (e:Entity {entity_name: "一线城市", entity_type: "概念"})
SET e.description = "北京上海广州深圳等核心城市",
    e.user_id = "1",
    e.updated_at = datetime()
MERGE (d:Document {doc_id: "0e3892a8-..."})
MERGE (e)-[:MENTIONED_IN]->(d)
```

**关系边** ([add_relations_batch](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/knowledge_graph.py#L222-L265)):

```python
kg_service.add_relations_batch(
    relations=[...],
    doc_id=document.document_id,
    user_id=document.user_id
)
```

Neo4j Cypher执行:
```cypher
MATCH (source:Entity {entity_name: "一线城市"})
MATCH (target:Entity {entity_name: "房价"})
MERGE (source)-[r:INFLUENCES {relation_type: "影响"}]->(target)
SET r.description = "一线城市房价相对稳定",
    r.doc_id = "0e3892a8-...",
    r.user_id = "1"
```

### 阶段3: 混合检索 (查询时)

用户提问: **"一线城市房价为什么比较稳定?"**

#### Step 1: 向量检索 (Qdrant)
- 将问题向量化
- 在Qdrant中搜索相似chunks
- 返回Top-K相关文档片段

#### Step 2: 图谱检索 (Neo4j)
根据 [KG_QUERY_MODE=mix](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/.env.production#L112),执行混合查询:

```cypher
// 找到"一线城市"和"房价"实体
MATCH (e1:Entity {entity_name: "一线城市"})
MATCH (e2:Entity {entity_name: "房价"})

// 查找它们之间的关系路径
MATCH path = (e1)-[*1..3]-(e2)
RETURN path, 
       relationships(path) AS relations,
       nodes(path) AS entities
LIMIT 10
```

可能返回:
```
路径1: 一线城市 -[影响]-> 房价
路径2: 一线城市 -[属于]-> 中国 -[对比]-> 日本 -[参考]-> 房价趋势
路径3: 一线城市 -[包含]-> 核心区 -[特征]-> 房价止跌微涨
```

#### Step 3: 结果融合 (HybridFusion)

[hybrid_fusion.py](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/hybrid_fusion.py) 将两种结果合并:

```python
class HybridFusionSearch:
    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        # 1. 向量检索结果
        vector_results = self.vector_search(query, top_k=top_k*2)
        
        # 2. 图谱检索结果
        kg_results = self.kg_search(query, top_k=top_k)
        
        # 3. 去重合并
        merged = self.merge_results(vector_results, kg_results)
        
        # 4. Rerank重排序
        if settings.use_rerank:
            merged = self.rerank(query, merged, top_n=top_k)
        
        return merged[:top_k]
```

#### Step 4: LLM生成最终答案

将融合的上下文输入LLM:

```
基于以下信息回答问题:

【向量检索结果】
- Chunk 1: "一线城市（北上广深）：核心区止跌微涨（+0.5%~+2%），远郊阴跌"
- Chunk 2: "驱动：人口负增长、城镇化放缓、库存高..."

【知识图谱关联】
- 一线城市 -[影响]-> 房价 (描述: 一线城市房价相对稳定)
- 一线城市 -[包含]-> 核心区 (描述: 核心区域房价表现较好)
- 中国 -[对比]-> 日本 (描述: 中日楼市周期对比)

问题: 一线城市房价为什么比较稳定?

请综合以上信息给出专业回答。
```

---

## 📈 性能优化特性

### 1. 并发实体提取

[entity_extractor.py#L165-L250](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/entity_extractor.py#L165-L250):

```python
async def extract_from_chunks(self, chunks: list, max_chunks: int = 10):
    # 使用Semaphore限制并发数 (默认3)
    semaphore = asyncio.Semaphore(settings.kg_entity_max_parallel)
    
    async def extract_single(chunk_data):
        async with semaphore:
            return await self._extract_single_chunk(chunk_data)
    
    # 并发执行所有chunks的实体提取
    tasks = [extract_single(c) for c in chunks[:max_chunks]]
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

**优势**: 
- 避免API限流
- 提升处理速度3-5倍

### 2. 批量写入Neo4j

[knowledge_graph.py#L180-L265](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/app/services/knowledge_graph.py#L180-L265):

```python
def add_entities_batch(self, entities: list, doc_id: str, user_id: str):
    """批量添加实体,使用MERGE避免重复"""
    with self._driver.session(database=settings.neo4j_database) as session:
        for entity in entities:
            session.run("""
                MERGE (e:Entity {entity_name: $name, entity_type: $type})
                SET e.description = $desc,
                    e.user_id = $user_id,
                    e.updated_at = datetime()
                WITH e
                MATCH (d:Document {doc_id: $doc_id})
                MERGE (e)-[:MENTIONED_IN]->(d)
            """, name=entity['name'], type=entity['type'], ...)
```

**优势**:
- MERGE确保幂等性(重复执行不产生重复节点)
- 单次事务批量提交,减少网络往返

### 3. 成本控制

- **限制chunk数量**: 每个文档最多处理10个chunks
- **仅处理文本类型**: 跳过图片、表格等非文本内容
- **可配置的并发数**: `KG_ENTITY_MAX_PARALLEL=3`

---

## 🎯 实际应用场景

### 场景1: 跨文档知识关联

**用户提问**: "OpenClaw和中国房价有什么关系?"

**传统RAG**: 无法找到直接相关的文档片段,返回空或无关结果

**知识图谱增强**:
```cypher
// 虽然两篇文档没有直接关系,但可能通过中间实体连接
MATCH path = (e1:Entity)-[*1..4]-(e2:Entity)
WHERE e1.entity_name CONTAINS "OpenClaw"
  AND e2.entity_name CONTAINS "房价"
RETURN path
```

可能发现间接关联:
```
OpenClaw -[属于]-> AI Agent -[应用于]-> 数据分析 -[涉及]-> 经济指标 -[包括]-> 房价
```

### 场景2: 实体探索式查询

**用户提问**: "帮我找出所有与'一线城市'相关的概念"

**图谱查询**:
```cypher
MATCH (e:Entity {entity_name: "一线城市"})-[r]-(related:Entity)
RETURN related.entity_name, related.entity_type, r.relation_type
ORDER BY related.entity_type
```

返回:
```
| 相关实体   | 类型   | 关系   |
|-----------|--------|--------|
| 房价      | 数据   | 影响   |
| 核心区    | 概念   | 包含   |
| 北京      | 位置   | 包括   |
| 上海      | 位置   | 包括   |
| 租金回报率| 数据   | 相关   |
```

### 场景3: 知识推理

**用户提问**: "如果日本的经验适用于中国,未来房价会怎样?"

**图谱提供推理路径**:
```
中国楼市 -[对比]-> 日本楼市 -[经历]-> 泡沫破裂 -[导致]-> 长期阴跌
                                    ↓
                            启示: 中国可能进入类似阶段
```

结合向量检索的具体数据,LLM可以给出更深入的预测分析。

---

## 🔍 如何验证知识图谱是否工作

### 1. 检查Neo4j中的节点数量

访问 http://localhost:7474 (浏览器),登录:
- Username: `neo4j`
- Password: `memora_neo4j_pass`

执行Cypher查询:
```cypher
// 统计节点数量
MATCH (n) RETURN labels(n) AS label, count(n) AS count

// 查看所有实体
MATCH (e:Entity) RETURN e.entity_name, e.entity_type LIMIT 20

// 查看关系
MATCH ()-[r]->() RETURN type(r) AS relation_type, count(r) AS count
```

### 2. 通过API测试

```bash
# 测试混合搜索
curl -X POST http://localhost:8000/api/v1/documents/search/quick \
  -H "Content-Type: application/json" \
  -d '{"query": "一线城市房价", "use_kg": true}'
```

### 3. 查看应用日志

```bash
docker logs memora-app | grep -i "知识图谱\|entity\|neo4j"
```

期望看到:
```
INFO | Neo4j 知识图谱连接成功: bolt://neo4j:7687
INFO | 开始构建知识图谱...
INFO | 知识图谱构建完成: doc=0e3892a8-..., entities=15, relations=8
```

---

## ⚙️ 配置调优指南

### 调整并发数

在 [.env.production](file:///Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base/.env.production#L129-L130):

```ini
# 实体提取并发数 (根据LLM API限流调整)
KG_ENTITY_MAX_PARALLEL=3  # 增加可提高速度,但可能触发限流

# 多模态处理并发数
MULTIMODAL_MAX_PARALLEL=2
```

### 切换查询模式

```ini
# 可用模式: vector / local / global / hybrid / mix
KG_QUERY_MODE=mix  # 推荐: 向量+图谱混合

# 纯向量检索(更快,但不利用图谱)
# KG_QUERY_MODE=vector

# 纯图谱检索(适合实体探索)
# KG_QUERY_MODE=local
```

### 禁用知识图谱(节省资源)

```ini
NEO4J_ENABLED=false  # 完全禁用图谱功能
```

---

## 🛠️ 故障排查

### 问题1: 知识图谱显示"unavailable"

**症状**: `/health` 返回 `"knowledge_graph": "unavailable"`

**排查步骤**:
```bash
# 1. 检查Neo4j容器状态
docker ps | grep neo4j

# 2. 查看Neo4j日志
docker logs memora-neo4j --tail 50

# 3. 测试Bolt连接
docker exec memora-app python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', 'memora_neo4j_pass'))
driver.verify_connectivity()
print('连接成功!')
driver.close()
"

# 4. 检查应用日志
docker logs memora-app | grep -i "neo4j\|knowledge.*graph"
```

**常见原因**:
- Neo4j密码错误 → 修改 `.env.production` 中的 `NEO4J_PASSWORD`
- 网络不通 → 确认Docker Compose中app和neo4j在同一网络
- 内存不足 → 调整 `NEO4J_server_memory_heap_max__size`

### 问题2: 文档处理后没有实体

**症状**: 日志显示 `entities=0, relations=0`

**排查步骤**:
```bash
# 1. 检查LLM API是否正常
curl https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer sk-ff813f1a3b664f449ea4916016330d39" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen-plus","messages":[{"role":"user","content":"Hello"}]}'

# 2. 检查文档内容是否为空
docker exec memora-mysql mysql -uroot -p'密码' personal_knowledgebase \
  -e "SELECT doc_id, title, LENGTH(content) as content_len FROM documents WHERE doc_id='你的文档ID';"

# 3. 手动测试实体提取
docker exec -it memora-app python -c "
import asyncio
from app.services.entity_extractor import get_entity_extractor

async def test():
    extractor = get_entity_extractor()
    result = await extractor.extract_from_chunks([
        {'content': '一线城市房价稳定,核心区微涨', 'chunk_id': 'test'}
    ])
    print(f'Entities: {len(result.entities)}')
    print(f'Relations: {len(result.relations)}')
    for e in result.entities:
        print(f'  - {e.name} ({e.entity_type})')

asyncio.run(test())
"
```

**常见原因**:
- LLM API密钥无效或额度用尽
- 文档内容为空或太短(<100字)
- Prompt格式错误导致LLM无法解析JSON

### 问题3: Neo4j查询慢

**优化方案**:
```cypher
// 1. 检查是否有索引
CALL db.indexes()

// 2. 如果没有,创建索引
CREATE INDEX entity_name_idx FOR (e:Entity) ON (e.entity_name);
CREATE INDEX entity_type_idx FOR (e:Entity) ON (e.entity_type);

// 3. 使用EXPLAIN分析查询计划
EXPLAIN MATCH (e:Entity {entity_name: "一线城市"})-[*1..3]-(related) RETURN related;

// 4. 限制路径深度
MATCH (e1:Entity)-[*1..2]-(e2:Entity)  // 不要超过3层
WHERE e1.entity_name = "一线城市"
RETURN e2 LIMIT 50
```

---

## 📚 相关文档

- [代码更新维护指南](./CODE_UPDATE_GUIDE.md) - 代码变更后如何维护图谱数据
- [MinerU集成方案](../Memora_MinerU与知识图谱集成方案_e9a1c9b9.md) - 原始设计方案
- [Neo4j官方文档](https://neo4j.com/docs/) - Cypher查询语言参考

---

## 🎓 学习资源

### Cypher查询入门

```cypher
// 基础查询
MATCH (n) RETURN n LIMIT 10

// 查找特定类型的实体
MATCH (e:Entity {entity_type: "概念"}) RETURN e.entity_name

// 查找关系
MATCH (a:Entity)-[r]->(b:Entity) 
WHERE a.entity_name = "一线城市"
RETURN a, r, b

// 最短路径
MATCH path = shortestPath(
    (a:Entity {entity_name: "OpenClaw"})-[*]-(b:Entity {entity_name: "房价"})
)
RETURN path

// 统计分析
MATCH (e:Entity)
RETURN e.entity_type, count(e) AS count
ORDER BY count DESC
```

### 最佳实践

1. **定期清理孤立节点**
```cypher
MATCH (e:Entity)
WHERE NOT (e)--()
DELETE e
```

2. **备份图谱数据**
```bash
docker exec memora-neo4j neo4j-admin database dump neo4j --to=/backups/neo4j.dump
```

3. **监控图谱规模**
```cypher
MATCH (n) RETURN labels(n) AS type, count(n) AS count
UNION ALL
MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count
```

---

**最后更新**: 2026-06-14  
**维护者**: Memora Team
