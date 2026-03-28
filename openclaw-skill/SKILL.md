---
name: personal-knowledge-base
description: >
  Personal Knowledge Base (Memora) — Semantic search, AI-powered Q&A, document management.
  Supports: search, AI answers with sources, list, detail, file upload (PDF/DOCX/TXT/MD), create text documents.
  个人知识库（Memora）— 语义搜索、AI 智能问答、文档管理。
  Use when: user asks about stored documents, wants to search/upload/create documents, or needs AI-organized answers from their knowledge base.
  NOT for: general chat, real-time news, tasks unrelated to the knowledge base.
metadata:
  openclaw:
    requires:
      env:
        - KB_API_BASE
---

# Personal Knowledge Base (Memora)

连接到个人知识库系统，支持语义搜索文档、获取 AI 整理答案、上传文件、创建文档。

## When to Run

- 用户提问涉及已存储的文档或知识内容
- 用户要求搜索知识库
- 用户要求列出文档或查看文档详情
- 用户想要上传文件或创建新文档到知识库
- 用户想要对某个主题进行知识整理

## Workflow

### 上传文件到知识库

1. 获取用户提供的文件路径和标题
2. 执行脚本:
   ```
   python scripts/kb_api.py upload "{文件绝对路径}" "{文档标题}"
   ```
3. 支持的文件类型: .txt .pdf .docx .md
4. 返回上传结果（包含 document_id）

### 创建纯文本文档

1. 获取用户提供的标题和文本内容
2. 执行脚本:
   ```
   python scripts/kb_api.py create "{文档标题}" "{文本内容}"
   ```
3. 返回创建结果（包含 document_id）

### 搜索知识库并获取 AI 整理答案

1. 提取用户的查询关键词
2. 执行脚本:
   ```
   python scripts/kb_api.py search_answer "{用户的查询内容}"
   ```
3. 解析返回的 JSON，提取 `answer` 字段和 `results` 中的来源信息
4. 以结构化方式呈现答案和来源

### 仅搜索文档（不生成答案）

1. 提取用户的搜索关键词
2. 执行脚本:
   ```
   python scripts/kb_api.py search "{搜索关键词}"
   ```
3. 解析返回的搜索结果列表

### 列出所有文档

1. 执行脚本:
   ```
   python scripts/kb_api.py list
   ```
2. 展示文档列表

### 查看文档详情

1. 获取文档 ID
2. 执行脚本:
   ```
   python scripts/kb_api.py detail "{document_id}"
   ```
3. 展示文档内容

## Output Format

### 上传/创建文档时:
✅ 文档 "{标题}" 已成功添加到知识库 (ID: {document_id})

### 搜索并整理答案时:
📚 **知识库查询结果**

{AI 整理的答案内容}

**参考来源:**
- 📄 {文档标题} (相关度: {score})

### 列出文档时:
📂 **文档列表** (共 {n} 篇)
1. 📄 {标题} - {创建时间}
2. ...

## Configuration

在使用前，需要设置环境变量 `KB_API_BASE` 指向知识库服务地址。
默认值: `http://127.0.0.1:8080`
