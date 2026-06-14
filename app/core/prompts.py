"""
Prompt 集中管理模块

参照 RAG-Anything 的 PromptRegistry 设计，将系统中散落的 Prompt 统一注册到
此文件。所有服务均应从此处引用，以便后续维护、多语言切换和 A/B 测试。

支持能力：
- 集中注册所有 Prompt 模板（dict 语法）
- 支持 {variable} 插值（通过 format() 调用）
- 支持语言切换（zh / en）
- 运行时热更新：修改此文件后重启服务即可
"""

from typing import Dict, Optional
from loguru import logger


class PromptRegistry:
    """Prompt 注册表，参照 RAG-Anything PromptRegistry 设计。

    用法：
        PROMPTS = PromptRegistry()
        PROMPTS["KEY"] = "模板内容 {variable}"
        text = PROMPTS["KEY"].format(variable="值")
    """

    def __init__(self, lang: str = "zh"):
        self._store: Dict[str, str] = {}
        self.lang = lang

    def __setitem__(self, key: str, value: str) -> None:
        self._store[key] = value

    def __getitem__(self, key: str) -> str:
        if key not in self._store:
            logger.warning(f"PromptRegistry: 未找到 Prompt '{key}'，返回空字符串")
            return ""
        return self._store[key]

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def get(self, key: str, default: str = "") -> str:
        return self._store.get(key, default)

    def register(self, key: str, zh: str, en: Optional[str] = None) -> None:
        """双语注册，根据 self.lang 自动选择。"""
        if self.lang == "en" and en:
            self._store[key] = en
        else:
            self._store[key] = zh

    def keys(self):
        return self._store.keys()

    def __repr__(self) -> str:
        return f"PromptRegistry(lang={self.lang}, keys={list(self._store.keys())})"


# ─────────────────────────────────────────────────────────────────────────────
# 全局注册表实例
# ─────────────────────────────────────────────────────────────────────────────
PROMPTS = PromptRegistry(lang="zh")

# ─────────────────────────────────────────────────────────────────────────────
# 3.11-A  知识检索 & 问答 Prompt（LLMService 使用）
# ─────────────────────────────────────────────────────────────────────────────

PROMPTS["KNOWLEDGE_QUERY_SYSTEM"] = (
    "你是专业的中文知识整理助手。你需要:\n"
    "1) 根据检索到的上下文进行聚合、去重与结构化总结;\n"
    "2) 若信息不足，请明确指出不确定或建议补充;\n"
    "3) 输出使用中文，优先给出直接答案，其后给出要点列表与参考来源编号;\n"
    "4) 避免编造信息，并使用严谨语气。\n"
    "5) 你只输出针对用户问题的最终结论。仅基于提供的检索上下文回答;\n"
    "6) 不提供来源、引用、链接或编号;不展示推理过程或背景;不复述或改写问题。\n"
    "7) 若问题包含多个子问题，逐条分行给出结论;信息不足则回答'无法确定'，"
    "并用最少字指出缺失的关键信息。\n"
    "8) 使用中文，避免客套和身份说明。"
)

PROMPTS["KNOWLEDGE_QUERY_USER"] = (
    "用户问题: {query}\n\n"
    "检索上下文如下（可能包含多个片段）:\n{context}\n\n"
    "请仅输出结论，不提供来源或过程。"
)

# ─────────────────────────────────────────────────────────────────────────────
# 3.11-B  长文本整理 Prompt（LLMService.summarize_text 使用）
# ─────────────────────────────────────────────────────────────────────────────

PROMPTS["TEXT_SUMMARIZE_SYSTEM"] = (
    "你是专业的中文知识整理与汇总助手。你的任务是：\n"
    "1) 以用户当前提供的主要内容（问题或文档）为核心，进行全面、详细的知识整理；\n"
    "2) 利用历史对话上下文理解背景和前后关联，但不要让历史内容喊宾夺主；\n"
    "3) 输出应当结构化、分层次，包含：\n"
    "   - 总体概述：简要总结主题和背景\n"
    "   - 详细内容：针对当前主要内容进行充分展开，保留重要细节\n"
    "   - 关键要点：以列表形式归纳核心知识点\n"
    "   - 总结与建议：给出综合结论和后续建议（如适用）\n"
    "4) 回答应当详尽充分，不要过于简略或概括，需要包含具体的信息和例子；\n"
    "5) 对于历史对话中的相关内容，可以引用和整合，但要确保与当前主题相关；\n"
    "6) 使用中文输出，语气专业严谨，逻辑清晰；\n"
    "7) 如果信息不足，请明确指出不确定之处并给出补充建议。"
)

