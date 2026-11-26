import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import agent_api
from llm_disposal import generate_advice


class StubLLM:
    def __init__(self, **changes):
        self.payload = {"relevant": True, "item": "废手机", "category": "special", "reason": "需要电子产品回收渠道", "answer": "请交正规回收渠道，提前备份并清理个人数据。", **changes}

    def with_structured_output(self, schema, method):
        assert method == "json_mode"
        return self

    def invoke(self, messages):
        self.question = json.loads(messages[-1].content)
        return self.payload


@pytest.mark.parametrize("text", ["废电脑", "废手机", "坏掉的路由器"])
def test_direct_answer_preserves_question_and_source(text):
    llm = StubLLM(item=text)
    result = generate_advice(llm, text, "shanghai")
    assert llm.question == {"question": text, "region": "上海"}
    assert result["source"] == "deepseek" and result["reply"]
    assert result["top"] is None and result["evidence"] == []
    assert result["advice"]["bin"] is None and result["advice"]["bin_zh"] == "专项回收"


def test_unrelated_question_is_not_assigned_a_bin():
    result = generate_advice(StubLLM(relevant=False, category="unknown", answer="请描述需要分类或回收的物品。"), "你好", "general")
    assert result["advice"] is None and not result["disposal_recognized"] and result["reply"]


def test_invalid_generated_category_is_rejected():
    with pytest.raises(ValidationError):
        generate_advice(StubLLM(category="invented"), "废手机", "general")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(agent_api, "build_agent", lambda: object())
    monkeypatch.setattr(agent_api, "_get_advice_llm", lambda: StubLLM())
    with TestClient(agent_api.app) as client:
        yield client


def test_answer_api(client):
    response = client.post("/api/v1/agent/answer", json={"text": "废手机", "region": "general"})
    assert response.json()["code"] == 200
    assert response.json()["result"]["source"] == "deepseek"


def test_empty_query_is_rejected(client):
    assert client.post("/api/v1/agent/answer", json={"text": "   "}).json()["code"] == 400
    assert client.post("/api/v1/agent/answer", json={"text": "字" * 301}).status_code == 422


def test_provider_error_is_actionable(client, monkeypatch):
    monkeypatch.setattr(agent_api, "_get_advice_llm", lambda: (_ for _ in ()).throw(TimeoutError()))
    response = client.post("/api/v1/agent/answer", json={"text": "废手机"})
    assert response.json()["code"] == 503 and "暂时不可用" in response.json()["msg"]
