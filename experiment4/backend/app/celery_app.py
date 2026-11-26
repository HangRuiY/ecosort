"""Celery 应用：Redis 作为消息队列和结果存储。

Windows 启动 worker（需在 backend 目录、同一 Python 环境）：
    celery -A app.celery_app worker --pool=solo -l info
"""
from __future__ import annotations

from celery import Celery

from . import config

celery_app = Celery("ecosort", broker=config.REDIS_URL, backend=config.REDIS_URL)
celery_app.conf.update(
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    result_expires=24 * 3600,
)


@celery_app.task(name="ecosort.detect_batch", bind=True)
def detect_batch(self, task_id: str):
    from .detector import get_detector
    from .tasks import run_batch
    get_detector().load_all()
    return run_batch(task_id, celery_id=self.request.id)
