# Memora 内存使用与架构分析报告

**生成时间**: 2026-06-14  
**分析范围**: 文档查询、向量检索、知识图谱、缓存机制

---

## 📊 一、当前内存使用情况分析

### 1.1 主要内存占用组件

| 组件 | 内存占用估算 | 是否可优化 | 风险等级 |
|------|------------|-----------|---------|
| **InMemoryDocumentStore** | ~50MB (100个文档) | ✅ 已优化 | 🟢 低 |
| **Embedding Model** | ~500MB-2GB | ⚠️ 需注意 | 🟡 中 |
| **Sparse Embedding Model** | ~200MB | ⚠️ 可选加载 | 🟡 中 |
| **Rerank Model** | ~300MB-1GB | ⚠️ 按需加载 | 🟡 中 |
| **Redis Client** | ~5MB | ✅ 外部服务 | 🟢 低 |
| **Qdrant Client** | ~10MB | ✅ 外部服务 | 🟢 低 |
| **Neo4j Driver** | ~5MB | ✅ 外部服务 | 🟢 低 |
| **FastAPI App** | ~100MB | - | 🟢 低 |
| **Python Runtime** | ~50MB | - | 🟢 低 |
| **总计** | **~1.2GB - 3.5GB** | - | - |

### 1.2 详细分析

#### ✅ 已优化的部分

**1. InMemoryDocumentStore (文档存储)**
```python
# 当前配置
max_cached_documents = 100  # 最多缓存100个完整文档

# 内存估算
- 每个文档平均大小: ~500KB (含content)
- 元数据: ~1KB/文档
- 总内存: 100 × 500KB + N × 1KB ≈ 50MB

# 优势
✅ LRU自动淘汰机制
✅ 元数据与内容分离
✅ 懒加载策略
```

**2. Redis缓存层**
```python
# 配置
REDIS_MAX_MEMORY = "256mb"
TTL = 3600秒 (1小时)
淘汰策略: allkeys-lru

# 实际占用
- 元数据: ~1KB/文档
- 1000个文档: ~1MB
- 10000个文档: ~10MB
- 远低于256MB限制 ✅
```

#### ⚠️ 潜在瓶颈

**1. Embedding模型 (最大风险点)**

```python
# 当前实现
class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer(settings.embedding_model)  # 常驻内存
        self.sparse_model = SparseTextEmbedding(...)  # 常驻内存
```

**问题分析:**
- ❌ 模型在应用启动时立即加载，无论是否有查询
- ❌ `SentenceTransformer` 默认加载到GPU/CPU，占用500MB-2GB
- ❌ 稀疏模型额外占用~200MB
- ❌ 如果启用rerank，再增加300MB-1GB

**场景模拟:**
```
假设用户只有10个文档，从未进行向量搜索：
- 当前: 模型仍占用~2GB内存 ❌
- 理想: 首次查询时才加载模型 ✅
```

**2. Rerank模型**

```python
# config/settings.py
use_rerank: bool = os.getenv("USE_RERANK", "true").lower() == "true"

# app/services/rerank.py
class RerankService:
    def __init__(self):
        self.model = CrossEncoder(settings.rerank_model)  # ~500MB
```

**问题:**
- ❌ 即使很少使用rerank，模型也常驻内存
- ❌ 对于小规模知识库，rerank收益有限但成本高

**3. 并发查询时的临时内存**

```python
# vector_store.py - 批量向量化
async def encode_texts(self, texts: List[str]):
    dense_embeddings = await self.embedding_service.encode_texts(texts)
    # 如果texts有1000个chunk，每个768维float32
    # 临时内存: 1000 × 768 × 4 bytes ≈ 3MB
    
    # 如果同时有10个用户上传文档
    # 峰值内存: 30MB+ (可接受)
```

---

## 🔍 二、文档查询流程内存分析

### 2.1 典型查询路径

```
用户请求: GET /api/v1/documents/{id}
    ↓
1. API层接收请求 (~1KB)
    ↓
2. DocumentService.get_document()
    ├─ 检查InMemoryDocumentStore缓存
    │   ├─ 命中: 直接返回 (~500KB)
    │   └─ 未命中: 
    │       ├─ 检查Redis缓存 (~1KB)
    │       └─ 从MySQL加载 (~500KB) → 写入缓存
    ↓
3. 返回Document对象 (~500KB)
    ↓
4. GC回收临时对象
```

**内存峰值**: ~1MB (单次查询)  
**并发100次**: ~100MB (可控) ✅

### 2.2 向量搜索查询

```
用户请求: POST /api/v1/search
    ↓
1. 接收查询文本 (~100B)
    ↓
2. EmbeddingService.encode_text()
    ├─ 加载模型到显存 (已在启动时完成)
    ├─ 计算嵌入向量: 768 floats ≈ 3KB
    ↓
3. QdrantClient.search()
    ├─ 发送RPC请求 (~10KB)
    ├─ 接收结果: top_k=10 chunks
    └─ 每个chunk: ~5KB × 10 = 50KB
    ↓
4. (可选) RerankService.rerank()
    ├─ 加载rerank模型 (已在启动时完成)
    ├─ 重排序10个结果
    └─ 临时内存: ~50KB
    ↓
5. 返回搜索结果 (~50KB)
```

