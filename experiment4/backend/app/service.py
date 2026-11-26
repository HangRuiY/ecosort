"""检测服务：前端上传 → 解码校验 → 实验一标准化 → 实验三模型推理 → 结果封装。"""
from __future__ import annotations

import time
import uuid

from . import config
from .advice import advise, count_bins
from .detector import get_detector
from .errors import InputError
from .preprocess import Letterbox, check_upload, decode_image, standardize
from .reuse import CLASS_KEYS, CLASS_NAMES_ZH


def validate_conf(conf: float) -> float:
    if not 0.01 <= conf <= 0.95:
        raise InputError("置信度阈值需在 0.01 到 0.95 之间")
    return conf


def format_detections(dets: list[dict], lb: Letterbox, region: str) -> list[dict]:
    out = []
    for i, d in enumerate(dets):
        x1, y1, x2, y2 = d["xyxy"]
        out.append({
            "id": i,
            "class_id": d["class_id"],
            "name": CLASS_KEYS[d["class_id"]],
            "name_zh": CLASS_NAMES_ZH[d["class_id"]],
            "confidence": round(d["confidence"], 4),
            "box": {"x1": round(x1, 1), "y1": round(y1, 1), "x2": round(x2, 1), "y2": round(y2, 1)},
            "box_original": lb.to_original(x1, y1, x2, y2),
            "advice": advise(d["class_id"], False, region),
        })
    return out


def detect_bytes(data: bytes, filename: str | None, content_type: str | None, conf: float,
                 backend: str | None, region: str = "general", max_mb: float | None = None) -> dict:
    t0 = time.perf_counter()
    validate_conf(conf)
    check_upload(filename, content_type, data, max_mb or config.MAX_UPLOAD_MB)
    image = decode_image(data)
    t1 = time.perf_counter()
    arr, lb = standardize(image)
    t2 = time.perf_counter()
    det = get_detector()
    used, note = det.pick(backend)
    [(dets, speed)], wall = det.predict([arr], used, conf)
    t3 = time.perf_counter()
    items = format_detections(dets, lb, region)
    bins = count_bins([d["advice"] for d in items])
    return {
        "request_id": uuid.uuid4().hex[:12],
        "filename": filename,
        "image": lb.as_dict(),
        "backend": backend or config.DEFAULT_BACKEND,
        "backend_used": used,
        "backend_note": note,
        "device": det.device,
        "conf": conf,
        "iou": config.NMS_IOU,
        "region": region,
        "count": len(items),
        "detections": items,
        "bins": bins,
        "timing_ms": {
            "decode": round((t1 - t0) * 1000, 2),
            "standardize": round((t2 - t1) * 1000, 2),
            "model_preprocess": speed.get("preprocess"),
            "model_inference": speed.get("inference"),
            "model_postprocess": speed.get("postprocess"),
            "pipeline": wall,
            "total": round((t3 - t0) * 1000, 2),
        },
    }
