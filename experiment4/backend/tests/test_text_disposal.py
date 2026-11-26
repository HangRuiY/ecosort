"""Regression checks for text examples outside the five visual classes."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.text_service import answer


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("text", ["烟头", "地上的烟头", "烟蒂", "烟屁股", "用纸包好的烟头", "香烟过滤嘴", "cigarette butt"])
@pytest.mark.parametrize("region,expected", [("general", "其他垃圾"), ("shanghai", "干垃圾")])
def test_cigarette_has_disposal_without_fake_material(client, text, region, expected):
    body = client.post("/api/v1/text", json={"text": text, "region": region}).json()
    result = body["result"]
    assert body["code"] == 200 and body["msg"] == "ok"
    assert result["disposal_recognized"] and not result["recognized"]
    assert result["top"] is None and result["ranking"] == []
    assert result["advice"]["bin"] == "other" and result["advice"]["bin_zh"] == expected
    assert result["rule_source"]["source_url"].startswith("https://lhsr.sh.gov.cn/")


@pytest.mark.parametrize("text", ["废电池", "纽扣电池", "普通干电池", "锂电池"])
def test_unspecified_battery_requires_type(text):
    result = answer(text)
    assert result["disposal_recognized"] and result["top"] is None
    assert result["advice"]["bin"] is None and result["advice"]["needs_review"]
    assert "确认电池类型" in result["advice"]["bin_zh"]


@pytest.mark.parametrize("text", ["镍镉电池", "氧化汞电池"])
def test_explicit_hazardous_battery(text):
    assert answer(text)["advice"]["bin"] == "hazardous"


def test_cigarette_and_battery_are_not_assigned_one_bin():
    result = answer("烟头和废电池")
    assert result["advice"]["bin"] is None and result["advice"]["needs_review"]


@pytest.mark.parametrize("text", ["喝完的易拉罐", "吃剩的果皮", "地上的烟头", "干净的快递纸箱", "碎掉的玻璃杯", "用完的牛奶盒", "用过的纸巾", "废电池"])
def test_every_frontend_example_has_guidance(client, text):
    result = client.post("/api/v1/text", json={"text": text}).json()["result"]
    assert result["advice"] and (result["recognized"] or result.get("disposal_recognized"))


def test_unknown_remains_unknown():
    result = answer("xyz123")
    assert not result["recognized"] and not result.get("disposal_recognized")
    assert result["advice"] is None and result["top"] is None


def test_cigarette_box_is_still_paper():
    result = answer("香烟纸盒")
    assert result["top"]["name"] == "paper_cardboard"


@pytest.mark.parametrize("text", ["烟头", "废电池"])
def test_agent_tool_keeps_disposal_guidance_without_fake_probability(monkeypatch, text):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "experiment5"))
    import tools
    monkeypatch.setattr(tools, "_post_with_retry", lambda *a, **k: {"code": 200, "result": answer(text)})
    result = json.loads(tools.classify_text.invoke({"text": text}))
    assert result["recognized"] and not result["material_recognized"]
    assert result["class_id"] is None and result["prob"] is None
    assert result["reason"] and result["evidence"]


def test_image_match_does_not_invent_a_cigarette_class(client):
    sample = config.SAMPLE_DIR / "taco_011368.png"
    body = client.post("/api/v1/match", files={"file": (sample.name, sample.read_bytes(), "image/png")}, data={"text": "烟头"}).json()
    assert body["code"] == 200 and body["result"]["verdict"] == "unknown"
    assert "不属于当前五类" in body["result"]["reason"]