**内存峰值**: ~200KB (单次查询)  
**并发100次**: ~20MB (可控) ✅

**⚠️ 关键问题**: 步骤2和4的模型虽然不随查询增长，但启动时就占用了大量内存。

---

## 🎯 三、架构合理性评估

### 3.1 优势 ✅

1. **分层缓存设计优秀**
   - L1: 内存LRU (100个文档) - 微秒级
   - L2: Redis (所有元数据) - 毫秒级
   - L3: MySQL (持久化) - 可靠
   - L4: Qdrant/Neo4j (向量/图谱) - 专业存储

2. **懒加载机制完善**
   - 文档内容按需加载
   - 避免启动时全量加载
   - LRU自动淘汰冷数据

3. **索引优化到位**
   - 多维度索引 (user/status/type)
   - 线程安全 (RLock)
   - 元数据轻量级

### 3.2 存在的问题 ⚠️

#### 问题1: AI模型常驻内存 (严重)

**现状:**
```python
# embedding.py - 启动时立即加载
def __init__(self):
    self._load_model()          # ~2GB
    self._load_sparse_model()   # ~200MB

# rerank.py - 启动时立即加载
def __init__(self):
    if settings.use_rerank:
        self.model = CrossEncoder(...)  # ~500MB
```

**影响:**
- 即使用户只有1个文档，也要占用~2.7GB内存
- 无法在低配服务器(如1GB RAM)上运行
- 资源利用率极低

**建议方案:**

**方案A: 延迟加载 (推荐)**
```python
class EmbeddingService:
    def __init__(self):
        self.model = None  # 不立即加载
        self._model_loaded = False
    
    def _ensure_model_loaded(self):
        """首次使用时加载模型"""
        if not self._model_loaded:
            logger.info("首次使用，加载embedding模型...")
            self.model = SentenceTransformer(...)
            self._model_loaded = True
    
    async def encode_text(self, text: str):
        self._ensure_model_loaded()  # 延迟加载
        # ... 正常编码
```

**优点:**
- ✅ 无查询时不占用模型内存
- ✅ 首次查询后常驻，后续快速
- ✅ 适合低频使用场景

**缺点:**
- ⚠️ 首次查询延迟增加5-10秒
- ⚠️ 需要处理并发加载竞争

---

**方案B: 模型卸载**
```python
class EmbeddingService:
    def __init__(self):
        self.model = None
        self._last_used_time = None
        self._idle_timeout = 3600  # 1小时未使用则卸载
    
    async def encode_text(self, text: str):
        if self.model is None:
            self._load_model()
        
        result = self.model.encode(text)
        self._last_used_time = time.time()
        return result
    
    def _check_and_unload(self):
        """定期检查并卸载空闲模型"""
        if (self._last_used_time and 
            time.time() - self._last_used_time > self._idle_timeout):
            logger.info("模型空闲超时，卸载以释放内存")
            del self.model
            self.model = None
            torch.cuda.empty_cache()  # 清理GPU显存
```

**优点:**
- ✅ 平衡内存和性能
- ✅ 适合间歇性使用场景

**缺点:**
- ⚠️ 需要后台线程定期检查
- ⚠️ 频繁加载/卸载有开销

---

**方案C: 轻量化模型 (推荐配合方案A)**
```python
# .env.production
EMBEDDING_MODEL=openai/text-embedding-v4  # API调用，零本地内存

# 或使用小型本地模型
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2  # ~80MB
```

**优点:**
- ✅ 大幅降低内存占用
- ✅ API方式零本地内存

**缺点:**
- ⚠️ API调用有网络延迟
- ⚠️ 需要API Key和费用

---

#### 问题2: 缺少内存监控

**现状:**
- ❌ 没有实时监控内存使用
- ❌ 无法预警内存泄漏
- ❌ 无法动态调整缓存大小

**建议:**
```python
# app/services/memory_monitor.py
import psutil
import tracemalloc

class MemoryMonitor:
    def __init__(self):
        tracemalloc.start()
    
    def get_memory_stats(self) -> Dict:
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,  # 物理内存
            "vms_mb": memory_info.vms / 1024 / 1024,  # 虚拟内存
            "document_cache_count": len(self.store.documents),
            "redis_keys": self.cache.get_stats()["total_keys"],
            "model_loaded": self.embedding.model is not None,
        }
    
    def check_threshold(self, threshold_mb=2048):
        """检查是否超过阈值"""
        stats = self.get_memory_stats()
        if stats["rss_mb"] > threshold_mb:
            logger.warning(f"内存使用过高: {stats['rss_mb']}MB")
            # 触发缓存清理
            self._emergency_cleanup()
```

---

#### 问题3: 并发控制不足

**现状:**
```python
# document_service.py
self.lock = threading.RLock()  # 全局锁

# 问题: 所有文档操作共用一个锁
# 高并发时会成为瓶颈
```

