# Memora 代码更新与数据维护指南

本文档说明在更新Memora代码后,如何确保已有文档的正常查找、载入和查询。

## 📊 数据存储架构

Memora使用多层存储架构:

```
┌─────────────────────────────────────────┐
│         应用层 (Python代码)              │
│  • DocumentService                       │
│  • DocumentProcessor                     │
│  • EmbeddingService                      │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┼──────────┬──────────────┐
    ▼          ▼          ▼              ▼
────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐
│ MySQL  │ │ Memory │ │ Qdrant │ │ File System  │
│ 元数据  │ │ 缓存   │ │ 向量库  │ │ 原始文件      │
└────────┘ └──────── └────────┘ └──────────────┘
```

### 各层职责:

| 存储层 | 内容 | 更新影响 | 持久性 |
|--------|------|----------|--------|
| **MySQL** | 文档ID、标题、状态、路径、标签等元数据 |  无影响 | 永久 |
| **Memory** | 运行时Document对象缓存 | ️ 重启清空 | 临时 |
| **Qdrant** | 文档向量嵌入(embeddings) | ⚠️ 模型变更需重建 | 永久 |
| **File System** | 原始PDF/TXT文件、解析缓存 | ❌ 无影响 | 永久 |

---

## ✅ 安全更新的场景(无需额外操作)

以下代码更新**不会影响**已有文档的正常使用:

### 1. API接口层更新
- 修改 `app/api/*.py` 中的路由逻辑
- 添加新的API端点
- 修改请求/响应格式

**影响**: 仅影响新请求的处理方式,不影响已存储数据

### 2. 业务逻辑优化
- 优化 `document_service.py` 中的查询逻辑
- 改进错误处理
- 性能优化

**影响**: 提升性能,不影响数据完整性

### 3. UI/前端更新
- 修改 `static/*.html`, `static/*.js`, `static/*.css`
- 调整页面布局、交互逻辑

**影响**: 仅改变展示方式,不影响后端数据

### 4. 配置参数调整
- 修改 `.env.production` 中的非关键参数
- 调整日志级别、超时时间等

**影响**: 运行时行为变化,不影响历史数据

---

## ⚠️ 需要额外处理的场景

以下代码更新**可能影响**已有文档,需要采取相应措施:

### 1. 文档解析器更新 (`document_processor.py`)

**场景**: 
- 更新了PDF解析逻辑(如集成MinerU新版本)
- 修改了文本提取算法
- 调整了解析缓存格式

**影响**: 
- 新上传文档使用新解析逻辑
- 已有文档仍使用旧解析结果(存储在文件系统)

**解决方案**:

#### 方案A: 保持兼容(推荐)
```python
# 在 document_processor.py 中添加版本标识
PARSER_VERSION = "v2.0"

def parse_document(file_path: str, doc_id: str) -> ParsedResult:
    # 检查是否已有解析缓存
    cache_key = f"{doc_id}_{PARSER_VERSION}"
    if cache_exists(cache_key):
        return load_from_cache(cache_key)
    
    # 否则使用新解析器
    result = new_parser(file_path)
    save_to_cache(cache_key, result)
    return result
```

#### 方案B: 批量重新解析
```bash
# 创建重新解析脚本 reparse_all.py
#!/usr/bin/env python3
"""重新解析所有文档以应用新的解析逻辑"""

from app.services.document_service import get_document_service
from app.core.sql import get_db
from app.models.db_models import DocumentORM

def reparse_all_documents():
    db = next(get_db())
    documents = db.query(DocumentORM).filter(
        DocumentORM.is_deleted == False
    ).all()
    
    document_service = get_document_service()
    
    for doc in documents:
        print(f"重新解析文档: {doc.title} ({doc.doc_id})")
        try:
            # 触发重新处理
            await document_service.reprocess_document(doc.doc_id, doc.user_id)
        except Exception as e:
            print(f"失败: {e}")

if __name__ == "__main__":
    reparse_all_documents()
```

**执行步骤**:
```bash
cd /Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base
docker exec -it memora-app python reparse_all.py
```

### 2. 分块策略更新 (`chunking_strategy.py`)

**场景**:
- 修改了文本分块算法(如从固定长度改为语义分块)
- 调整了chunk大小、重叠窗口等参数

**影响**:
- 新文档使用新分块策略
- 已有文档的chunks仍在Qdrant中,但可能与新策略不一致

**解决方案**:

#### 方案A: 双版本共存
```python
# chunking_strategy.py
CHUNKING_VERSION = "v2"

def chunk_text(text: str, doc_id: str, version: str = None) -> List[Chunk]:
    version = version or CHUNKING_VERSION
    
    if version == "v1":
        return legacy_chunk(text)
    elif version == "v2":
        return semantic_chunk(text)
    else:
        raise ValueError(f"Unknown version: {version}")
```

