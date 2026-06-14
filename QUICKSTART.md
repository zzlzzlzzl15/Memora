# Memora MinerU & 知识图谱集成 - 快速开始

## 🎯 已完成的工作

✅ 所有代码修改完成 (10/10任务)  
✅ 自动化检查通过 (22/22项)  
✅ 测试脚本已创建  

## 📦 文件清单

### 新增文件
- `.env.production` - 生产环境配置
- `check_integration.sh` - 集成检查脚本
- `deploy_verify.sh` - Docker部署验证脚本
- `quick_verify.py` - Python快速验证脚本
- `tests/test_mineru_integration.py` - 集成测试用例
- `IMPLEMENTATION_REPORT.md` - 完整实施报告

### 修改文件
- `requirements.txt` - 添加 magic-pdf
- `Dockerfile` - 添加系统依赖
- `app/services/entity_extractor.py` - 并发优化
- `app/services/knowledge_graph.py` - 批量写入
- `app/services/hybrid_fusion.py` - 查询模式扩展
- `app/services/document_service.py` - 图谱构建优化

## 🚀 快速开始

### 步骤1: 检查代码 (已完成)

```bash
bash check_integration.sh
```

**结果**: ✅ 22/22 通过

### 步骤2: 构建Docker镜像

```bash
docker-compose build
```

**预计时间**: 5-10分钟

### 步骤3: 启动服务

```bash
docker-compose up -d
```

**等待30秒让服务完全启动**

### 步骤4: 健康检查

```bash
bash deploy_verify.sh
```

或手动检查:
```bash
curl http://localhost:8000/health
curl http://localhost:7474  # Neo4j Browser
```

### 步骤5: 测试API

访问 API文档: http://localhost:8000/docs

## 🧪 测试方法

### 方法1: 使用Swagger UI

1. 打开 http://localhost:8000/docs
2. 选择 `/api/v1/documents/upload` 接口
3. 上传一个PDF文档
4. 查看返回结果

### 方法2: 使用curl命令

```bash
# 上传文档
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test.pdf"

# 搜索文档 (vector模式)
curl -X POST http://localhost:8000/api/v1/documents/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "机器学习", "query_mode": "vector"}'

# 搜索文档 (mix模式 - 推荐)
curl -X POST http://localhost:8000/api/v1/documents/search \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "机器学习", "query_mode": "mix"}'
```

### 方法3: 运行Python测试

```bash
# 在Docker容器内运行
docker exec -it memora-app python3 tests/test_mineru_integration.py
```

## 🔍 故障排查

### 查看日志

```bash
# 应用日志
docker-compose logs -f app

# Neo4j日志
docker-compose logs -f neo4j

# 查看所有服务
docker-compose logs -f
```

### 常见问题

**Q: MinerU解析失败?**
```bash
# 检查magic-pdf是否安装
docker exec -it memora-app python3 -c "import magic_pdf; print('OK')"
```

**Q: Neo4j连接失败?**
```bash
# 检查Neo4j服务状态
docker-compose ps neo4j

# 测试连接
docker exec -it memora-app python3 -c "
from app.services.knowledge_graph import get_knowledge_graph_service
kg = get_knowledge_graph_service()
print('Connected:', kg.available)
"
```

**Q: 实体提取没有结果?**
```bash
# 检查LLM配置
docker-compose logs app | grep "LLM"

# 查看实体提取日志
docker-compose logs app | grep "实体提取"
```

## 📊 监控和可视化

### Neo4j Browser

访问: http://localhost:7474  
用户名: neo4j  
密码: memora_neo4j_pass

执行Cypher查询:
```cypher
// 查看所有实体
MATCH (e:Entity) RETURN e LIMIT 25

// 查看关系
MATCH (e1:Entity)-[r]->(e2:Entity) RETURN e1, r, e2 LIMIT 25

// 统计
MATCH (e:Entity) RETURN count(e) AS entity_count
```

### Qdrant Dashboard

访问: http://localhost:6333/dashboard

查看向量集合、点数等信息。

## 🎓 查询模式说明

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| vector | 纯向量检索 | 快速语义搜索 |
| local | 实体匹配 → 局部子图 | 精确实体查询 |
| global | 关系遍历 → 全局推理 | 跨文档知识发现 |
| hybrid | local + global | 全面图谱查询 |
| mix | hybrid + vector | **最全面,推荐** |

## 📝 配置调优

编辑 `.env.production`:

```env
# MinerU配置
USE_MINERU=true              # 启用MinerU
MINERU_METHOD=auto           # auto/ocr/txt

# 并发控制
MULTIMODAL_MAX_PARALLEL=2    # VLM并发数(降低避免限速)
KG_ENTITY_MAX_PARALLEL=3     # 实体提取并发数(提高加快速度)

# 查询模式
KG_QUERY_MODE=mix            # 默认查询模式

# VLM配置
VLM_ENABLED=true
VLM_MODEL="qwen-vl-max"
```

修改后重启:
```bash
docker-compose restart app
```

## 📚 更多信息

- 详细实施报告: `IMPLEMENTATION_REPORT.md`
- RAG-Anything参考: `/Users/zzl/Desktop/个人文件夹/Memora/RAG-Anything`

## ✅ 验收清单

- [ ] Docker镜像构建成功
- [ ] 所有服务启动正常
- [ ] Neo4j可访问
- [ ] 上传PDF文档成功
- [ ] 实体提取有结果
- [ ] 知识图谱有数据
- [ ] Vector模式搜索可用
- [ ] Mix模式搜索可用
- [ ] fused_context返回非空

## 🎉 完成!

如果所有检查通过,恭喜您成功集成MinerU和知识图谱!

下一步建议:
1. 上传真实业务文档
2. 测试不同查询模式效果
3. 根据实际需求调优参数
4. 开发前端可视化界面

---

**需要帮助?** 查看 `IMPLEMENTATION_REPORT.md` 获取更多细节。
