# Memora - 个人 AI 知识库系统

<p align="center">
  <img src="https://img.shields.io/badge/version-2.0.3-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/python-3.11+-orange.svg" alt="Python">
  <img src="https://img.shields.io/badge/docker-ready-brightgreen.svg" alt="Docker">
</p>

**Memora** 是一个自托管的个人 AI 知识库系统，提供从知识沉淀到智能问答的一体化体验。基于向量检索、混合搜索和 LLM 驱动的智能整理，帮助您高效管理、检索和利用个人知识资产。

##  核心特性

### 🔐 隐私保护与本地部署
- **完全私有化**：数据存储在本地，无需上传至第三方平台
- **离线可用**：支持离线模式，网络中断时仍可正常使用
- **单用户免认证**：开箱即用，无需复杂的用户管理系统

###  智能语义检索
- **混合检索策略**：稠密向量 + BM42 稀疏向量双引擎检索
- **相关性重排序**：可选 Rerank 模型对结果二次排序，提升准确率
- **降级容错机制**：自动回退到备用检索策略，确保服务可用性
- **语义级理解**：基于向量相似度而非关键词匹配，精准理解查询意图

###  多格式文档处理
- **支持格式**：PDF、Word (.docx/.doc)、纯文本 (.txt)、Markdown (.md)
- **智能分块**：使用 LangChain 递归字符分割器，兼容中英文标点
- **向量化存储**：同时生成稠密向量和稀疏向量，存入 Qdrant 数据库
- **元数据管理**：支持标签、自定义元数据，便于文档组织

### 💬 AI 驱动的智能问答
- **两种交互模式**：
  - **知识查询**：基于检索结果的精准问答
  - **知识梳理**：LLM 自动整理和总结检索到的知识
- **流式输出**：实时显示生成内容，提升交互体验
- **会话管理**：支持多轮对话和历史记录保存
- **引用溯源**：答案附带来源文档链接，方便验证

### 🕸️ 知识图谱可视化 (v2.0+)
- **力导向布局**：自动计算节点位置，形成自然的网络结构
- **双视图展示**：文档关系图谱 + 实体关系图谱
- **交互式操作**：
  - 鼠标滚轮缩放（以光标为中心）
  - 拖拽空白区域平移画布
  - 拖拽节点重新定位
  - 悬停显示详细信息
- **Obsidian 风格设计**：黑色节点、白色背景、微妙的连接线

### 🌐 网页抓取与集成
- **内置爬虫**：使用 httpx + BeautifulSoup，无外部依赖
- **OpenClaw 集成**：作为 AI Agent Skill，支持零依赖客户端调用
- **API 接口**：RESTful API，便于与其他系统集成

## ️ 技术架构

```
─────────────────────────────────────────────────────────────┐
│                        Web Browser                          │
│                    (前端 UI - HTML/CSS/JS)                   │
───────────────────────────┬─────────────────────────────────┘
                            │ HTTP / WebSocket
┌───────────────────────────▼─────────────────────────────────┐
│                     Memora Backend                          │
│                      (FastAPI / Python)                      │
├──────────────┬────────────────┬─────────────────────────────┤
│  Document    │   Retrieval    │      AI Services            │
│  Processing  │    Engine      │                             │
├──────────────┼────────────────┼─────────────────────────────┤
│ • PDF Parser │ • Dense Vector │ • Embedding (DashScope/     │
│ • DOCX Parse │   Search       │   Local ST)                 │
│ • Text Split │ • Sparse Vector│ • LLM Chat (DeepSeek/       │
│ • Metadata   │   (BM42)       │   OpenAI Compatible)        │
│ • Upload API │ • Hybrid Search│ • Rerank (Qwen3-Rerank)     │
│              │ • Fallback Logic│ • Stream Response          │
──────┬───────┴────────┬───────┴──────────────┬──────────────┘
       │                │                      │
┌──────▼──────┐  ┌──────▼──────┐       ┌──────▼──────┐
│   MySQL     │  │   Qdrant    │       │ External    │
│  (Metadata) │  │ (Vector DB) │       │ APIs        │
│             │  │             │       │             │
│ • Documents │  │ • Dense     │       │ • DashScope │
│ • Users     │  │   Vectors   │       │ • DeepSeek  │
│ • Sessions  │  │ • Sparse    │       │ • OpenAI    │
│ • History   │  │   (BM42)    │       │ Compatible  │
└─────────────┘  └─────────────┘       └─────────────┘
```

