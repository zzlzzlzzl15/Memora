"""
3.12 文档智能摘要服务

文档入库后，异步调用 LLM 生成结构化摘要：
  - summary: 核心内容概述（200字以内）
  - key_points: 关键要点列表
  - keywords: 关键词列表
  - entities: 主要实体列表（名称 + 类型）

摘要结果持久化到 DocumentORM.doc_metadata JSON 字段中，
以 "ai_summary" 键存储，不影响现有字段。

参照 RAG-Anything 的健壮 JSON 解析设计：四级降级解析策略。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from app.core.prompts import PROMPTS
from config.settings import settings


# ─────────────────────────────────────────────────────────────────────────────
# 健壮 JSON 解析（四级降级，参照 RAG-Anything 设计）
# ─────────────────────────────────────────────────────────────────────────────

def _robust_json_parse(text: str) -> Optional[Dict]:
    """四级降级 JSON 解析。"""
    if not text:
        return None

    # 级别 1：直接解析
    try:
        return json.loads(text)
    except Exception:
        pass

    # 级别 2：去除 Markdown 代码块
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 级别 3：提取第一个 {...} 块
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass

    # 级别 4：修复单引号 → 双引号后再试
    try:
        fixed = cleaned.replace("'", '"')
        return json.loads(fixed)
    except Exception:
        pass

    return None


# ─────────────────────────────────────────────────────────────────────────────
# DocumentSummaryService
# ─────────────────────────────────────────────────────────────────────────────

class DocumentSummaryService:
    """文档智能摘要服务。

    使用 LLM 对文档内容进行结构化摘要。摘要结果写入
    DocumentORM.doc_metadata["ai_summary"]。
    """

    # 摘要时截取的最大字符数（避免超出 LLM 上下文限制）
    CONTENT_MAX_LEN = 6000

    def __init__(self):
        self.api_base = settings.llm_api_base
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.api_base)

    def _clip(self, text: str) -> str:
        if len(text) > self.CONTENT_MAX_LEN:
            return text[: self.CONTENT_MAX_LEN] + "..."
        return text

    async def _call_llm(self, messages: List[Dict]) -> str:
        """调用 LLM，返回原始文本。"""
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(
            base_url=self.api_base, timeout=timeout, headers=headers
        ) as client:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 1024,
                "stream": False,
            }
            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    def _build_fallback_summary(
        self, title: str, content: str
    ) -> Dict[str, Any]:
        """LLM 不可用时的本地回退摘要。"""
        # 取前 200 字作为摘要
        raw = (content or "").strip()
        summary = raw[:200] + ("..." if len(raw) > 200 else "")

        # 简单分句取前三句作为要点
        sentences = re.split(r"[。！？.!?]", raw)
        key_points = [s.strip() for s in sentences if len(s.strip()) > 10][:3]

        # 用文档标题拆分关键词（中文空格分词简易版）
        keywords = list({w for w in re.findall(r"[\u4e00-\u9fa5]{2,6}", title) if w})[:5]

        return {
            "summary": summary,
            "key_points": key_points,
            "keywords": keywords,
            "entities": [],
            "generated_by": "local_fallback",
        }

    async def generate_summary(
        self, document_id: str, title: str, content: str
    ) -> Dict[str, Any]:
        """生成文档摘要，返回结构化字典。

        返回格式：
        {
            "summary": str,
            "key_points": List[str],
            "keywords": List[str],
            "entities": List[{"name": str, "type": str}],
            "generated_by": "llm" | "local_fallback"
        }
        """
        if not content or not content.strip():
            logger.info(f"[summary] doc={document_id} 内容为空，跳过摘要生成")
            return self._build_fallback_summary(title, "")

        if not self.available:
            logger.info(f"[summary] LLM 不可用，使用本地摘要 doc={document_id}")
            return self._build_fallback_summary(title, content)

        try:
            messages = [
                {"role": "system", "content": PROMPTS["DOC_SUMMARY_SYSTEM"]},
                {
                    "role": "user",
                    "content": PROMPTS["DOC_SUMMARY_USER"].format(
                        title=title, content=self._clip(content)
                    ),
                },
            ]
            raw = await self._call_llm(messages)
            parsed = _robust_json_parse(raw)
            if not parsed:
                raise ValueError(f"JSON 解析失败，原始输出: {raw[:200]}")

            result = {
                "summary": parsed.get("summary", ""),
                "key_points": parsed.get("key_points", []),
                "keywords": parsed.get("keywords", []),
                "entities": parsed.get("entities", []),
                "generated_by": "llm",
            }
            logger.info(
                f"[summary] doc={document_id} "
                f"summary_len={len(result['summary'])} "
                f"keywords={result['keywords'][:3]}"
            )
            return result

        except Exception as e:
            logger.error(f"[summary] LLM 摘要失败 doc={document_id}: {e}")
            return self._build_fallback_summary(title, content)

    async def save_summary_to_db(
        self, document_id: str, summary: Dict[str, Any]
    ) -> bool:
        """将摘要写入 DocumentORM.doc_metadata["ai_summary"]。"""
        try:
            from app.core.sql import get_db
            from app.models.db_models import DocumentORM

            db = next(get_db())
            doc_orm = db.query(DocumentORM).filter(
                DocumentORM.doc_id == document_id
            ).first()
            if not doc_orm:
                logger.warning(f"[summary] 未找到文档 doc={document_id}")
                return False

            existing_meta = {}
            if doc_orm.doc_metadata:
                try:
                    existing_meta = json.loads(doc_orm.doc_metadata)
                except Exception:
                    pass

            existing_meta["ai_summary"] = summary
            doc_orm.doc_metadata = json.dumps(existing_meta, ensure_ascii=False)
            db.commit()
            logger.info(f"[summary] 摘要已写入 DB doc={document_id}")
            return True
        except Exception as e:
            logger.error(f"[summary] 写入 DB 失败 doc={document_id}: {e}")
            return False

    async def summarize_and_save(
        self, document_id: str, title: str, content: str
    ) -> Dict[str, Any]:
        """生成并保存摘要（一站式调用）。"""
        summary = await self.generate_summary(document_id, title, content)
        await self.save_summary_to_db(document_id, summary)
        return summary


# ─────────────────────────────────────────────────────────────────────────────
# 全局单例
# ─────────────────────────────────────────────────────────────────────────────
_summary_service: Optional[DocumentSummaryService] = None


def get_summary_service() -> DocumentSummaryService:
    global _summary_service
    if _summary_service is None:
        _summary_service = DocumentSummaryService()
    return _summary_service
