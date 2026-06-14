"""
3.14 增强文档导出服务

支持三种格式导出文档内容：
- markdown: 带元数据 frontmatter 的 Markdown 文件
- html: 完整的 HTML 文档（Markdown 渲染为 HTML，含样式）
- json: 完整 JSON 对象（含文档信息、摘要、内容）

设计原则：
- 轻量无外部依赖（markdown→html 使用内置正则简单渲染，有 markdown 包时优先使用）
- 所有格式均在内存中生成，返回 bytes 供 StreamingResponse 使用
- 文件名自动 sanitize（去除非法字符）
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, Optional
from loguru import logger


# ─────────────────────────────────────────────────────────────────────────────
# 文件名 sanitize
# ─────────────────────────────────────────────────────────────────────────────

def _safe_filename(title: str, ext: str) -> str:
    """将标题转换为安全的文件名。"""
    name = re.sub(r'[\\/:*?"<>|]', "_", title or "document")
    name = name.strip(". ").strip()
    if not name:
        name = "document"
    # 限制长度
    if len(name) > 80:
        name = name[:80].rstrip()
    return f"{name}.{ext}"


# ─────────────────────────────────────────────────────────────────────────────
# Markdown → HTML 简易转换（可选依赖 markdown 包）
# ─────────────────────────────────────────────────────────────────────────────

def _md_to_html(md_text: str) -> str:
    """Markdown 转 HTML。优先使用 markdown 包，否则回退到简易实现。"""
    try:
        import markdown as md_lib  # type: ignore
        return md_lib.markdown(
            md_text,
            extensions=["tables", "fenced_code", "nl2br"],
        )
    except ImportError:
        pass

    # ── 简易正则转换（无外部依赖）──────────────────────────────────────────
    html = md_text

    # 代码块（带语言标注）
    html = re.sub(
        r"```(\w+)?\n(.*?)```",
        lambda m: f"<pre><code class=\"language-{m.group(1) or ''}\">{m.group(2)}</code></pre>",
        html,
        flags=re.DOTALL,
    )
    # 行内代码
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    # 标题 h1-h6
    for i in range(6, 0, -1):
        html = re.sub(
            r"^#{" + str(i) + r"}\s+(.+)$", rf"<h{i}>\1</h{i}>", html, flags=re.MULTILINE
        )
    # 粗体 / 斜体
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    # 链接
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)
    # 有序 / 无序列表（简单处理，每行一项）
    html = re.sub(r"^\s*[-*]\s+(.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"^\s*\d+\.\s+(.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    # 换行 → <p>
    paragraphs = html.split("\n\n")
    processed = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if para.startswith("<h") or para.startswith("<pre") or para.startswith("<li"):
            processed.append(para)
        else:
            processed.append(f"<p>{para.replace(chr(10), '<br>')}</p>")
    return "\n".join(processed)


# ─────────────────────────────────────────────────────────────────────────────
# HTML 页面模板
# ─────────────────────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
         max-width: 860px; margin: 40px auto; padding: 0 24px; color: #1a1a1a; line-height: 1.8; }}
  h1, h2, h3, h4 {{ color: #111; margin-top: 1.5em; }}
  h1 {{ font-size: 2em; border-bottom: 2px solid #eee; padding-bottom: 0.3em; }}
  h2 {{ font-size: 1.5em; border-bottom: 1px solid #eee; padding-bottom: 0.2em; }}
  pre {{ background: #f6f8fa; border-radius: 6px; padding: 16px; overflow-x: auto; }}
  code {{ background: #f6f8fa; border-radius: 3px; padding: 2px 5px; font-size: 0.9em; }}
  pre code {{ background: none; padding: 0; }}
  a {{ color: #0366d6; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  blockquote {{ border-left: 4px solid #dfe2e5; color: #6a737d; margin: 0; padding: 0 16px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #dfe2e5; padding: 8px 12px; }}
  th {{ background: #f6f8fa; }}
  .meta-info {{ background: #f9f9f9; border: 1px solid #eee; border-radius: 8px;
               padding: 16px; margin-bottom: 32px; font-size: 0.9em; color: #555; }}
  .meta-info p {{ margin: 4px 0; }}
  .tag {{ display: inline-block; background: #e8f4fd; color: #0366d6;
          border-radius: 4px; padding: 2px 8px; font-size: 0.8em; margin: 2px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta-info">
  {meta_html}
</div>
{content_html}
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# DocumentExportService
# ─────────────────────────────────────────────────────────────────────────────

class DocumentExportService:
    """文档导出服务。

    支持格式：
    - markdown (.md): YAML frontmatter + 原始 Markdown 内容
    - html (.html): 完整带样式 HTML 页面
    - json (.json): 文档完整 JSON 对象

    所有方法返回 (bytes, filename, media_type) 三元组。
    """

    # ── 公共入口 ────────────────────────────────────────────────────────────

    def export(
        self,
        document: Any,  # app.models.document.Document
        fmt: str = "markdown",
        include_summary: bool = True,
    ) -> tuple[bytes, str, str]:
        """导出文档。

        Args:
            document: Document Pydantic 对象
            fmt: 导出格式，"markdown" | "html" | "json"
            include_summary: 是否在导出内容中包含 ai_summary（若有）

        Returns:
            (content_bytes, filename, media_type)
        """
        fmt = fmt.lower().strip()
        if fmt == "markdown":
            return self._export_markdown(document, include_summary)
        elif fmt == "html":
            return self._export_html(document, include_summary)
        elif fmt == "json":
            return self._export_json(document, include_summary)
        else:
            raise ValueError(f"不支持的导出格式: {fmt}，可选: markdown / html / json")

    # ── Markdown 导出 ────────────────────────────────────────────────────────

    def _export_markdown(self, document: Any, include_summary: bool) -> tuple[bytes, str, str]:
        title = document.title or "未命名文档"
        metadata = document.metadata or {}
        tags = document.tags or []
        ai_summary = metadata.get("ai_summary") if include_summary else None

        lines: list[str] = ["---"]
        lines.append(f"title: \"{title}\"")
        lines.append(f"file_type: {document.file_type}")
        if tags:
            lines.append(f"tags: [{', '.join(tags)}]")
        created_at = document.created_at
        if created_at:
            lines.append(f"created_at: {created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at)}")
        updated_at = document.updated_at
        if updated_at:
            lines.append(f"updated_at: {updated_at.isoformat() if hasattr(updated_at, 'isoformat') else str(updated_at)}")
        lines.append("---")
        lines.append("")

        # AI 摘要区块
        if ai_summary:
            lines.append("## AI 智能摘要")
            lines.append("")
            if ai_summary.get("summary"):
                lines.append(ai_summary["summary"])
                lines.append("")
            kps = ai_summary.get("key_points", [])
            if kps:
                lines.append("**关键要点：**")
                for kp in kps:
                    lines.append(f"- {kp}")
                lines.append("")
            kws = ai_summary.get("keywords", [])
            if kws:
                lines.append(f"**关键词：** {', '.join(kws)}")
                lines.append("")
            lines.append("---")
            lines.append("")

        # 正文
        lines.append("## 正文")
        lines.append("")
        lines.append(document.content or "")

        md_text = "\n".join(lines)
        filename = _safe_filename(title, "md")
        return md_text.encode("utf-8"), filename, "text/markdown; charset=utf-8"

    # ── HTML 导出 ────────────────────────────────────────────────────────────

    def _export_html(self, document: Any, include_summary: bool) -> tuple[bytes, str, str]:
        title = document.title or "未命名文档"
        metadata = document.metadata or {}
        tags = document.tags or []
        ai_summary = metadata.get("ai_summary") if include_summary else None

        # 构建元数据区块 HTML
        meta_parts: list[str] = []
        created_at = document.created_at
        if created_at:
            ts = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
            meta_parts.append(f"<p>📅 <strong>创建时间：</strong>{ts}</p>")
        file_type = document.file_type
        if file_type:
            meta_parts.append(f"<p>📄 <strong>文档类型：</strong>{file_type}</p>")
        if tags:
            tag_html = " ".join(f'<span class="tag">{t}</span>' for t in tags)
            meta_parts.append(f"<p>🏷 <strong>标签：</strong>{tag_html}</p>")
        meta_html = "\n  ".join(meta_parts) if meta_parts else ""

        # 内容区块
        content_parts: list[str] = []

        if ai_summary:
            content_parts.append("<section>")
            content_parts.append("<h2>AI 智能摘要</h2>")
            if ai_summary.get("summary"):
                content_parts.append(f"<p>{ai_summary['summary']}</p>")
            kps = ai_summary.get("key_points", [])
            if kps:
                content_parts.append("<p><strong>关键要点：</strong></p>")
                content_parts.append("<ul>")
                for kp in kps:
                    content_parts.append(f"  <li>{kp}</li>")
                content_parts.append("</ul>")
            kws = ai_summary.get("keywords", [])
            if kws:
                kw_html = " ".join(f'<span class="tag">{k}</span>' for k in kws)
                content_parts.append(f"<p><strong>关键词：</strong>{kw_html}</p>")
            content_parts.append("</section>")
            content_parts.append("<hr>")

        # 正文渲染
        raw_content = document.content or ""
        content_html_body = _md_to_html(raw_content)
        content_parts.append(f"<section>\n<h2>正文</h2>\n{content_html_body}\n</section>")

        content_html = "\n".join(content_parts)
        html = _HTML_TEMPLATE.format(
            title=title,
            meta_html=meta_html,
            content_html=content_html,
        )
        filename = _safe_filename(title, "html")
        return html.encode("utf-8"), filename, "text/html; charset=utf-8"

    # ── JSON 导出 ────────────────────────────────────────────────────────────

    def _export_json(self, document: Any, include_summary: bool) -> tuple[bytes, str, str]:
        title = document.title or "未命名文档"
        metadata = document.metadata or {}

        data: Dict[str, Any] = {
            "document_id": document.document_id,
            "title": title,
            "file_type": document.file_type,
            "tags": document.tags or [],
            "status": document.status,
            "file_size": document.file_size,
            "created_at": (
                document.created_at.isoformat()
                if document.created_at and hasattr(document.created_at, "isoformat")
                else str(document.created_at)
            ),
            "updated_at": (
                document.updated_at.isoformat()
                if document.updated_at and hasattr(document.updated_at, "isoformat")
                else str(document.updated_at)
            ),
            "content": document.content or "",
        }

        if include_summary:
            ai_summary = metadata.get("ai_summary")
            if ai_summary:
                data["ai_summary"] = ai_summary

        # 排除 ai_summary 之外的 metadata 字段（避免冗余）
        extra_meta = {k: v for k, v in metadata.items() if k != "ai_summary"}
        if extra_meta:
            data["metadata"] = extra_meta

        json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        filename = _safe_filename(title, "json")
        return json_bytes, filename, "application/json; charset=utf-8"


# ─────────────────────────────────────────────────────────────────────────────
# 全局单例
# ─────────────────────────────────────────────────────────────────────────────

_export_service: Optional[DocumentExportService] = None


def get_export_service() -> DocumentExportService:
    global _export_service
    if _export_service is None:
        _export_service = DocumentExportService()
    return _export_service
