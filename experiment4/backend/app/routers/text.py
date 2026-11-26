from __future__ import annotations

from fastapi import APIRouter, Depends

from ..config import MAX_TEXT_LEN
from ..deps import require_key
from ..errors import InputError, ok
from ..schemas import ApiResponse, TextQuery
from ..text_service import answer
from ..llm_fallback import with_llm_fallback

router = APIRouter(tags=["文本问答"])


def clean_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        raise InputError("文本为空，请描述要投放的物品，例如“喝完的易拉罐”")
    if len(text) > MAX_TEXT_LEN:
        raise InputError(f"文本长度 {len(text)} 字，超过 {MAX_TEXT_LEN} 字上限")
    return text


@router.post("/text", response_model=ApiResponse, summary="物品描述 → 材质类别与投放建议",
             description="application/json：{\"text\": \"...\", \"region\": \"general\"}。")
def text_query(body: TextQuery, _=Depends(require_key)):
    text = clean_text(body.text)
    region = body.region if body.region in ("general", "shanghai") else "general"
    result = with_llm_fallback(answer(text, region), text, region)
    msg = "ok" if result["recognized"] or result.get("disposal_recognized") or result.get("reply") else result.get("fallback_message", "请补充要处理的物品描述")
    return ok(result, msg)
