"""实验五：把实验四后端 API 封装为 Agent 可调用的工具（任务 5.3.1）。

复用关系：两个工具分别对接实验四的 /api/v1/detect 与 /api/v1/text 接口。
返回值统一为 JSON 字符串：
- 大模型直接阅读 JSON 组织自然语言总结；
- 结构化数据同时被 agent.py 提取为 tool_results，随 API 返回给前端渲染结果卡片。

异常处理：每次工具调用内置 3 次重试（任务书"重点关注 3"），失败时返回
{"ok": false, "error": ...}，让 Agent 能向用户解释而不是崩溃。
"""
from __future__ import annotations

import json
from pathlib import Path

import requests
from langchain_core.tools import tool

from env import load_env

_API = load_env().get("AGENT_API_BASE", "http://localhost:8000/api/v1").rstrip("/")
_TIMEOUT = 60
_RETRIES = 3
_MAX_ROWS = 20  # 结果卡片最多展示的目标数


def _post_with_retry(url: str, **kwargs) -> dict:
    """POST，3 次重试；最终失败抛 RuntimeError（由各工具捕获转成提示）。"""
    last_err: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            r = requests.post(url, timeout=_TIMEOUT, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # 网络/超时/5xx 都重试
            last_err = exc
            if attempt < _RETRIES:
                continue
    raise RuntimeError(f"{_RETRIES} 次尝试均失败：{last_err}")


@tool
def detect_trash(image_path: str) -> str:
    """对一张图片进行垃圾检测。输入：本地图片的完整路径（JPG/PNG）。
    返回：JSON，含每个目标的材质类别、置信度与投放建议。当用户上传图片或给出图片路径时使用本工具。"""
    path = Path(image_path.strip().strip('"'))
    if not path.exists():
        return json.dumps({"ok": False, "error": f"找不到图片文件 {path}"}, ensure_ascii=False)
    try:
        with path.open("rb") as f:
            data = _post_with_retry(f"{_API}/detect", files={"file": f}, data={"conf": "0.40"})
    except RuntimeError as exc:
        return json.dumps({"ok": False, "error": f"图像检测服务暂时不可用，请稍后再试（{exc}）"}, ensure_ascii=False)
    if data.get("code") != 200:
        return json.dumps({"ok": False, "error": f"检测接口返回异常 - {data.get('msg')}"}, ensure_ascii=False)
    result = data["result"]
    dets = [
        {
            "class_id": d["class_id"],
            "name_zh": d["name_zh"],
            "confidence": round(float(d["confidence"]), 3),
            "bin_key": d["advice"].get("bin"),
            "bin_zh": d["advice"].get("bin_zh", d["advice"].get("bin", "待核查")),
            "needs_review": bool(d["advice"].get("needs_review")),
            "box": d.get("box"),  # 640×640 坐标，前端画框用
        }
        for d in result.get("detections", [])[:_MAX_ROWS]
    ]
    return json.dumps({
        "ok": True,
        "count": result.get("count", len(dets)),
        "truncated": result.get("count", len(dets)) > len(dets),
        "backend": result.get("backend_used"),
        "total_ms": (result.get("timing_ms") or {}).get("total"),
        "source": path.stem,  # 图片名（去扩展名），命中示例集时前端可直接取图
        "detections": dets,
    }, ensure_ascii=False)


@tool
def classify_text(text: str) -> str:
    """判断一段物品文字描述的材质类别与投放建议。输入：不超过300字的中文物品描述。
    返回：JSON，含材质类别、置信度、投放建议与知识库依据。当用户用文字描述物品时使用本工具。"""
    desc = text.strip()
    if not desc:
        return json.dumps({"ok": False, "error": "描述为空"}, ensure_ascii=False)
    if len(desc) > 300:
        desc = desc[:300]
    try:
        data = _post_with_retry(f"{_API}/text", json={"text": desc})
    except RuntimeError as exc:
        return json.dumps({"ok": False, "error": f"文本分析服务暂时不可用，请稍后再试（{exc}）"}, ensure_ascii=False)
    if data.get("code") != 200:
        return json.dumps({"ok": False, "error": f"文本接口返回异常 - {data.get('msg')}"}, ensure_ascii=False)
    r = data["result"]
    if not r.get("recognized") and not r.get("disposal_recognized"):
        return json.dumps({"ok": True, "recognized": False,
                           "error": "未能识别该描述的材质，建议用户换个说法或提供图片"}, ensure_ascii=False)
    top = r.get("top") or {}
    advice = r.get("advice") or {}
    evidence = [(e.get("title") or e.get("id") or "") for e in (r.get("evidence") or [])[:3]]
    if r.get("rule_source"):
        evidence.insert(0, r["rule_source"]["title"])
    return json.dumps({
        "ok": True,
        "recognized": True,
        "material_recognized": bool(r.get("recognized")),
        "class_id": top.get("class_id"),
        "name_zh": top.get("name_zh") or r.get("disposal_item"),
        "prob": round(float(top["prob"]), 3) if top.get("prob") is not None else None,
        "bin_key": advice.get("bin"),
        "bin_zh": advice.get("bin_zh", advice.get("bin", "待核查")),
        "needs_review": bool(advice.get("needs_review")),
        "reason": advice.get("reason"),
        "contaminated": bool(r.get("contaminated")),
        "evidence": [e for e in evidence if e],
    }, ensure_ascii=False)


TOOLS = [detect_trash, classify_text]
