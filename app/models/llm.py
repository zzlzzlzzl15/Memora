from pydantic import BaseModel, Field
from typing import Optional


class TextSummarizeRequest(BaseModel):
    """长文本整理请求模型"""
    text: str = Field(..., min_length=1, max_length=100000, description="待整理的长文本内容")
    title: Optional[str] = Field(None, description="可选标题，用于提示模型上下文")
    source_url: Optional[str] = Field(None, description="来源URL，可选")