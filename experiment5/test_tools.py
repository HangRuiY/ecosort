"""工具层联调：不经大模型，直接调用 tools.py 的两个工具（需实验4后端已启动）。

运行：conda run -n agent python test_tools.py
"""
from __future__ import annotations

from pathlib import Path

from tools import classify_text, detect_trash

SAMPLE = Path(r"D:\AI全栈开发\ecosort\experiment4\backend\assets\samples\000005.png")

print("=== 工具1：detect_trash ===")
out = detect_trash.invoke({"image_path": str(SAMPLE)})
print(out)

print("\n=== 工具2：classify_text ===")
out = classify_text.invoke({"text": "沾了油的外卖塑料餐盒"})
print(out)

print("\n=== 异常路径：不存在的图片 ===")
out = detect_trash.invoke({"image_path": "X:/not_exist/cat.png"})
print(out)
