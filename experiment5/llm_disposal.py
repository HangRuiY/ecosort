"""Direct LLM advice for descriptions the local material rules cannot answer."""
from __future__ import annotations

import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class GeneratedAdvice(BaseModel):
    relevant: bool = Field(description="是否为物品处置、垃圾分类或回收相关问题")
    item: str = Field(min_length=1, max_length=100, description="具体物品名称；信息不足时说明需补充")
    category: Literal["recyclable", "kitchen", "hazardous", "other", "special", "unknown"]
    reason: str = Field(min_length=1, max_length=800, description="分类或需要专项回收/补充信息的简短理由")
    answer: str = Field(min_length=1, max_length=3000, description="直接回答原始问题，说明可行的处理步骤及必要的注意事项")


SYSTEM = """你是循智 EcoSort 的物品处置与回收问答助手。用户的问题未被本地规则明确覆盖，
请直接理解原始问题并提供有帮助的建议，不要要求用户换成系统词表中的词。
必须按给定 schema 返回 JSON，不要输出 Markdown 代码围栏。
规则：
1. 回答垃圾分类、回收、废旧物品处理问题。无关问题礼貌引导回物品处置，不强行编造分类。
2. category 是建议的处理渠道，不是视觉检测模型类别。不确定时使用 unknown 并提出具体澄清问题。
3. 电子产品、复合物品、需要正规回收渠道的物品可用 special；不要因含塑料或金属就判为普通材质垃圾。
4. 废电脑、废手机等应给出正规电子产品回收/以旧换新等处理渠道，提醒保护个人数据；不要提供危险拆解操作。
5. 涉及电池、化学品或不明危险物时说明哪些信息还需确认，不根据模糊名称武断指定投放桶。
6. 使用所选地区的一般分类称谓；无法确认当地细则时明确说明以当地规则、回收点要求为准。
7. 不能声称查询过知识库、实时规定或官方文件，不能编造来源链接、统计概率或模型检测结果。
8. answer 用中文，通常3至6句话；reason 简短清晰。信息不足仍应给出有用的澄清问题。
"""


def generate_advice(llm, text: str, region: str) -> dict:
    structured = llm.with_structured_output(GeneratedAdvice, method="json_mode")
    value = structured.invoke([
        SystemMessage(content=SYSTEM + "\n必须输出下列 JSON Schema 的全部必填字段（包括 relevant 和 item）：\n" + json.dumps(GeneratedAdvice.model_json_schema(), ensure_ascii=False)),
        HumanMessage(content=json.dumps({"question": text, "region": "上海" if region == "shanghai" else "通用，具体城市未指定"}, ensure_ascii=False)),
    ])
    result = value if isinstance(value, GeneratedAdvice) else GeneratedAdvice.model_validate(value)
    labels = {
        "recyclable": "可回收物", "kitchen": "湿垃圾" if region == "shanghai" else "厨余垃圾",
        "hazardous": "有害垃圾", "other": "干垃圾" if region == "shanghai" else "其他垃圾",
        "special": "专项回收", "unknown": "需补充物品信息",
    }
    return {
        "text": text, "method": "llm-disposal", "source": "deepseek",
        "recognized": False, "disposal_recognized": result.relevant,
        "disposal_item": result.item, "top": None, "ranking": [], "matched_keywords": [],
        "contaminated": False, "evidence": [], "reply": result.answer,
        "advice": {
            "bin": result.category if result.category in {"recyclable", "kitchen", "hazardous", "other"} else None,
            "bin_zh": labels[result.category], "needs_review": True, "reason": result.reason,
        } if result.relevant else None,
    }