**建议:**
```python
# 细粒度锁 - 按用户或文档ID分片
class ShardedLock:
    def __init__(self, shards=16):
        self.shards = [threading.RLock() for _ in range(shards)]
    
    def get_lock(self, key: str):
        shard_id = hash(key) % len(self.shards)
        return self.shards[shard_id]

# 使用
lock = self.sharded_lock.get_lock(user_id)
with lock:
    # 操作该用户的文档
```

---

## 📈 四、优化建议优先级

### P0 - 立即实施 (高优先级)

1. **Embedding模型延迟加载**
   - 预计节省: 1.5-2GB内存
   - 实施难度: ⭐⭐
   - 影响: 首次查询慢5-10秒

2. **添加内存监控**
   - 预计收益: 及时发现问题
   - 实施难度: ⭐
   - 影响: 无负面影响

### P1 - 短期优化 (中优先级)

3. **Rerank模型可选加载**
   - 预计节省: 500MB-1GB
   - 实施难度: ⭐⭐
   - 配置项: `USE_RERANK=false`

4. **细粒度锁优化**
   - 预计收益: 提升并发性能30%
   - 实施难度: ⭐⭐⭐
   - 影响: 代码重构较大

### P2 - 长期规划 (低优先级)

5. **模型卸载机制**
   - 预计节省: 动态管理
   - 实施难度: ⭐⭐⭐⭐
   - 适用场景: 极低频使用

6. **切换到API Embedding**
   - 预计节省: 2GB+
   - 实施难度: ⭐⭐
   - 成本: API调用费用

---

## 🎯 五、结论

### 5.1 整体评价

**架构评分: 8/10** ⭐⭐⭐⭐

**优点:**
- ✅ 分层缓存设计合理
- ✅ 懒加载机制完善
- ✅ 索引优化到位
- ✅ 线程安全考虑周全

**缺点:**
- ❌ AI模型常驻内存是最大瓶颈
- ❌ 缺少内存监控和告警
- ❌ 并发控制可以更精细

### 5.2 内存瓶颈判断

**是否存在瓶颈?** 

**答案: 取决于使用场景**

| 场景 | 内存需求 | 是否瓶颈 |
|------|---------|---------|
| **个人使用 (<100文档)** | ~1.5GB | 🟢 否 |
| **小团队 (<1000文档)** | ~2GB | 🟢 否 |
| **中型企业 (<10000文档)** | ~2.5GB | 🟡 临界 |
| **大规模部署 (>10000文档)** | ~3GB+ | 🔴 是 |

**关键发现:**
- 文档存储本身已优化良好 (50MB)
- **真正的瓶颈是AI模型** (2-3GB)
- 对于90%的用户，当前架构完全够用
- 只有在低配服务器(1GB RAM)或大规模部署时才需要优化

### 5.3 推荐行动

**立即执行:**
1. 添加内存监控端点 `/api/v1/system/memory`
2. 实现Embedding模型延迟加载
3. 提供配置项禁用Rerank (`USE_RERANK=false`)

**观察指标:**
- RSS内存使用趋势
- 模型加载频率
- 缓存命中率
- 并发查询数

**决策依据:**
- 如果RSS < 2GB且稳定 → 无需进一步优化
- 如果RSS > 3GB或持续增长 → 实施P0/P1优化
- 如果部署在1GB服务器 → 必须实施方案A+C

---

## 📝 六、附录

### 6.1 内存计算公式

```python
总内存 = 
  Python基础 (~50MB) +
  FastAPI框架 (~100MB) +
  文档缓存 (N_docs × 500KB, max 100) +
  Redis客户端 (~5MB) +
  Embedding模型 (500MB-2GB) +
  Sparse模型 (200MB, 可选) +
  Rerank模型 (500MB, 可选) +
  其他依赖 (~50MB)

最小配置 (禁用sparse+rerank):
  = 50 + 100 + 50 + 5 + 500 + 50 = ~755MB

最大配置 (全部启用):
  = 50 + 100 + 50 + 5 + 2000 + 200 + 1000 + 50 = ~3.5GB
```

### 6.2 监控脚本示例

```bash
#!/bin/bash
# monitor_memory.sh

while true; do
    RSS=$(docker stats memora-app --format "{{.MemUsage}}" | cut -d'/' -f1)
    echo "$(date): Memora RSS = $RSS"
    sleep 60
done
```

### 6.3 健康检查端点建议

```python
# app/api/system.py
@router.get("/system/memory")
async def get_memory_stats():
    """获取系统内存使用情况"""
    monitor = get_memory_monitor()
    return monitor.get_memory_stats()

# 返回示例
{
  "rss_mb": 1250.5,
  "vms_mb": 2100.3,
  "document_cache": {
    "cached_docs": 45,
    "max_cache": 100,
    "metadata_docs": 150
  },
  "redis": {
    "connected": true,
    "keys": 150,
    "memory_used": "2.5MB"
  },
  "models": {
    "embedding_loaded": true,
    "sparse_loaded": false,
    "rerank_loaded": false
  }
}
```

---

**报告结束**
