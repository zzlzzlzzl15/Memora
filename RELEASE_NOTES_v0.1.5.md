# Memora v0.1.5 Release Notes

> 本次版本聚焦 **上传体验修复 + 静态资源缓存根治 + 关键安全/部署文件 .gitignore 修复**。

## 1. 上传文档标题自动 fallback

**问题**：用户选好文件但没填标题时，前端弹 `请选择文件并填写标题` 拒绝上传，违背「选好文件就能传」的直觉。

**修复**（前端 + 后端两层防御）：

### 前端 [static/script.js](static/script.js)
- 标题为空时 fallback 到 `file.name.replace(/\.[^./\\]+$/, '')`（去除最后一段扩展名）
- 例：`MyNotes.md` → 标题 `MyNotes`
- 用户填的标题优先

### 后端 [app/api/documents.py](app/api/documents.py)
- `title: str = Form(...)` → `title: Optional[str] = Form(None)`
- endpoint 内 fallback 到 `Path(file.filename).stem`
- 与前端逻辑保持一致

**覆盖范围**：两处上传函数都已修复
- `uploadDocument()`（主上传页 [script.js:2007](static/script.js#L2007)）
- `submitFileSource()`（Source Modal [script.js:2165](static/script.js#L2165)）

## 2. 静态资源缓存根治

**问题**：用户改完前端 JS，浏览器还是用旧版本（service worker / disk cache 命中）。

**修复**：

### [static/index.html](static/index.html)
- 改 query string：`?v=astronaut-theme-20260616` → `?v=v0.3.5-20261014-2358`
- URL 变了浏览器**强制**重新拉

### [app/main.py](app/main.py)
- `/` 路由加 `Cache-Control: no-cache, no-store, must-revalidate`
- `/static/*` 用 `NoCacheStaticFiles` 类同样加 no-cache 头
- 双管齐下避免浏览器缓存前端资源

**用户操作**：浏览器按 **F5 普通刷新** 即可拿到最新版（不需要硬刷新）。

## 3. Docker Compose 改进：app 代码 bind mount

**问题**：之前改 `app/*.py` 要 `docker compose build app` 重新打 image，调试慢。

**修复** [docker-compose.yml](docker-compose.yml)：
- 加 `./app:/app/app` bind mount
- 改完 `app/*.py` 后 `docker compose restart app` 立即生效（不用 rebuild）

## 4. 关键 .gitignore 修复

### 安全相关
- **加** `.env.production`（含 API key / MySQL root password / Neo4j password）
- **加** `.env.production.bak.*`（备份文件含 token）
- **加** `.env.production.example`（未来用，提交无 token 模板）

### Runtime 文件
- **加** `.memora.pid`（runtime 进程 PID）
- **加** `nohup.out`（runtime 日志）

### 部署文件错误 ignore 修复（v0.1.5 之前）
- **删** `Dockerfile`（之前错误 ignore，导致 Dockerfile 改动从未进过 git）
- **删** `docker-compose*.yml`（同上）
- 保留 `.dockerignore`

## 5. 其他改进

### [app/services/document_service.py](app/services/document_service.py)
- 文档上传后**后台异步**向量化（`asyncio.create_task`），不阻塞上传接口

### [app/services/knowledge_graph.py](app/services/knowledge_graph.py)
- 加 `_serialize_value()` 静态方法，Neo4j 值（datetime、Node、Relationship）正确转 JSON

### [Dockerfile](Dockerfile)
- 改回默认 deb 源（清华 Trixie mirror 不稳定）

## 6. 元数据

- `config/settings.py`: `0.1.4` → `0.1.5`

## 7. ⚠️ 安全建议

**重要**：v0.1.5 之前 `.env.production` **已 tracked** 在 git history 里（2 个 commit：`1f11022` 和 `fc750a4`），含**真实 API keys**。

**建议立即做**：
1. **轮换所有 API key**：
   - DashScope / OpenAI API key
   - LLM（Minimax）Agent Plan key
   - Qdrant API key
   - MySQL root password
   - Neo4j password
   - SMTP password
2. 本次 release **不**含**新** token（已 `git checkout` 回滚 `.env.production` 改动 + 加 `.gitignore` 阻止未来误提交）
3. **历史清理**（可选，危险操作）：用 [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/) 或 `git filter-branch` 从 history 删除 `.env.production`（**会改写所有 commit hash**）

## 8. 升级方式

```bash
git pull
docker compose restart app    # 不用 rebuild image（bind mount 改动立即生效）
```

浏览器**F5 普通刷新**拿前端新代码。