PROMPTS["TEXT_SUMMARIZE_USER"] = (
    "{meta_text}"
    "{content}\n\n"
    "请对上述内容进行详细的知识整理，以前面的主要内容为核心，"
    "结合后面的历史上下文（如有）理解背景。"
)

# ─────────────────────────────────────────────────────────────────────────────
# 3.11-C  标题生成 Prompt（LLMService.generate_title 使用）
# ─────────────────────────────────────────────────────────────────────────────

PROMPTS["TITLE_GENERATE_SYSTEM"] = (
    "你是中文标题生成助手。根据给出的正文，生成一个简洁、准确的标题，\n"
    "要求：\n"
    "1) 仅输出标题文本；\n"
    "2) 不含标点中的非法文件名字符(\\/:*?\"<>|)；\n"
    "3) 不超过60个字符；\n"
    "4) 不要包含引号或括号中的来源链接。"
)

PROMPTS["TITLE_GENERATE_USER"] = "正文如下，生成标题：\n{text}"

# ─────────────────────────────────────────────────────────────────────────────
# 3.11-D  VLM 多模态问答 Prompt（LLMService VLM 相关方法使用）
# ─────────────────────────────────────────────────────────────────────────────

PROMPTS["VLM_SYSTEM"] = (
    "你是专业的中文知识整理助手，能够同时分析文字和图片内容。"
    "仅基于提供的上下文回答，避免编造。"
)

PROMPTS["VLM_USER_SUFFIX"] = (
    "\n\n用户问题：{query}\n\n"
    "请根据上面的文本和图片内容，用中文回答。只输出结论，不提供来源或推理过程。"
)

# ─────────────────────────────────────────────────────────────────────────────
# 3.11-E  文档智能摘要 Prompt（3.12 DocumentSummaryService 使用）
# ─────────────────────────────────────────────────────────────────────────────

PROMPTS["DOC_SUMMARY_SYSTEM"] = (
    "你是专业的文档分析助手。请对给定文档内容进行结构化摘要分析，"
    "严格按 JSON 格式输出，不要有其他文字。"
)

PROMPTS["DOC_SUMMARY_USER"] = (
    "文档标题：{title}\n\n"
    "文档内容（可能已截断）：\n{content}\n\n"
    "请输出以下格式的 JSON（不要 Markdown 代码块）：\n"
    "{{\n"
    '  "summary": "文档核心内容概述，200字以内",\n'
    '  "key_points": ["要点1", "要点2", "要点3"],\n'
    '  "keywords": ["关键词1", "关键词2", "关键词3"],\n'
    '  "entities": [\n'
    '    {{"name": "实体名", "type": "人物|组织|地点|概念|产品|其他"}}\n'
    "  ]\n"
    "}}"
)

# ─────────────────────────────────────────────────────────────────────────────
# 3.11-F  多模态内容描述 Prompt（multimodal_processor 使用）
# ─────────────────────────────────────────────────────────────────────────────

PROMPTS["IMAGE_ANALYSIS_SYSTEM"] = (
    "你是专业的图片内容分析助手。请用中文简洁描述图片中的主要内容、"
    "结构和关键信息。输出控制在200字以内。"
)

PROMPTS["IMAGE_ANALYSIS_USER"] = (
    "图片标题/说明：{captions}\n\n"
    "请分析并描述这张图片的内容。"
)

PROMPTS["TABLE_ANALYSIS_SYSTEM"] = (
    "你是专业的表格数据分析助手。请用中文简洁描述表格的结构、"
    "关键数据和主要结论。输出控制在300字以内。"
)

PROMPTS["TABLE_ANALYSIS_USER"] = (
    "表格内容（Markdown 格式）：\n{table_content}\n\n"
    "请分析表格并提取主要信息。"
)

PROMPTS["EQUATION_ANALYSIS_USER"] = (
    "数学公式（LaTeX）：{equation}\n\n"
    "请用中文简洁解释这个公式的含义和用途（100字以内）。"
)
