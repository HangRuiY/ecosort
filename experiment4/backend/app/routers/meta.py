from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from .. import __version__, config
from .. import tasks as T
from ..advice import BINS, MATERIAL_RULES, REGIONS
from ..detector import get_detector
from ..errors import NotFoundError, ok
from ..reuse import CLASS_KEYS, CLASS_NAMES_ZH, SOURCE
from ..schemas import ApiResponse
from ..text_service import get_kb

router = APIRouter(tags=["服务信息"])


@router.get("/health", response_model=ApiResponse, summary="服务与模型状态")
def health():
    det = get_detector()
    info = det.health()
    kb = get_kb()
    mode, reason = T.detect_mode()
    available = det.available()
    return ok({
        "status": "ok" if available else "degraded",
        "version": __version__,
        **info,
        "available_backends": available,
        "knowledge_base": {"documents": len(kb.records), "error": kb.error},
        "tasks": {"mode": mode, "reason": reason},
        "reuse_source": SOURCE,
        "data_source": "project" if config.EXP3_DIR.is_dir() else "experiment4/backend/assets",
        "limits": {"max_upload_mb": config.MAX_UPLOAD_MB, "max_text_len": config.MAX_TEXT_LEN,
                   "max_batch_files": config.MAX_BATCH_FILES, "max_task_file_mb": config.MAX_TASK_FILE_MB},
    })


@router.get("/classes", response_model=ApiResponse, summary="五类材质与默认投放规则")
def classes():
    return ok({
        "classes": [{"class_id": i, "name": CLASS_KEYS[i], "name_zh": CLASS_NAMES_ZH[i],
                     "default_bin": MATERIAL_RULES[i][0], "needs_review": MATERIAL_RULES[i][1],
                     "note": MATERIAL_RULES[i][2]} for i in range(len(CLASS_KEYS))],
        "bins": BINS, "regions": REGIONS,
    })


@router.get("/samples", response_model=ApiResponse, summary="示例图片列表（实验三验证集）")
def samples():
    items = [{"id": s, "url": f"/api/v1/samples/{s}.png"} for s in config.SAMPLE_IDS
             if (config.SAMPLE_DIR / f"{s}.png").is_file()]
    return ok({"samples": items})


@router.get("/samples/{name}", summary="示例图片文件")
def sample_file(name: str):
    stem = name.rsplit(".", 1)[0]
    path = config.SAMPLE_DIR / f"{stem}.png"
    if stem not in config.SAMPLE_IDS or not path.is_file():
        raise NotFoundError("示例图片不存在")
    return FileResponse(path, media_type="image/png")
