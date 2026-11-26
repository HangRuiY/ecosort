"""Ask the Agent service directly when no local material/disposal rule applies."""
from __future__ import annotations

import logging

import httpx

log = logging.getLogger("ecosort")
URL = "http://127.0.0.1:8001/api/v1/agent/answer"


def _request_answer(text: str, region: str) -> dict:
    with httpx.Client(timeout=40, trust_env=False) as client:
        response = client.post(URL, json={"text": text, "region": region})
        response.raise_for_status()
        return response.json()


def with_llm_fallback(local: dict, text: str, region: str) -> dict:
    if local.get("recognized") or local.get("disposal_recognized"):
        return local
    try:
        body = _request_answer(text, region)
        result = body.get("result")
        if body.get("code") != 200 or not isinstance(result, dict):
            raise ValueError("Agent answer failed")
        if result.get("source") != "deepseek" or not isinstance(result.get("reply"), str) or not result["reply"].strip():
            raise ValueError("Agent answer is incomplete")
        required = {"recognized", "top", "ranking", "matched_keywords", "evidence", "advice", "disposal_item"}
        if not required.issubset(result) or result["recognized"] is not False or result["top"] is not None:
            raise ValueError("Agent answer has an invalid format")
        if any(not isinstance(result[key], list) for key in ("ranking", "matched_keywords", "evidence")):
            raise ValueError("Agent answer has invalid lists")
        advice = result["advice"]
        if advice is not None and (not isinstance(advice, dict) or not {"bin", "bin_zh", "needs_review", "reason"}.issubset(advice)):
            raise ValueError("Agent advice is incomplete")
        return {**result, "text": text, "fallback_status": "answered"}
    except Exception as exc:
        log.warning("直接 AI 问答不可用：%s", type(exc).__name__)
        return {**local, "fallback_status": "unavailable", "fallback_message": "本地规则暂未覆盖这个物品，AI 问答服务暂时不可用，请稍后重试。"}
