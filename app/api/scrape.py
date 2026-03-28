from typing import Any, Dict, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

from config.settings import settings
from app.core.security import get_current_user


class ScrapeOptions(BaseModel):
    formats: List[str] = ["markdown"]
    onlyMainContent: bool = True
    timeout: int = 30000
    skipTlsVerification: bool = True
    removeBase64Images: bool = True
    blockAds: bool = True
    proxy: str = "auto"
    storeInCache: bool = True
    zeroDataRetention: bool = False


class WebScrapeRequest(BaseModel):
    url: str
    title: Optional[str] = None
    options: Optional[ScrapeOptions] = None
    api_key: Optional[str] = None


router = APIRouter(prefix="/scrape", tags=["来源抓取"])


@router.post("/url")
async def scrape_url(req: WebScrapeRequest, user: Dict[str, Any] = Depends(get_current_user)):
    """使用 BeautifulSoup 抓取网页内容，并返回标准化结果。

    认证：复用现有 Bearer Token；仅用于鉴别当前用户。
    """
    if not req.url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少抓取地址 url")

    # 兼容原有选项：仅使用 timeout 与 onlyMainContent，其余忽略
    opts = req.options.model_dump() if req.options else ScrapeOptions().model_dump()
    timeout_sec = max(5, int(opts.get("timeout", 30000) / 1000))
    only_main = bool(opts.get("onlyMainContent", True))

    try:
        # 通过trust_env使用系统代理，提高在受限网络环境下的连通性
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_sec), trust_env=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }) as client:
            r = await client.get(req.url)
        if r.status_code >= 400:
            reason = r.reason_phrase or ""
            snippet = (r.text or "")[:200]
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"抓取失败 HTTP {r.status_code} {reason}: {snippet}")

        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        # 清理不必要的标签
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        # 提取标题
        title = (req.title or (soup.title.string.strip() if soup.title and soup.title.string else None)) or "网页来源"

        # 选择主要内容区域
        def pick_main() -> Any:
            candidates = []
            for name in ["article", "main"]:
                el = soup.find(name)
                if el: candidates.append(el)
            # 通过常见类名作为候选
            class_hints = ["content", "post", "article", "entry", "markdown", "prose", "page-content", "container"]
            for hint in class_hints:
                for el in soup.find_all(["div", "section"], class_=lambda c: c and hint in str(c)):
                    candidates.append(el)
            # 兜底 body
            candidates.append(soup.body or soup)
            # 选取文本最长的元素
            best = max(candidates, key=lambda el: len(el.get_text(separator="\n").strip()), default=soup)
            return best

        main_el = pick_main() if only_main else (soup.body or soup)

        # 简易 HTML -> Markdown 转换
        def to_md(el) -> str:
            lines = []
            def walk(node, depth=0):
                from bs4 import Tag, NavigableString
                if isinstance(node, NavigableString):
                    text = str(node)
                    if text.strip():
                        lines.append(text)
                    return
                if not isinstance(node, Tag):
                    return
                name = node.name.lower()
                if name in {"script", "style", "noscript"}:
                    return
                if name in {"h1","h2","h3","h4","h5","h6"}:
                    level = int(name[1])
                    lines.append("#"*level + " " + (node.get_text(strip=True) or ""))
                    lines.append("")
                elif name == "p":
                    lines.append(node.get_text(strip=False))
                    lines.append("")
                elif name == "br":
                    lines.append("")
                elif name in {"ul","ol"}:
                    ordered = (name == "ol")
                    idx = 1
                    for li in node.find_all("li", recursive=False):
                        content = li.get_text(strip=True)
                        prefix = (f"{idx}. " if ordered else "- ")
                        lines.append(prefix + content)
                        idx += 1
                    lines.append("")
                elif name in {"pre","code"}:
                    code_text = node.get_text(strip=False)
                    lines.append("```\n" + code_text + "\n```")
                    lines.append("")
                elif name == "blockquote":
                    q = node.get_text(strip=False).splitlines()
                    for l in q:
                        lines.append("> " + l)
                    lines.append("")
                elif name == "a":
                    href = node.get("href") or ""
                    text = node.get_text(strip=True)
                    lines.append(f"[{text}]({href})" if href else text)
                elif name == "img":
                    alt = node.get("alt") or ""
                    src = node.get("src") or ""
                    if src:
                        lines.append(f"![{alt}]({src})")
                else:
                    for child in node.children:
                        walk(child, depth+1)
            walk(el)
            md = "\n".join([l.rstrip() for l in lines])
            # 规范化空行
            return "\n".join([s for s in md.splitlines()])

        markdown = to_md(main_el).strip()
        if not markdown:
            # 兜底：纯文本
            markdown = (soup.get_text(separator="\n") or "").strip()
        if not markdown:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="抓取成功但未解析到有效内容")

        return {"url": req.url, "title": title, "markdown": markdown}
    except HTTPException:
        raise
    except httpx.RequestError as e:
        err_type = e.__class__.__name__
        err_msg = str(e).strip() or repr(e)
        if isinstance(e, httpx.TimeoutException):
            err_msg = f"请求超时（{err_type}），已等待 {timeout_sec}s 未连接成功"
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"error": err_msg})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"抓取接口异常: {e}")