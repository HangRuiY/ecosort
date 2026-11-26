from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from .. import config
from .. import tasks as T
from ..deps import require_key
from ..errors import InputError, PayloadTooLarge, ok
from ..preprocess import check_upload
from ..schemas import ApiResponse
from ..service import validate_conf

router = APIRouter(tags=["异步任务"])


@router.post("/tasks", response_model=ApiResponse, summary="提交批量检测任务",
             description="两种方式：① files 上传多张图片（每张 ≤30 MB，最多 64 张）；"
                         "② source=validation 且 count=N，从实验三验证集取前 N 张。返回 task_id，用 GET /tasks/{id} 轮询。")
def create_task(files: list[UploadFile] | None = File(None), source: str | None = Form(None),
                count: int = Form(32), conf: float = Form(0.25), backend: str | None = Form(None),
                region: str = Form("general"), _=Depends(require_key)):
    validate_conf(conf)
    if source == "validation":
        if not 1 <= count <= config.MAX_BATCH_FILES:
            raise InputError(f"count 需在 1 到 {config.MAX_BATCH_FILES} 之间")
        if not config.SAMPLE_DIR.is_dir():
            raise InputError("找不到验证集目录 experiment3/data/images/val")
        paths = sorted(p for p in config.SAMPLE_DIR.iterdir() if p.suffix.lower() in config.ALLOWED_SUFFIXES)[:count]
        label = f"验证集 {len(paths)} 张"
        return ok(T.submit(paths, label, backend, conf, region), "已提交")
    if not files:
        raise InputError("请上传至少一张图片，或使用 source=validation")
    if len(files) > config.MAX_BATCH_FILES:
        raise PayloadTooLarge(f"一次最多提交 {config.MAX_BATCH_FILES} 张，本次 {len(files)} 张")
    task_id = T.new_task_id()
    folder = T.TASK_DIR / task_id / "inputs"
    folder.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    try:
        for i, f in enumerate(files):
            data = f.file.read()
            check_upload(f.filename, f.content_type, data, config.MAX_TASK_FILE_MB)
            safe = f"{i:03d}{Path(f.filename or 'img.jpg').suffix.lower() or '.jpg'}"
            p = folder / safe
            p.write_bytes(data)
            paths.append(p)
    except Exception:
        shutil.rmtree(folder.parent, ignore_errors=True)
        raise
    names = [f.filename for f in files]
    label = names[0] if len(names) == 1 else f"{names[0]} 等 {len(names)} 张"
    return ok(T.submit(paths, label, backend, conf, region, task_id=task_id), "已提交")


@router.get("/tasks", response_model=ApiResponse, summary="最近的任务")
def recent():
    return ok({"tasks": T.list_tasks(), "mode": T.detect_mode()[0]})


@router.get("/tasks/{task_id}", response_model=ApiResponse, summary="查询任务状态与进度")
def status(task_id: str):
    return ok(T.get_status(task_id))


@router.get("/tasks/{task_id}/result", response_model=ApiResponse, summary="下载任务结果")
def result(task_id: str):
    return ok(T.get_result(task_id))
