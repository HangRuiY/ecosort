"""图文匹配工作流：通过 FastAPI 依赖注入串联 图像检测 → 文本分类 → 类别比对。

FastAPI 按声明顺序解析依赖，所以 image_stage 一定先于 text_stage 执行。
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, File, Form, UploadFile

from ..deps import require_key
from ..errors import ok
from ..reuse import CLASS_NAMES_ZH
from ..schemas import ApiResponse
from ..service import detect_bytes
from ..text_service import answer
from .text import clean_text

router = APIRouter(tags=["图文匹配"])
# Five material classes are distinct. The former ten-class subfamilies do not
# apply after merging the plastic and packaging subclasses.


def image_stage(file: UploadFile = File(...), conf: float = Form(0.25), backend: str | None = Form(None),
                region: str = Form("general")) -> dict:
    t = time.perf_counter()
    r = detect_bytes(file.file.read(), file.filename, file.content_type, conf, backend, region)
    r["stage_ms"] = round((time.perf_counter() - t) * 1000, 2)
    return r


def text_stage(text: str = Form(...), region: str = Form("general")) -> dict:
    t = time.perf_counter()
    r = answer(clean_text(text), region)
    r["stage_ms"] = round((time.perf_counter() - t) * 1000, 2)
    return r


@router.post("/match", response_model=ApiResponse, summary="图文一致性比对",
             description="multipart/form-data：file（图片）+ text（描述）。先检测图片，再分类文字，比对材质类别。")
def match(image=Depends(image_stage), text=Depends(text_stage), _=Depends(require_key)):
    best: dict[int, float] = {}
    for d in image["detections"]:
        best[d["class_id"]] = max(best.get(d["class_id"], 0.0), d["confidence"])
    image_classes = [{"class_id": c, "name_zh": CLASS_NAMES_ZH[c], "confidence": p,
                      "count": sum(1 for d in image["detections"] if d["class_id"] == c)}
                     for c, p in sorted(best.items(), key=lambda x: -x[1])]
    if not text["recognized"]:
        reason = (f"“{text['disposal_item']}”已有单独投放规则，但不属于当前五类视觉材质，无法进行材质比对"
                  if text.get("disposal_recognized") else "文字中没有识别出物品材质，无法比对")
        verdict, score = "unknown", 0.0
    else:
        target = text["top"]["class_id"]
        if target in best:
            verdict, score = "consistent", best[target]
            reason = f"文字描述为“{CLASS_NAMES_ZH[target]}”，图片中检出 {next(c['count'] for c in image_classes if c['class_id'] == target)} 个同类目标"
        elif not best:
            verdict, score, reason = "inconsistent", 0.0, "图片中没有检出任何垃圾目标"
        else:
            verdict, score = "inconsistent", 0.0
            reason = f"文字描述为“{CLASS_NAMES_ZH[target]}”，图片中检出的是{'、'.join(c['name_zh'] for c in image_classes)}"
    result = {
        "verdict": verdict, "score": round(score, 4), "reason": reason,
        "image": {"filename": image["filename"], "count": image["count"], "classes": image_classes,
                  "detections": image["detections"], "image": image["image"], "backend_used": image["backend_used"]},
        "text": {"top": text["top"], "ranking": text["ranking"], "contaminated": text["contaminated"],
                 "advice": text["advice"], "matched_keywords": text["matched_keywords"]},
        "workflow": [
            {"step": "image_detect", "endpoint": "/api/v1/detect", "ms": image["stage_ms"]},
            {"step": "text_classify", "endpoint": "/api/v1/text", "ms": text["stage_ms"]},
            {"step": "compare", "endpoint": "/api/v1/match", "ms": 0.0},
        ],
    }
    return ok(result)
