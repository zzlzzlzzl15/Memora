# 内存监控使用指南

## 📊 功能概述

Memora现已内置**实时内存监控系统**,帮助您:
- 🔍 实时监控内存使用情况
- ⚠️ 预警内存超标风险
- 🧹 紧急清理释放内存
- 🏥 全面健康检查

---

## 🚀 API端点

### 1. 获取内存统计

**端点**: `GET /api/v1/system/memory`

**功能**: 获取详细的内存使用统计

**示例**:
```bash
curl http://localhost:8000/api/v1/system/memory | python3 -m json.tool
```

**响应示例**:
```json
{
  "timestamp": "2026-06-14T09:30:00",
  "process": {
    "rss_mb": 1250.5,
    "vms_mb": 2100.3,
    "percent": 15.6
  },
  "system": {
    "total_gb": 16.0,
    "available_gb": 8.5,
    "used_percent": 46.8
  },
  "components": {
    "document_cache": {
      "cached_documents": 45,
      "metadata_documents": 150,
      "max_cache_size": 100,
      "cache_usage_percent": 45.0
    },
    "redis_cache": {
      "enabled": true,
      "connected": true,
      "total_keys": 150,
      "used_memory_human": "2.5MB",
      "max_memory_human": "256.0MB",
      "ttl_seconds": 3600
    },
    "embedding_model": {
      "loaded": true,
      "provider": "sentence",
      "sparse_enabled": false,
      "sparse_loaded": false
    },
    "rerank_model": {
      "enabled": true,
      "loaded": true
    }
  }
}
```

**关键字段说明**:
- `rss_mb`: 物理内存占用(MB) - **最重要指标**
- `cached_documents`: L1缓存中的完整文档数
- `metadata_documents`: 元数据总数
- `embedding_model.loaded`: Embedding模型是否已加载

---

### 2. 检查内存阈值

**端点**: `GET /api/v1/system/memory/check?threshold_mb=2048`

**功能**: 检查当前内存是否超过指定阈值

**参数**:
- `threshold_mb`: 内存阈值(MB),默认2048

**示例**:
```bash
curl "http://localhost:8000/api/v1/system/memory/check?threshold_mb=2048" | python3 -m json.tool
```

**响应示例**:
```json
{
  "threshold_mb": 2048,
  "current_mb": 1250.5,
  "exceeded": false,
  "usage_percent": 61.06,
  "recommendation": "内存使用正常"
}
```

**recommendation可能值**:
- ✅ "内存使用正常" - < 80%阈值
- ℹ️ "接近阈值,建议关注内存增长趋势" - 80%-100%
- ⚠️ "超过阈值,建议监控趋势并考虑优化" - 100%-150%
- 🚨 "严重超标! 建议立即清理缓存或重启服务" - > 150%

---

### 3. 紧急清理内存

**端点**: `POST /api/v1/system/memory/cleanup`

**功能**: 执行紧急内存清理

**⚠️ 警告**: 
- 会清空所有缓存
- 后续查询会变慢(需重新加载)
- 仅在内存严重超标时使用

**示例**:
```bash
curl -X POST http://localhost:8000/api/v1/system/memory/cleanup | python3 -m json.tool
```

**响应示例**:
```json
{
  "success": true,
  "cleanup_result": {
    "timestamp": "2026-06-14T09:35:00",
    "actions": [
      {
        "action": "clear_document_cache",
        "cleared_count": 45,
        "success": true
      },
      {
        "action": "clear_redis_cache",
        "cleared": true,
        "success": true
      },
      {
        "action": "force_garbage_collection",
        "collected_objects": 1234,
        "success": true
      }
    ],
    "after_cleanup": {
      "process": {
        "rss_mb": 850.2,
        ...
      }
    }
  }
}
```

---

### 4. 详细健康检查

**端点**: `GET /api/v1/system/health/detailed`

**功能**: 全面的系统健康检查

**示例**:
```bash
curl http://localhost:8000/api/v1/system/health/detailed | python3 -m json.tool
```

**响应示例**:
```json
{
  "status": "healthy",
  "checks": {
    "memory": {
      "status": "ok",
      "rss_mb": 1250.5,
      "usage_percent": 15.6
    },
    "redis": {
      "status": "ok"
    },
    "qdrant": {
      "status": "ok"
    },
    "neo4j": {
      "status": "ok"
    }
  }
}
```

**status可能值**:
- `healthy`: 所有组件正常
- `degraded`: 部分组件异常,但核心功能可用
- `unhealthy`: 关键组件故障

---

