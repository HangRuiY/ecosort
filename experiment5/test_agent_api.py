"""Agent API 测试（需 agent_api 已在 8001 运行、实验4后端在 8000 运行）。

运行：conda run -n agent python test_agent_api.py
"""
import json
import time

import requests

BASE = "http://localhost:8001/api/v1/agent"

h = requests.get(f"{BASE}/health", timeout=10).json()
print("health:", h["result"])

t0 = time.time()
r = requests.post(f"{BASE}/chat", json={"message": "沾了油的外卖塑料餐盒应该扔哪个垃圾桶？"}, timeout=120)
d = r.json()
print("chat: http", r.status_code, "| code", d["code"], f"| 总耗时 {time.time() - t0:.1f}s")
print("tool_calls:", d["result"]["tool_calls"])
print("reply:", d["result"]["reply"][:100], "...")
print("latency_ms:", d["result"]["latency_ms"])

# 400：空消息
r2 = requests.post(f"{BASE}/chat", json={"message": "  "}, timeout=30)
print("空消息 ->", r2.json()["code"], r2.json()["msg"])

# 400：超长
r3 = requests.post(f"{BASE}/chat", json={"message": "字" * 1001}, timeout=30)
print("超长   ->", r3.json()["code"], r3.json()["msg"])

# 多轮：带 history
r4 = requests.post(f"{BASE}/chat", timeout=120, json={
    "message": "那刚才说的这个，冲洗干净后呢？",
    "history": [
        {"role": "user", "content": "沾了油的外卖塑料餐盒应该扔哪个垃圾桶？"},
        {"role": "assistant", "content": d["result"]["reply"]},
    ]})
print("多轮  ->", r4.json()["result"]["reply"][:120], "...")
