"""接口测试：python -m pytest tests -q（在 backend 目录运行）。"""
from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("ECOSORT_TASK_MODE", "local")
from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.main import app  # noqa: E402

SAMPLE = config.SAMPLE_DIR / "000005.png"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def has_model(client):
    return bool(client.get("/api/v1/health").json()["result"]["available_backends"])


def test_health_format(client):
    body = client.get("/api/v1/health").json()
    assert set(body) == {"code", "result", "msg"} and body["code"] == 200
    assert body["result"]["knowledge_base"]["documents"] == 21
    assert body["result"]["reuse_source"] == "experiment1.py"  # 项目原件或 assets 副本


def test_404_unified(client):
    r = client.get("/api/v1/not-exist")
    assert r.status_code == 404 and r.json()["code"] == 404


def test_bad_format(client):
    r = client.post("/api/v1/detect", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 400 and "PNG/JPG" in r.json()["msg"]


def test_corrupt_image(client):
    r = client.post("/api/v1/detect", files={"file": ("a.png", b"not an image", "image/png")})
    assert r.status_code == 400


def test_missing_file(client):
    r = client.post("/api/v1/detect", data={"conf": "0.3"})
    assert r.status_code == 400 and r.json()["msg"] == "缺少图片文件"


def test_conf_range(client):
    r = client.post("/api/v1/detect", files={"file": ("a.png", b"x", "image/png")}, data={"conf": "1.5"})
    assert r.status_code == 400


@pytest.mark.skipif(not SAMPLE.is_file(), reason="缺少实验三验证集示例图")
def test_detect_sample_matches_experiment3(client, has_model):
    if not has_model:
        pytest.skip("没有可用模型")
    r = client.post("/api/v1/detect", files={"file": ("000005.png", SAMPLE.read_bytes(), "image/png")},
                    data={"backend": "pytorch_fp32"}).json()
    res = r["result"]
    assert r["code"] == 200 and res["count"] == 4  # 实验2交接五类模型v4：2金属+1塑料主目标
    top = res["detections"][0]
    assert top["name"] == "metal" and abs(top["confidence"] - 0.91) < 0.03  # v4最高置信目标
    assert res["timing_ms"]["total"] < 2000  # 前端展示延迟 ≤2 秒的后端部分


def test_text(client):
    r = client.post("/api/v1/text", json={"text": "沾了油的外卖塑料餐盒"}).json()["result"]
    assert r["top"]["name"] == "plastic" and r["contaminated"] and r["advice"]["bin"] == "other"
    assert r["evidence"]


def test_text_empty(client):
    assert client.post("/api/v1/text", json={"text": "   "}).status_code == 400


@pytest.mark.skipif(not SAMPLE.is_file(), reason="缺少示例图")
def test_match(client, has_model):
    if not has_model:
        pytest.skip("没有可用模型")
    r = client.post("/api/v1/match", files={"file": ("a.png", SAMPLE.read_bytes(), "image/png")},
                    data={"text": "两个金属罐头"}).json()["result"]
    assert r["verdict"] == "consistent"
    assert [s["step"] for s in r["workflow"]] == ["image_detect", "text_classify", "compare"]


def test_task_flow(client, has_model):
    if not has_model or not config.SAMPLE_DIR.is_dir():
        pytest.skip("没有可用模型或验证集")
    tid = client.post("/api/v1/tasks", data={"source": "validation", "count": "3"}).json()["result"]["task_id"]
    for _ in range(120):
        st = client.get(f"/api/v1/tasks/{tid}").json()["result"]
        if st["state"] in ("SUCCESS", "FAILURE"):
            break
        time.sleep(0.25)
    assert st["state"] == "SUCCESS" and st["done"] == 3
    assert client.get(f"/api/v1/tasks/{tid}/result").json()["result"]["summary"]["images"] == 3


def test_task_404(client):
    assert client.get("/api/v1/tasks/doesnotexist").status_code == 404
