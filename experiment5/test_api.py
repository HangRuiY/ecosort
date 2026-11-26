"""实验五第 0 步：验证 DeepSeek API 连通（仅用标准库，无需安装任何包）。

运行：python test_api.py
"""
from __future__ import annotations

import json
import time
import urllib.request

from env import load_env

env = load_env()
BASE = env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
MODEL = env.get("DEEPSEEK_MODEL", "deepseek-chat")
KEY = env["DEEPSEEK_API_KEY"]

body = json.dumps({
    "model": MODEL,
    "messages": [
        {"role": "system", "content": "你是测试助手，只回复要求的内容。"},
        {"role": "user", "content": "回复四个字：API连通"},
    ],
}).encode("utf-8")

req = urllib.request.Request(
    f"{BASE}/chat/completions",
    data=body,
    headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
)

t0 = time.time()
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode("utf-8"))
latency = time.time() - t0

reply = data["choices"][0]["message"]["content"]
usage = data.get("usage", {})
print(f"模型:   {MODEL}")
print(f"回复:   {reply}")
print(f"延迟:   {latency:.2f}s")
print(f"tokens: prompt={usage.get('prompt_tokens')} completion={usage.get('completion_tokens')}")
print("✅ DeepSeek API 连通正常")