#### 方案B: 重建向量索引
```bash
# 创建重建脚本 rebuild_vectors.py
#!/usr/bin/env python3
"""重建所有文档的向量索引"""

import asyncio
from app.services.document_service import get_document_service
from app.core.sql import get_db
from app.models.db_models import DocumentORM

async def rebuild_all_vectors():
    db = next(get_db())
    documents = db.query(DocumentORM).filter(
        DocumentORM.is_deleted == False,
        DocumentORM.status.in_(['completed', 'indexed'])
    ).all()
    
    document_service = get_document_service()
    
    for doc in documents:
        print(f"重建向量: {doc.title} ({doc.doc_id})")
        try:
            # 删除旧向量
            await document_service.vector_store.delete_document_vectors(
                doc.doc_id, doc.user_id
            )
            
            # 重新处理(会生成新向量)
            await document_service._process_document_vectors(doc)
        except Exception as e:
            print(f"失败: {e}")

if __name__ == "__main__":
    asyncio.run(rebuild_all_vectors())
```

### 3. Embedding模型变更

**场景**:
- 更换了embedding模型(如从OpenAI改为本地模型)
- 更新了模型版本

**影响**:
- **严重**: 不同模型的向量空间不兼容,无法混用
- 必须重新向量化所有文档

**解决方案**:

#### 完整迁移流程:

```bash
# 1. 备份当前Qdrant数据
docker stop memora-qdrant
tar -czf qdrant_backup.tar.gz -C /path/to/qdrant_data .

# 2. 修改 .env.production 中的embedding配置
# EMBEDDING_MODEL=new-model-name
# EMBEDDING_API_KEY=new-key

# 3. 清空Qdrant集合
docker start memora-qdrant
curl -X DELETE http://localhost:6333/collections/central_library

# 4. 运行迁移脚本
docker exec -it memora-app python migrate_embeddings.py

# 5. 验证
curl http://localhost:8000/api/v1/documents/search/quick?q=test
```

**迁移脚本 `migrate_embeddings.py`**:
```python
#!/usr/bin/env python3
"""迁移所有文档到新的embedding模型"""

import asyncio
from app.services.document_service import get_document_service
from app.core.sql import get_db
from app.models.db_models import DocumentORM

async def migrate_all_embeddings():
    db = next(get_db())
    documents = db.query(DocumentORM).filter(
        DocumentORM.is_deleted == False,
        DocumentORM.status.in_(['completed', 'indexed'])
    ).all()
    
    document_service = get_document_service()
    total = len(documents)
    
    print(f"开始迁移 {total} 个文档的向量...")
    
    for i, doc in enumerate(documents, 1):
        print(f"[{i}/{total}] 迁移: {doc.title}")
        try:
            # 删除旧向量
            await document_service.vector_store.delete_document_vectors(
                doc.doc_id, doc.user_id
            )
            
            # 重新生成向量(使用新模型)
            await document_service._process_document_vectors(doc)
            
            # 更新状态
            doc.status = 'indexed'
            db.commit()
            
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            doc.status = 'failed'
            doc.error_message = str(e)
            db.commit()
    
    print(f"\n迁移完成! 成功: {sum(1 for d in documents if d.status == 'indexed')}")

if __name__ == "__main__":
    asyncio.run(migrate_all_embeddings())
```

### 4. 数据库模型变更 (`db_models.py`)

**场景**:
- 添加了新字段到 `DocumentORM`
- 修改了字段类型
- 添加了新表

**影响**:
- 需要数据库迁移(Migration)

**解决方案**:

#### 使用Alembic进行数据库迁移:

```bash
# 1. 安装Alembic
pip install alembic

# 2. 初始化
cd /Users/zzl/Desktop/个人文件夹/Memora/personal_knowledge_base
alembic init migrations

# 3. 配置 migrations/alembic.ini
# sqlalchemy.url = mysql+pymysql://root:memora_mysql_root_pass_2024@mysql:3306/personal_knowledgebase

# 4. 创建迁移脚本
alembic revision --autogenerate -m "Add progress and error_message columns"

# 5. 查看生成的脚本 migrations/versions/xxx_xxx.py
# 手动调整如果需要

# 6. 应用迁移
alembic upgrade head

# 7. 验证
docker exec memora-mysql mysql -uroot -pmemora_mysql_root_pass_2024 \
  personal_knowledgebase -e "DESCRIBE documents;"
```

---

## 🔄 标准更新流程

### 场景1: 小更新(API/UI优化)

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 构建新镜像
cd personal_knowledge_base
docker compose build app

# 3. 重启服务
docker compose up -d app

# 4. 验证
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/documents/
```

**✅ 已有文档完全不受影响**

### 场景2: 中等更新(解析器/分块策略)

```bash
# 1-3. 同上

# 4. 选择性重新处理受影响的文档
# 方法A: 通过API逐个触发
curl -X POST http://localhost:8000/api/v1/documents/{doc_id}/reprocess

# 方法B: 批量重新处理(见上文脚本)
docker exec -it memora-app python reparse_all.py