### 核心技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| **后端框架** | FastAPI (Python 3.11+) | 高性能异步 Web 框架 |
| **向量数据库** | Qdrant | 支持稠密+稀疏向量的混合检索 |
| **关系数据库** | MySQL 8.0 | 存储文档元数据、用户信息、会话历史 |
| **嵌入模型** | DashScope text-embedding-v4 / Sentence-Transformers | 支持云端 API 和本地模型 |
| **LLM 服务** | DeepSeek / OpenAI 兼容接口 | 支持流式输出和多轮对话 |
| **重排序模型** | Qwen3-Rerank (可选) | 提升检索结果的相关性 |
| **文档解析** | PyPDF2, docx2txt, LangChain | 多格式文档处理和文本分块 |
| **网页抓取** | httpx + BeautifulSoup | 内置爬虫，无外部依赖 |
| **容器化** | Docker + Docker Compose | 一键部署，环境隔离 |

##  快速安装

### 方式一：Docker Compose 部署（推荐）

#### 1. 克隆仓库

```bash
git clone https://github.com/zzlzzlzzl15/Memora.git
cd Memora/personal_knowledge_base
```

#### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置必要的参数：

```env
# LLM 配置（二选一）
DEEPSEEK_API_KEY=your_deepseek_api_key
# OPENAI_API_KEY=your_openai_api_key
# OPENAI_BASE_URL=https://api.deepseek.com/v1

# Embedding 配置（二选一）
EMBEDDING_MODEL=text-embedding-v4
DASHSCOPE_API_KEY=your_dashscope_api_key
# EMBEDDING_MODEL=openai/text-embedding-ada-002

# 可选：Rerank 配置
USE_RERANK=true
RERANK_API_KEY=your_qwen_rerank_api_key

# 数据库配置（默认即可）
MYSQL_ROOT_PASSWORD=root_password
MYSQL_DATABASE=memora_db
MYSQL_USER=memora_user
MYSQL_PASSWORD=memora_password

# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8080
DEBUG=false
```

#### 3. 启动服务

```bash
# 启动所有服务（Neo4j, Qdrant, MySQL, App）
docker-compose up -d

# 查看日志
docker-compose logs -f app

# 停止服务
docker-compose down
```

#### 4. 访问应用

打开浏览器访问：**http://localhost:8080**

### 方式二：本地开发环境

#### 1. 安装依赖

```bash
cd personal_knowledge_base
pip install -r requirements.txt
```

#### 2. 启动依赖服务

```bash
# 仅启动数据库服务（Qdrant, MySQL）
docker-compose -f docker-compose-dev.yml up -d
```

#### 3. 配置环境变量

同 Docker Compose 部署方式，创建并编辑 `.env` 文件。

#### 4. 启动应用

```bash
python app/main.py
```

访问：**http://localhost:8080**

### 方式三：通过 OpenClaw Skill 安装

