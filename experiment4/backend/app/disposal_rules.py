"""Text-only disposal guidance for items outside the five visual classes."""
from __future__ import annotations

from .advice import BINS

SOURCE_URL = "https://lhsr.sh.gov.cn/srgl/20240806/40b9feaa-53db-472f-8a6b-2c3cf0465def.html"
SOURCE_TITLE = "上海市生活垃圾分类投放指引（2024版）"


def disposal_rule(text: str, region: str) -> dict | None:
    """Do not invent a visual class or a material probability for these items."""
    region = region if region in ("general", "shanghai") else "general"
    cigarette_words = ("烟头", "烟蒂", "烟屁股", "香烟头", "香烟过滤嘴", "香烟滤嘴", "cigarette butt", "cigarette stub")
    battery_words = ("电池", "蓄电池")
    low = text.lower()
    keywords = [word for word in cigarette_words if word in low]
    if keywords and any(word in low for word in battery_words):
        name, bin_key, review = "烟蒂和废电池", None, True
        reason = "描述包含多种物品，请分别查询和投放：烟蒂熄灭后投其他垃圾，废电池需先确认类型，不能将两者按同一类处理。"
        source_text = "指引分别列出烟蒂和特定废电池，混合物品需要分别投放。"
    elif keywords:
        name, bin_key, review = "烟蒂", "other", False
        reason = "烟头、烟蒂按其他垃圾处理（上海称干垃圾），完全熄灭后再投放。"
        source_text = "指引将烟蒂列入干垃圾。请遵循所在地分类名称和投放要求。"
    elif any(word in low for word in battery_words):
        keywords = [word for word in battery_words if word in low]
        name, bin_key, review = "废电池", None, True
        reason = "请先确认电池类型：镍镉电池、氧化汞电池按有害垃圾处理；其他电池请按当地分类或专项回收要求处理。可补充电池标签或类型，不能仅凭‘废电池’确定投放桶。"
        source_text = "指引明确列出废镍镉电池、废氧化汞电池等有害垃圾；仅凭‘废电池’无法确认具体类型。"
        if any(word in low for word in ("镍镉", "镉镍", "氧化汞")):
            name, bin_key, review = "废镍镉/氧化汞电池", "hazardous", False
            reason = "镍镉电池、氧化汞电池按有害垃圾单独投放，注意保持完整，具体收集方式以当地要求为准。"
    else:
        return None
    return {
        "item": name,
        "keywords": keywords,
        "advice": {
            "bin": bin_key,
            "bin_zh": BINS[bin_key][region] if bin_key else ("请分开确认物品" if name == "烟蒂和废电池" else "需确认电池类型"),
            "needs_review": review,
            "reason": reason,
        },
        "source": {"title": SOURCE_TITLE, "source_url": SOURCE_URL, "text": source_text},
    }
