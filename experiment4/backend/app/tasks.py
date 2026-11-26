"""批量 / 大图的异步检测任务。

状态沿用 Celery：PENDING → STARTED → SUCCESS / FAILURE，进度写入 storage/tasks/<id>/status.json。
运行模式：
- celery：Redis 可连接且有 worker 在线时，任务交给 Celery worker（可在另一台机器/进程）
- local：没有 Redis 或 worker 时，用 FastAPI 进程内的单线程池执行，接口和状态完全相同
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path

from . import config
from .advice import count_bins
from .detector import get_detector
from .errors import NotFoundError, ServiceUnavailable
from .preprocess import load_path
from .reuse import CLASS_NAMES_ZH
from .service import format_detections

log = logging.getLogger("ecosort")
TASK_DIR = config.STORAGE_DIR / "tasks"
TZ = timezone(timedelta(hours=8))
CHUNK = 8
_local_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ecosort-task")
_io_lock = threading.Lock()
_mode_cache = {"t": 0.0, "mode": "local", "reason": ""}


def _write(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for _ in range(5):  # Windows 下读取方短暂占用文件时重试
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    os.replace(tmp, path)


def _read(path: Path) -> dict:
    for _ in range(5):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, PermissionError):
            time.sleep(0.05)
    return json.loads(path.read_text(encoding="utf-8"))


def status_path(task_id: str) -> Path:
    if not task_id.replace("-", "").isalnum() or len(task_id) > 40:
        raise NotFoundError("任务 ID 不存在")
    return TASK_DIR / task_id / "status.json"


def update(task_id: str, **fields):
    with _io_lock:
        p = status_path(task_id)
        st = _read(p)
        st.update(fields)
        _write(p, st)
        return st


def detect_mode() -> tuple[str, str]:
    """auto 模式下探测 Redis 与 worker，结果缓存 15 秒。"""
    if config.TASK_MODE == "local":
        return "local", "配置为本地线程池"
    now = time.time()
    if config.TASK_MODE == "auto" and now - _mode_cache["t"] < 15:
        return _mode_cache["mode"], _mode_cache["reason"]
    mode, reason = "local", ""
    try:
        import redis
        redis.Redis.from_url(config.REDIS_URL, socket_connect_timeout=0.5, socket_timeout=0.5).ping()
        from .celery_app import celery_app
        workers = celery_app.control.ping(timeout=1.0) or []
        if workers:
            mode, reason = "celery", f"Redis 已连接，{len(workers)} 个 Celery worker 在线"
        else:
            reason = "Redis 已连接但没有 Celery worker，改用本地线程池"
    except Exception as exc:
        reason = f"Redis 不可用（{exc.__class__.__name__}），改用本地线程池"
    if config.TASK_MODE == "celery" and mode != "celery":
        raise ServiceUnavailable(f"任务队列不可用：{reason}")
    _mode_cache.update(t=now, mode=mode, reason=reason)
    return mode, reason


def submit(paths: list[Path], label: str, backend: str | None, conf: float, region: str,
           task_id: str | None = None) -> dict:
    task_id = task_id or new_task_id()
    (TASK_DIR / task_id).mkdir(parents=True, exist_ok=True)
    mode, reason = detect_mode()
    status = {
        "task_id": task_id, "label": label, "state": "PENDING", "mode": mode, "mode_reason": reason,
        "backend": backend or config.DEFAULT_BACKEND, "conf": conf, "region": region,
        "total": len(paths), "done": 0, "progress": 0.0, "objects": 0,
        "created_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "started_at": None, "finished_at": None, "error": None,
        "inputs": [str(p) for p in paths],
    }
    _write(TASK_DIR / task_id / "status.json", status)
    if mode == "celery":
        from .celery_app import detect_batch
        detect_batch.apply_async(args=[task_id], task_id=task_id)
    else:
        _local_pool.submit(run_batch, task_id)
    return public(status)


def new_task_id() -> str:
    return f"{uuid.uuid4().hex[:8]}-{uuid.uuid4().hex[:4]}"


def run_batch(task_id: str, celery_id: str | None = None) -> dict:
    st = _read(status_path(task_id))
    det = get_detector()
    try:
        used, note = det.pick(st["backend"])
        update(task_id, state="STARTED", started_at=datetime.now(TZ).isoformat(timespec="seconds"),
               backend_used=used, backend_note=note)
        paths = [Path(p) for p in st["inputs"]]
        images, total_objects, t0 = [], 0, time.perf_counter()
        for start in range(0, len(paths), CHUNK):
            chunk = paths[start:start + CHUNK]
            arrays, boxes, names = [], [], []
            for p in chunk:
                try:
                    arr, lb = load_path(p)
                    arrays.append(arr); boxes.append(lb); names.append(p.name)
                except Exception as exc:
                    images.append({"file": p.name, "error": getattr(exc, "msg", str(exc)), "detections": []})
            if arrays:
                outputs, _ = det.predict(arrays, used, st["conf"])
                for name, lb, (dets, speed) in zip(names, boxes, outputs):
                    items = format_detections(dets, lb, st["region"])
                    total_objects += len(items)
                    images.append({"file": name, "image": lb.as_dict(), "count": len(items),
                                   "detections": items, "speed_ms": speed})
            done = min(len(paths), start + len(chunk))
            update(task_id, done=done, progress=round(done / len(paths) * 100, 1), objects=total_objects)
        per_class: dict[str, int] = {}
        advices = []
        for im in images:
            for d in im["detections"]:
                per_class[d["name_zh"]] = per_class.get(d["name_zh"], 0) + 1
                advices.append(d["advice"])
        result = {"task_id": task_id, "backend_used": used, "conf": st["conf"], "images": images,
                  "summary": {"images": len(images), "objects": total_objects,
                              "per_class": {k: per_class.get(k, 0) for k in CLASS_NAMES_ZH if per_class.get(k)},
                              "bins": count_bins(advices),
                              "failed_images": sum(1 for im in images if im.get("error")),
                              "duration_s": round(time.perf_counter() - t0, 3)}}
        _write(TASK_DIR / task_id / "result.json", result)
        update(task_id, state="SUCCESS", progress=100.0, finished_at=datetime.now(TZ).isoformat(timespec="seconds"))
        return result["summary"]
    except Exception as exc:
        msg = getattr(exc, "msg", None) or f"{exc.__class__.__name__}: {exc}"
        log.exception("任务 %s 失败", task_id)
        update(task_id, state="FAILURE", error=msg, finished_at=datetime.now(TZ).isoformat(timespec="seconds"))
        raise


def public(st: dict) -> dict:
    return {k: v for k, v in st.items() if k != "inputs"}


def get_status(task_id: str) -> dict:
    p = status_path(task_id)
    if not p.is_file():
        raise NotFoundError("任务 ID 不存在")
    return public(_read(p))


def get_result(task_id: str) -> dict:
    st = get_status(task_id)
    if st["state"] != "SUCCESS":
        raise NotFoundError(f"任务尚未完成（当前状态 {st['state']}）")
    return _read(TASK_DIR / task_id / "result.json")


def list_tasks(limit: int = 20) -> list[dict]:
    if not TASK_DIR.is_dir():
        return []
    files = sorted(TASK_DIR.glob("*/status.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    out = []
    for f in files:
        try:
            out.append(public(_read(f)))
        except Exception:
            continue
    return sorted(out, key=lambda s: s["created_at"], reverse=True)
