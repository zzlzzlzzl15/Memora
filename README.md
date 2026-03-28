# Memora - Personal Knowledge Base with AI

> A self-hosted personal knowledge base powered by semantic vector search and AI-driven answers. Includes an [OpenClaw](https://github.com/anthropics/openclaw) Skill for seamless AI assistant integration.

[English](#features) | [中文说明](#-中文说明)

---

## Features

- **Semantic Search** - Find documents by meaning, not just keywords, using vector similarity (DashScope / OpenAI embeddings)
- **AI-Powered Q&A** - Ask questions and get AI-generated answers with source citations (DeepSeek / OpenAI LLM)
- **Document Management** - Upload files (PDF, DOCX, TXT, Markdown) or create text documents directly
- **OpenClaw Skill** - Zero-dependency Python client for AI assistant integration
- **Hybrid Retrieval** - Dense vectors + BM42 sparse vectors + Rerank for optimal search quality
- **Single-User Mode** - No login required, perfect for personal use
- **Web UI** - Clean three-panel interface: documents, AI chat, and studio

## Architecture

```
                    ┌──────────────────┐
                    │   Web Browser    │
                    │   (Frontend UI)  │
                    └────────┬─────────┘
                             │ HTTP
┌─────────────┐              │
│  OpenClaw   │──kb_api.py──▶│
│  AI Agent   │              │
└─────────────┘    ┌─────────▼──────────┐
                   │   Memora Backend   │
                   │   (FastAPI)        │
                   └──┬──────┬──────┬───┘
                      │      │      │
               ┌──────▼┐ ┌───▼───┐ ┌▼──────────┐
               │Qdrant │ │ MySQL │ │ DashScope  │
               │(Vector│ │(Meta- │ │ (Embedding)│
               │Search)│ │ data) │ │ DeepSeek   │
               └───────┘ └───────┘ │ (LLM Chat) │
                                   └────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for MySQL + Qdrant)
- API Keys:
  - **DashScope** (Alibaba Cloud) for text embedding, OR OpenAI API
  - **DeepSeek** for LLM chat, OR OpenAI API

### 1. Clone & Configure

```bash
git clone https://github.com/zzlzzlzzl15/Memora.git
cd Memora
cp .env.example .env
```

Edit `.env` with your API keys (see [API Key Setup Guide](#api-key-setup-guide) below).

### 2. Start Infrastructure

```bash
# Start MySQL and Qdrant using Docker
docker-compose -f docker-compose-dev.yml up -d
```

This starts:
- **MySQL 8.0** on port `3306` (metadata storage)
- **Qdrant** on ports `6333` (HTTP) and `6334` (gRPC) (vector database)

### 3. Install Dependencies & Run

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
./start.sh
# Or manually: python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### 4. Access Web UI

Open http://localhost:8080 in your browser. No login required in single-user mode.

---

## API Key Setup Guide

### DashScope (Alibaba Cloud) - for Text Embedding

DashScope provides the `text-embedding-v4` model used for document vectorization.

1. Register at [DashScope Console](https://dashscope.console.aliyun.com/)
2. Navigate to **API Keys** and create a new key
3. Set in `.env`:

```env
OPENAI_API_KEY="sk-your-dashscope-api-key"
EMBEDDING_API_BASE="https://dashscope.aliyuncs.com/compatible-mode/v1"
EMBEDDING_MODEL="openai/text-embedding-v4"
```

### DeepSeek - for LLM Chat

DeepSeek provides the chat model used for AI-powered Q&A.

1. Register at [DeepSeek Platform](https://platform.deepseek.com/)
2. Navigate to **API Keys** and create a new key
3. Set in `.env`:

```env
LLM_API_BASE="https://api.deepseek.com/v1"
LLM_API_KEY="sk-your-deepseek-api-key"
LLM_MODEL="deepseek-chat"
```

### Alternative: OpenAI

You can use OpenAI for both embedding and LLM:

```env
# Embedding
OPENAI_API_KEY="sk-your-openai-api-key"
EMBEDDING_API_BASE="https://api.openai.com/v1"
EMBEDDING_MODEL="text-embedding-3-small"
VECTOR_SIZE=1536

# LLM
LLM_API_BASE="https://api.openai.com/v1"
LLM_API_KEY="sk-your-openai-api-key"
LLM_MODEL="gpt-4o-mini"
```

---

## OpenClaw Integration

### What is OpenClaw?

[OpenClaw](https://github.com/anthropics/openclaw) is an open-source AI agent platform. It uses **Skills** (defined in `SKILL.md` files) to extend the AI assistant's capabilities with custom tools and workflows.

### Install OpenClaw

```bash
# macOS
brew install openclaw

# Or via npm
npm install -g openclaw
```

For detailed installation, see the [OpenClaw documentation](https://github.com/anthropics/openclaw).

### Install the Memora Skill

Copy the skill files to your OpenClaw workspace:

```bash
cp -r openclaw-skill ~/.openclaw/workspace/skills/personal-knowledge-base
```

### Configure the Skill

The skill connects to the Memora backend via HTTP. By default, it uses `http://127.0.0.1:8080`.

To use a custom endpoint, set the environment variable:

```bash
export KB_API_BASE="http://your-server:8080"
```

### Verify Installation

```bash
# Check skill is recognized
openclaw skills list

# Test the connection
python3 ~/.openclaw/workspace/skills/personal-knowledge-base/scripts/kb_api.py list
```

---

## Usage

The Memora Skill supports 6 commands. You can use them via the OpenClaw agent or directly from the command line.

### Search Documents

Find documents by semantic similarity:

```bash
python3 scripts/kb_api.py search "machine learning basics"
```

```json
{
  "total": 2,
  "results": [
    {
      "title": "ML Introduction",
      "content": "Machine learning is a subset of...",
      "score": 0.89,
      "document_id": "abc-123"
    }
  ]
}
```

### AI-Powered Q&A

Search and get an AI-generated answer with sources:

```bash
python3 scripts/kb_api.py search_answer "What are the best ski resorts near Munich?"
```

```json
{
  "query": "What are the best ski resorts near Munich?",
  "answer": "Based on your knowledge base, the top ski resorts near Munich include...",
  "total": 3,
  "sources": [
    {
      "title": "Munich Ski Guide",
      "score": 0.92
    }
  ]
}
```

### List All Documents

```bash
python3 scripts/kb_api.py list
```

```json
{
  "total": 5,
  "documents": [
    {
      "title": "Meeting Notes",
      "status": "indexed",
      "document_id": "abc-123",
      "created_at": "2026-03-28T10:00:00"
    }
  ]
}
```

### View Document Details

```bash
python3 scripts/kb_api.py detail "abc-123-document-id"
```

### Upload a File

Upload PDF, DOCX, TXT, or Markdown files:

```bash
python3 scripts/kb_api.py upload "/path/to/document.pdf" "My Document Title"
```

```json
{
  "status": "success",
  "document_id": "new-doc-id",
  "title": "My Document Title",
  "message": "Document 'My Document Title' uploaded successfully"
}
```

### Create a Text Document

Create a document directly from text:

```bash
python3 scripts/kb_api.py create "Meeting Notes" "Today we discussed the Q1 roadmap..."
```

---

## Configuration Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | DashScope or OpenAI API key (for embedding) | `sk-xxx` |
| `LLM_API_KEY` | DeepSeek or OpenAI API key (for LLM) | `sk-xxx` |
| `DATABASE_URL` | MySQL connection string | `mysql+pymysql://root:pass@127.0.0.1:3306/personal_knowledgebase` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `KB_API_BASE` | API endpoint (for OpenClaw Skill) | `http://127.0.0.1:8080` |
| `EMBEDDING_MODEL` | Embedding model name | `openai/text-embedding-v4` |
| `EMBEDDING_API_BASE` | Embedding API endpoint | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_API_BASE` | LLM API endpoint | `https://api.deepseek.com/v1` |
| `LLM_MODEL` | LLM model name | `deepseek-chat` |
| `QDRANT_HOST` | Qdrant server host | `localhost` |
| `QDRANT_PORT` | Qdrant gRPC port | `6334` |
| `VECTOR_SIZE` | Embedding vector dimensions | `1024` |
| `MAX_FILE_SIZE` | Max upload file size (bytes) | `10485760` (10MB) |
| `USE_RERANK` | Enable reranking | `true` |
| `RERANK_MODEL` | Rerank model name | `qwen3-rerank` |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/documents/upload` | Upload a file |
| `POST` | `/api/v1/documents/create` | Create a text document |
| `POST` | `/api/v1/documents/search` | Semantic search |
| `POST` | `/api/v1/documents/search/answer` | Search + AI answer |
| `POST` | `/api/v1/documents/search/answer/stream` | Search + streaming AI answer |
| `GET` | `/api/v1/documents/` | List all documents |
| `GET` | `/api/v1/documents/{id}` | Get document details |
| `PUT` | `/api/v1/documents/{id}` | Update a document |
| `DELETE` | `/api/v1/documents/{id}` | Delete a document (to recycle bin) |
| `POST` | `/api/v1/documents/{id}/restore` | Restore from recycle bin |

---

## Project Structure

```
Memora/
├── app/                        # FastAPI backend
│   ├── api/                    # API route handlers
│   ├── core/                   # Database, security, email
│   ├── models/                 # Pydantic & SQLAlchemy models
│   ├── services/               # Business logic
│   │   ├── embedding.py        # Vector embedding service
│   │   ├── vector_store.py     # Qdrant vector operations
│   │   ├── llm_service.py      # LLM integration
│   │   └── document_service.py # Document CRUD
│   ├── tasks/                  # Background tasks
│   └── main.py                 # Application entry point
├── config/
│   └── settings.py             # Configuration management
├── static/                     # Frontend (HTML/JS/CSS)
├── openclaw-skill/             # OpenClaw Skill
│   ├── SKILL.md                # Skill definition
│   └── scripts/
│       └── kb_api.py           # API client (zero dependencies)
├── .env.example                # Environment variable template
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker image build
├── docker-compose.yml          # Production deployment
├── docker-compose-dev.yml      # Development (MySQL + Qdrant)
├── start.sh                    # Start script
└── stop.sh                     # Stop script
```

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## 中文说明

### 项目简介

Memora 是一个自托管的个人知识库系统，基于语义向量搜索和 AI 驱动的智能问答。它包含一个 [OpenClaw](https://github.com/anthropics/openclaw) Skill，可以让 AI 助手直接管理和查询你的知识库。

### 核心功能

- **语义搜索** - 基于向量相似度的智能文档搜索（DashScope / OpenAI embedding）
- **AI 问答** - 提问即可获得 AI 整理的答案和来源引用（DeepSeek / OpenAI LLM）
- **文档管理** - 支持上传 PDF、DOCX、TXT、Markdown 文件，或直接创建文本文档
- **OpenClaw 集成** - 零依赖 Python 客户端，AI 助手可直接调用
- **单用户模式** - 无需登录，开箱即用

### 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/zzlzzlzzl15/Memora.git
cd Memora

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API 密钥（见下方说明）

# 3. 启动基础服务（MySQL + Qdrant）
docker-compose -f docker-compose-dev.yml up -d

# 4. 安装依赖并启动
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./start.sh

# 5. 打开浏览器访问 http://localhost:8080
```

### API 密钥申请

#### DashScope（阿里百炼）- 用于文本向量化

1. 访问 [阿里百炼控制台](https://dashscope.console.aliyun.com/) 注册账号
2. 进入 **API-KEY 管理**，创建新的 API Key
3. 在 `.env` 中设置：

```env
OPENAI_API_KEY="sk-你的DashScope密钥"
EMBEDDING_API_BASE="https://dashscope.aliyuncs.com/compatible-mode/v1"
EMBEDDING_MODEL="openai/text-embedding-v4"
```

#### DeepSeek - 用于 AI 问答

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/) 注册账号
2. 进入 **API Keys**，创建新的密钥
3. 在 `.env` 中设置：

```env
LLM_API_BASE="https://api.deepseek.com/v1"
LLM_API_KEY="sk-你的DeepSeek密钥"
LLM_MODEL="deepseek-chat"
```

### OpenClaw Skill 安装

#### 什么是 OpenClaw？

[OpenClaw](https://github.com/anthropics/openclaw) 是一个开源 AI Agent 平台。通过 Skill（技能）机制，可以让 AI 助手调用自定义工具和工作流。

#### 安装 OpenClaw

```bash
# macOS
brew install openclaw

# 或通过 npm
npm install -g openclaw
```

#### 安装 Memora Skill

```bash
# 将技能文件复制到 OpenClaw 工作空间
cp -r openclaw-skill ~/.openclaw/workspace/skills/personal-knowledge-base

# 验证安装
openclaw skills list
```

### 6 个命令速查

| 命令 | 说明 | 示例 |
|------|------|------|
| `search` | 语义搜索文档 | `python3 kb_api.py search "关键词"` |
| `search_answer` | 搜索并生成 AI 答案 | `python3 kb_api.py search_answer "你的问题"` |
| `list` | 列出所有文档 | `python3 kb_api.py list` |
| `detail` | 查看文档详情 | `python3 kb_api.py detail "文档ID"` |
| `upload` | 上传文件 | `python3 kb_api.py upload "/路径/文件.pdf" "标题"` |
| `create` | 创建文本文档 | `python3 kb_api.py create "标题" "内容"` |