## 📈 监控最佳实践

### 1. 定期监控

**推荐频率**: 每5-10分钟检查一次

**脚本示例**:
```bash
#!/bin/bash
# monitor.sh

while true; do
    RSS=$(curl -s http://localhost:8000/api/v1/system/memory | \
          python3 -c "import sys,json; print(json.load(sys.stdin)['process']['rss_mb'])")
    
    echo "$(date): RSS = ${RSS}MB"
    
    if (( $(echo "$RSS > 2048" | bc -l) )); then
        echo "⚠️ 内存超过2GB!"
        # 发送告警邮件/消息
    fi
    
    sleep 300  # 5分钟
done
```

---

### 2. 设置告警阈值

**推荐配置**:

| 服务器配置 | 警告阈值 | 紧急阈值 | 行动 |
|-----------|---------|---------|------|
| 2GB RAM | 1.5GB | 1.8GB | 清理缓存 |
| 4GB RAM | 3GB | 3.5GB | 清理缓存 |
| 8GB RAM | 6GB | 7GB | 观察趋势 |
| 16GB RAM | 12GB | 14GB | 无需担心 |

---

### 3. 集成Prometheus + Grafana (高级)

**步骤**:

1. **安装prometheus-client**:
```bash
pip install prometheus-client
```

2. **暴露metrics端点**:
```python
# app/api/system.py
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

@router.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

3. **配置Prometheus抓取**:
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'memora'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/system/metrics'
```

4. **Grafana仪表盘**:
   - 导入预设模板
   - 监控RSS、缓存命中率、模型状态等

---

## 🔧 故障排查

### 问题1: 内存持续增长

**症状**: RSS持续上升,不下降

**排查步骤**:

1. **检查是否有内存泄漏**:
```bash
# 每小时记录一次
curl http://localhost:8000/api/v1/system/memory | jq '.process.rss_mb' >> memory.log
```

2. **查看增长趋势**:
```bash
# 绘制图表
python3 -c "
import matplotlib.pyplot as plt
data = [float(line.strip()) for line in open('memory.log')]
plt.plot(data)
plt.xlabel('Hours')
plt.ylabel('RSS (MB)')
plt.title('Memory Growth Trend')
plt.show()
"
```

3. **如果确认泄漏**:
   - 检查是否有未关闭的数据库连接
   - 检查是否有循环引用
   - 执行紧急清理测试是否能恢复

---

### 问题2: 首次查询很慢

**原因**: Embedding模型延迟加载

**解决**:
- 这是正常现象(5-10秒)
- 后续查询会很快
- 如需优化,可改为启动时加载

---

### 问题3: 缓存命中率低

**检查**:
```bash
curl http://localhost:8000/api/v1/system/memory | jq '.components.document_cache'
```

**如果`cache_usage_percent`很低**:
- 可能是用户访问模式分散
- 考虑增加`max_cached_documents`(在settings中)
- 或接受较低的命中率

---

## 📊 关键指标解读

### RSS (Resident Set Size)

**定义**: 进程实际占用的物理内存

**正常范围**:
- 小型部署(<100文档): 800MB-1.5GB
- 中型部署(<1000文档): 1.5GB-2.5GB
- 大型部署(>1000文档): 2.5GB-4GB

**异常信号**:
- 持续增长不下降 → 可能泄漏
- 突然飙升 → 可能有大量并发
- 超过80%系统内存 → 需要优化

---

### 缓存命中率

**计算**: `cached_documents / max_cache_size`

**理想值**:
- > 70%: 优秀
- 50%-70%: 良好
- 30%-50%: 一般
- < 30%: 需要优化

**提升方法**:
- 增加`max_cached_documents`
- 分析用户访问模式,预加载热点文档

---

### 模型加载状态

**embedding_model.loaded**:
- `true`: 模型已加载,占用~2GB
- `false`: 模型未加载,节省内存但首次查询慢

**建议**:
- 高频使用 → 保持加载
- 低频使用 → 考虑卸载机制

---

## 🎯 总结

**日常监控清单**:

- [ ] 每天检查一次RSS趋势
- [ ] 每周检查缓存命中率
- [ ] 每月评估是否需要调整配置
- [ ] 设置自动化告警(>80%阈值)

**应急处理流程**:

1. 发现内存超标
2. 调用 `/api/v1/system/memory/check` 确认
3. 如严重超标,调用 `/api/v1/system/memory/cleanup`
4. 观察清理后效果
5. 如无效,重启服务
6. 分析根本原因

---

**祝您监控愉快! 🎉**
