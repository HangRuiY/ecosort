import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import llm_fallback


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def generated(text):
    return {
        "source": "deepseek", "method": "llm-disposal", "recognized": False,
        "disposal_recognized": True, "disposal_item": text, "top": None,
        "ranking": [], "matched_keywords": [], "evidence": [],
        "reply": "请交正规电子产品回收渠道处理，提前做好个人数据保护。",
        "advice": {"bin": None, "bin_zh": "专项回收", "needs_review": True, "reason": "属于电子废弃物"},
    }


@pytest.mark.parametrize("text", ["废电脑", "废手机", "旧路由器", "我换下来的平板怎么处理？"])
def test_uncovered_item_uses_original_question(client, monkeypatch, text):
    calls = []
    def request(question, region):
        calls.append((question, region))
        return {"code": 200, "result": generated(text)}
    monkeypatch.setattr(llm_fallback, "_request_answer", request)
    body = client.post("/api/v1/text", json={"text": text, "region": "shanghai"}).json()
    assert body["code"] == 200 and body["msg"] == "ok"
    assert calls == [(text, "shanghai")]
    assert body["result"]["source"] == "deepseek"
    assert body["result"]["advice"]["bin_zh"] == "专项回收"
    assert body["result"]["top"] is None and body["result"]["ranking"] == []


@pytest.mark.parametrize("text", ["烟头", "废电池", "干净的塑料瓶", "沾了油的外卖塑料餐盒"])
def test_local_rules_skip_direct_llm(client, monkeypatch, text):
    def unexpected(*args):
        pytest.fail("A local answer must not call the direct LLM endpoint")
    monkeypatch.setattr(llm_fallback, "_request_answer", unexpected)
    result = client.post("/api/v1/text", json={"text": text}).json()["result"]
    assert result["advice"] and result.get("source") != "deepseek"


def test_unavailable_llm_returns_visible_failure(client, monkeypatch):
    monkeypatch.setattr(llm_fallback, "_request_answer", lambda *args: (_ for _ in ()).throw(TimeoutError()))
    body = client.post("/api/v1/text", json={"text": "废电脑"}).json()
    assert body["result"]["fallback_status"] == "unavailable"
    assert "AI 问答服务暂时不可用" in body["result"]["fallback_message"]
    assert body["result"]["top"] is None


@pytest.mark.parametrize("body", [{"code": 503, "result": {}}, {"code": 200, "result": {}}, {"code": 200, "result": {"source": "deepseek", "reply": "incomplete"}}])
def test_malformed_answer_is_not_displayed(client, monkeypatch, body):
    monkeypatch.setattr(llm_fallback, "_request_answer", lambda *args: body)
    result = client.post("/api/v1/text", json={"text": "废手机"}).json()["result"]
    assert result["fallback_status"] == "unavailable"
