"""图片上传链路测试：multipart 带 file 调 /api/v1/agent/chat。

运行：conda run -n agent python test_upload.py   （需 agent_api 在 8001、后端在 8000）
"""
import json
import time
from pathlib import Path

import requests

BASE = "http://localhost:8001/api/v1/agent"
SAMPLE = Path(r"D:\AI全栈开发\ecosort\experiment4\backend\assets\samples\000005.png")

# 等服务就绪
for _ in range(15):
    try:
        if requests.get(f"{BASE}/health", timeout=2).status_code == 200:
            break
    except Exception:
        pass
    time.sleep(2)
print("服务已就绪\n")

# 1) 带图上传 + 一句话描述
with SAMPLE.open("rb") as f:
    t0 = time.time()
    r = requests.post(f"{BASE}/chat",
                      data={"message": "帮我看看这张图里有什么垃圾", "history": "[]"},
                      files={"file": (SAMPLE.name, f, "image/png")}, timeout=120)
d = r.json()
print("上传聊天: http", r.status_code, "| code", d["code"], f"| 总耗时 {time.time() - t0:.1f}s")
res = d["result"]
det = next((x for x in res["tool_results"] if x.get("ok") and "detections" in x), None)
print("tool_results 类型数:", len(res["tool_results"]), "| 检测结果含目标数:", det and det["count"])
print("reply:", res["reply"][:120], "...\n")

# 2) 纯文本（JSON 通道回归）
r2 = requests.post(f"{BASE}/chat", json={"message": "喝完的易拉罐是什么垃圾？"}, timeout=120)
d2 = r2.json()
txt = next((x for x in d2["result"]["tool_results"] if x.get("ok") and "name_zh" in x), None)
print("文本聊天: code", d2["code"], "| 结构化:", txt and {"name_zh": txt["name_zh"], "bin_zh": txt["bin_zh"]})

# 3) 非法格式 400
r3 = requests.post(f"{BASE}/chat",
                   data={"message": "看看这个"}, files={"file": ("a.gif", b"GIF89a", "image/gif")}, timeout=30)
print("gif 上传 -> code:", r3.json()["code"], "|", r3.json()["msg"])

# 4) 超大小模拟（>10MB 的 png 头填充）
big = b"\x89PNG\r\n\x1a\n" + b"0" * (10 * 1024 * 1024 + 100)
r4 = requests.post(f"{BASE}/chat",
                   data={"message": "看看这个"}, files={"file": ("big.png", big, "image/png")}, timeout=60)
print("超大上传 -> code:", r4.json()["code"], "|", r4.json()["msg"])

# 5) 临时文件已清理
leftovers = list(Path("storage/uploads").glob("*")) if Path("storage/uploads").exists() else []
print("uploads 目录残留:", len(leftovers), "个文件")