如果您已安装 [OpenClaw](https://github.com/openclaw/openclaw)，可以通过 clawhub 一键安装：

```bash
# 等待 clawhub 发布后执行
openclaw skills install memora-knowledge-graph@2.0.3
```

或手动安装：

```bash
# 克隆仓库
git clone https://github.com/zzlzzlzzl15/Memora.git
cd Memora/personal_knowledge_base

# 运行安装脚本
./install.sh
```

##  使用指南

### 1. 上传文档

1. 点击左侧边栏的 **"上传文档"** 按钮
2. 选择文件（支持 PDF、DOCX、TXT、MD）
3. 填写标题和标签（可选）
4. 点击 **"上传"**，系统自动解析、分块、向量化

### 2. 智能问答

1. 在右侧聊天界面输入问题
2. 选择交互模式：
   - **知识查询**：获取基于检索结果的精准答案
   - **知识梳理**：让 AI 整理和总结相关知识
3. 查看答案和引用的源文档

### 3. 浏览知识图谱

1. 点击顶部导航栏的 **"知识图谱"** 按钮
2. 查看两个预览卡片：
   - **文档关系图谱**：显示文档之间的关联
   - **实体关系图谱**：显示提取的实体及其关系
3. 点击任意卡片进入全屏模态框，进行交互式探索：
   - 滚轮缩放
   - 拖拽平移
   - 拖拽节点
   - 悬停查看详情

### 4. 管理文档

- **查看列表**：左侧边栏查看所有文档
- **搜索文档**：使用快速搜索功能
- **回收站**：查看和管理已删除的文档（30天内可恢复）
- **彻底删除**：永久删除文档及其向量数据

## ️ 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 无 |
| `OPENAI_API_KEY` | OpenAI 兼容 API Key | 无 |
| `OPENAI_BASE_URL` | OpenAI 兼容 API Base URL | `https://api.openai.com/v1` |
| `EMBEDDING_MODEL` | 嵌入模型名称 | `text-embedding-v4` |
| `DASHSCOPE_API_KEY` | DashScope API Key | 无 |
| `USE_RERANK` | 是否启用 Rerank | `false` |
| `RERANK_API_KEY` | Rerank API Key | 无 |
| `RERANK_TOP_N` | Rerank 返回数量 | `5` |
| `RETRIEVAL_TOP_K` | 初始检索候选数 | `20` |
| `QDRANT_HOST` | Qdrant 地址 | `qdrant` |
| `QDRANT_PORT` | Qdrant 端口 | `6333` |
| `MYSQL_HOST` | MySQL 地址 | `mysql` |
| `MYSQL_PORT` | MySQL 端口 | `3306` |
| `MYSQL_DATABASE` | MySQL 数据库名 | `memora_db` |
| `MYSQL_USER` | MySQL 用户名 | `memora_user` |
| `MYSQL_PASSWORD` | MySQL 密码 | `memora_password` |

### 性能调优

#### 检索参数

```env
# 稠密向量相似度阈值（越高越严格）
QDRANT_DENSE_DEFAULT_THRESHOLD=0.7

# 稀疏向量相似度阈值
QDRANT_SPARSE_DEFAULT_THRESHOLD=0.0

# 初始检索候选数量（启用 Rerank 时）
RETRIEVAL_TOP_K=20

# 最终返回结果数量
QDRANT_DEFAULT_LIMIT=5
```

#### LLM 参数

```env
# LLM 温度（控制随机性，0-1）
LLM_TEMPERATURE=0.7

# 最大生成长度
LLM_MAX_TOKENS=2000

# 是否流式输出
LLM_STREAM=true
```

## ️ 故障排除

### 常见问题

#### 1. 服务无法启动

**症状**：`docker-compose up` 后某个容器持续重启

**解决方案**：
```bash
# 查看日志
docker-compose logs -f <service_name>

# 检查端口占用
lsof -i :8080

# 清理并重新启动
docker-compose down -v
docker-compose up -d
```

#### 2. 文档上传失败

**症状**：上传文档时提示错误

**可能原因**：
- 文件格式不支持
- 文件大小超过限制（默认 10MB）
- 解析器依赖缺失

**解决方案**：
```bash
# 检查应用日志
docker-compose logs -f app

# 确认支持的格式：PDF, DOCX, TXT, MD
# 减小文件大小或分批上传
```

#### 3. 检索结果为空

**症状**：查询后无结果返回

**可能原因**：
- 未上传任何文档
- 查询词与文档内容不相关
- 相似度阈值过高

**解决方案**：
- 确认已上传文档并成功向量化
- 尝试不同的查询词
- 降低 `QDRANT_DENSE_DEFAULT_THRESHOLD` 值

#### 4. LLM 调用失败

**症状**：问答时无响应或报错

**可能原因**：
- API Key 未配置或无效
- 网络连接问题
- API 配额耗尽

**解决方案**：
```bash
# 检查 .env 文件中的 API Key 配置
cat .env | grep API_KEY

# 测试 API 连通性
curl -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  https://api.deepseek.com/v1/chat/completions \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"test"}]}'

# 查看应用日志中的详细错误信息
docker-compose logs -f app | grep -i error
```

#### 5. 知识图谱不显示

**症状**：点击知识图谱按钮后无内容

**可能原因**：
- 浏览器缓存旧版本
- API 返回空数据

**解决方案**：
```bash
# 清除浏览器缓存或使用无痕模式
# 硬刷新页面：Cmd+Shift+R (Mac) / Ctrl+Shift+R (Windows)

# 检查浏览器控制台是否有错误
# 确认已上传文档且有足够的实体/关系数据
```

### 获取帮助

如果遇到问题，请：

1. 查看应用日志：`docker-compose logs -f app`
2. 检查 [GitHub Issues](https://github.com/zzlzzlzzl15/Memora/issues)
3. 提交新的 Issue，附上：
   - 问题描述
   - 复现步骤
   - 相关日志
   - 环境信息（操作系统、Docker 版本等）

## 📦 项目结构

```
Memora/
├── personal_knowledge_base/          # 主应用目录
│   ├── app/                          # 应用代码
│   │   ├── api/                      # API 路由
│   │   │   ├── documents.py          # 文档管理 API
│   │   │   ├── conversations.py      # 会话管理 API
│   │   │   ├── llm.py                # LLM 交互 API
│   │   │   ├── scrape.py             # 网页抓取 API
│   │   │   └── ...
│   │   ├── core/                     # 核心模块
│   │   │   ├── database.py           # 数据库连接
│   │   │   ├── resilience.py         # 韧性机制（重试、熔断）
│   │   │   ├── prompts.py            # Prompt 模板
│   │   │   └── ...
│   │   ├── models/                   # 数据模型
│   │   │   ├── document.py           # 文档模型
│   │   │   ├── conversation.py       # 会话模型
│   │   │   └── ...
│   │   ├── services/                 # 业务逻辑
│   │   │   ├── document_service.py   # 文档服务
│   │   │   ├── retrieval_service.py  # 检索服务
│   │   │   ├── embedding_service.py  # 向量化服务
│   │   │   └── ...
│   │   └── main.py                   # 应用入口
│   ├── config/                       # 配置管理
│   │   └── settings.py               # 环境变量加载
│   ├── static/                       # 前端静态文件
│   │   ├── index.html                # 主页面
│   │   ├── style.css                 # 样式文件
│   │   └── script.js                 # JavaScript（含知识图谱可视化）
│   ├── tests/                        # 测试代码
│   ├── openclaw-skill/               # OpenClaw Skill 定义
│   │   ├── SKILL.md                  # Skill 说明文档
│   │   └── scripts/
│   │       └── kb_api.py             # API 客户端脚本
│   ├── .env                          # 环境变量（需自行创建）
│   ├── .env.example                  # 环境变量示例
│   ├── requirements.txt              # Python 依赖
│   ├── docker-compose.yml            # Docker Compose 配置
│   ├── Dockerfile                    # Docker 镜像构建
│   ├── start.sh                      # 启动脚本
│   └── stop.sh                       # 停止脚本
── RAG-Anything/                     # RAG-Anything 参考实现
├── docs/                             # 文档目录
├── README.md                         # 本文档
└── LICENSE                           # MIT 许可证
```

## 🤝 贡献指南

欢迎贡献！请遵循以下步骤：

1. **Fork 本仓库**
2. **创建特性分支**：`git checkout -b feature/amazing-feature`
3. **提交更改**：`git commit -m 'Add amazing feature'`
4. **推送到分支**：`git push origin feature/amazing-feature`
5. **提交 Pull Request**

### 开发规范

- 遵循 PEP 8 Python 编码规范
- 添加必要的单元测试
- 更新相关文档
- 保持向后兼容性

##  许可证

本项目采用 [MIT License](LICENSE) 开源协议。

## 🙏 致谢

- [RAG-Anything](https://github.com/RAG-Anything/RAG-Anything) - 提供了多模态 RAG 架构的参考
- [Qdrant](https://qdrant.tech/) - 高性能向量数据库
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化 Web 框架
- [LangChain](https://www.langchain.com/) - LLM 应用开发框架
- [OpenClaw](https://github.com/openclaw/openclaw) - AI Agent 生态系统

## 📞 联系方式

- **GitHub**: [zzlzzlzzl15/Memora](https://github.com/zzlzzlzzl15/Memora)
- **Issues**: [提交问题](https://github.com/zzlzzlzzl15/Memora/issues)
- **Email**: support@memora.dev

---

**Made with ❤️ by zzlzzlzzl15**

*Memora - Your Personal AI Knowledge Base*
