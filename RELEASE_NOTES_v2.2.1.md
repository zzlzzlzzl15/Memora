# Memora v2.2.1 Release Notes

> 本次版本是 **v2.2.0 的小补丁**：对齐版本号，**没有功能变更**，仅做版本号 bump。

## 1. 版本号对齐 2.2.0 → 2.2.1

v2.2.0 release commit (3036e9b, 2026-09-30) **没有为 v2.2.0 打 git tag**，且 CSS cache 版本字符串停留在 `kg-v2.2.0-20260930`。

本次同步修正：

| 文件 | 旧值 | 新值 |
|---|---|---|
| `VERSION` | `2.2.0` | `2.2.1` |
| `package.json` | `"version": "2.2.0"` | `"version": "2.2.1"` |
| `static/index.html` | `style.css?v=kg-v2.2.0-20260930` | `style.css?v=kg-v2.2.1-20261015` |

## 2. 元数据

- `VERSION`: 2.2.0 → **2.2.1**
- `package.json`: 2.2.0 → **2.2.1**
- `static/index.html` CSS cache buster: `kg-v2.2.0-20260930` → **`kg-v2.2.1-20261015`**
- 仓库 git tag: 新增 **`v2.2.1`**（v2.2.0 当时未打）

## 3. 不变项

- 应用代码（`app/`、`config/`、`docker-compose.yml`、`Dockerfile`）：**无变更**
- 文档：`README.md` / `CHANGELOG.md` / `SKILL.md`：**无变更**
  - 注：CHANGELOG.md / SKILL.md 受 `.gitignore` `*.md` 规则约束，本就不跟踪
- App 内部版本号 `config/settings.py: app_version`：保持 `0.1.5`（与 Memora 仓库版本号分离，独立维护）

## 4. 升级方式

```bash
git pull
docker compose restart app    # 不用 rebuild image（bind mount 改动立即生效）
```

浏览器 **F5 普通刷新** 拿到新版本（CSS cache 已带新 query string）。