# 5. 验证搜索结果
curl http://localhost:8000/api/v1/documents/search/quick?q=关键词
```

### 场景3: 重大更新(Embedding模型/核心架构)

```bash
# 1. 备份数据
docker stop memora-qdrant memora-mysql
tar -czf backup_$(date +%Y%m%d).tar.gz \
  qdrant_data/ mysql_data/ uploads/

# 2. 备份数据库
docker exec memora-mysql mysqldump -uroot -pmemora_mysql_root_pass_2024 \
  personal_knowledgebase > backup_$(date +%Y%m%d).sql

# 3. 更新代码并构建
git pull origin main
docker compose build app

# 4. 启动服务
docker compose up -d

# 5. 运行迁移脚本
docker exec -it memora-app python migrate_embeddings.py

# 6. 全面测试
# - 文档列表
# - 文档详情  
# - 搜索功能
# - 知识图谱

# 7. 确认无误后清理备份(保留至少7天)
```

---

## 📋 检查清单

每次代码更新后,执行以下检查:

### 基础检查
- [ ] 服务正常启动 (`docker compose ps`)
- [ ] 健康检查通过 (`curl http://localhost:8000/health`)
- [ ] 文档列表正常 (`curl http://localhost:8000/api/v1/documents/`)

### 数据完整性检查
- [ ] 文档数量正确 (对比更新前后)
- [ ] 文档详情可访问 (随机抽样5-10个)
- [ ] 文件可下载 (检查原始文件完整性)

### 功能检查
- [ ] 搜索功能正常 (测试几个关键词)
- [ ] 新文档上传正常
- [ ] 文档删除/恢复正常

### 性能检查
- [ ] API响应时间在可接受范围
- [ ] 内存使用正常 (`docker stats memora-app`)
- [ ] 数据库连接池正常

---

## 🛡️ 最佳实践

### 1. 版本控制
- 为解析器、分块策略、embedding模型添加版本号
- 在缓存key中包含版本标识
- 支持多版本共存和平滑迁移

### 2. 向后兼容
- 尽量保持API接口向后兼容
- 新增字段设置默认值
- 废弃字段标记为deprecated而非直接删除

### 3. 数据备份
- 定期自动备份(每周一次)
- 重大更新前手动备份
- 备份验证(定期测试恢复)

### 4. 灰度发布
- 先在测试环境验证
- 生产环境分批更新(如有多个实例)
- 保留回滚方案

### 5. 监控告警
- 监控文档加载成功率
- 监控向量检索准确率
- 设置异常告警阈值

---

## 🆘 故障恢复

### 场景1: 更新后发现文档丢失

**症状**: API返回空列表,但MySQL中有数据

**原因**: 应用启动时未加载文档到内存

**解决**:
```bash
# 1. 检查日志
docker logs memora-app | grep "加载.*文档"

# 2. 如果没有看到加载日志,检查代码
# 确认 app/main.py 中调用了 load_documents_from_db()

# 3. 手动触发加载
docker restart memora-app

# 4. 验证
curl http://localhost:8000/api/v1/documents/
```

### 场景2: 搜索无结果

**症状**: 文档存在但搜索不到

**原因**: Qdrant向量索引损坏或未同步

**解决**:
```bash
# 1. 检查Qdrant状态
curl http://localhost:6333/collections/central_library

# 2. 检查文档向量ID
docker exec memora-mysql mysql -uroot -pmemora_mysql_root_pass_2024 \
  personal_knowledgebase -e "SELECT doc_id, vector_id FROM documents LIMIT 5;"

# 3. 如果vector_id为空,重新向量化
docker exec -it memora-app python -c "
from app.services.document_service import get_document_service
import asyncio

async def fix():
    ds = get_document_service()
    doc = ds.store.get_document('文档ID')
    await ds._process_document_vectors(doc)

asyncio.run(fix())
"

# 4. 如果问题普遍,重建所有向量(见上文脚本)
```

### 场景3: 解析失败

**症状**: 文档状态为failed,错误信息显示解析异常

**原因**: 解析器代码有bug或依赖缺失

**解决**:
```bash
# 1. 查看详细错误
docker exec memora-mysql mysql -uroot -pmemora_mysql_root_pass_2024 \
  personal_knowledgebase -e "SELECT doc_id, error_message FROM documents WHERE status='failed';"

# 2. 检查应用日志
docker logs memora-app | grep -A 10 "ERROR.*parse"

# 3. 修复代码后重新处理
curl -X POST http://localhost:8000/api/v1/documents/{doc_id}/reprocess
```

---

## 📞 获取帮助

如遇问题:

1. 查看应用日志: `docker logs memora-app --tail 100`
2. 查看数据库状态: `docker exec memora-mysql mysql -uroot -p密码 personal_knowledgebase -e "SHOW TABLES;"`
3. 查看Qdrant状态: `curl http://localhost:6333/collections`
4. 参考本文档的故障恢复章节

---

**最后更新**: 2026-06-14  
**维护者**: Memora Team
