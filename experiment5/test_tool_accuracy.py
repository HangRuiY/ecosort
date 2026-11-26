"""工具调用准确率测试（报告要求：10 轮测试，正确选择工具比例 ≥90%）。

5 条文本查询（期望 classify_text）+ 5 条图像查询（期望 detect_trash），
记录每轮是否选对工具、端到端延迟；结果写入 outputs/tool_accuracy.json。

运行：conda run -n agent python test_tool_accuracy.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from agent import build_agent, chat

SAMPLES = Path(r"D:\AI全栈开发\ecosort\experiment4\backend\assets\samples")

CASES = [  # (查询, 期望工具, 任务类型)
    ("喝完的易拉罐是什么垃圾？", "classify_text", "text"),
    ("快递纸箱怎么投放？", "classify_text", "text"),
    ("废旧电池应该扔哪里？", "classify_text", "text"),
    ("香蕉皮属于哪类垃圾？", "classify_text", "text"),
    ("碎玻璃瓶怎么处理？", "classify_text", "text"),
    (f"帮我看看这张图里有什么垃圾：{SAMPLES / '000005.png'}", "detect_trash", "image"),
    (f"识别一下这张图片里的垃圾：{SAMPLES / '000013.png'}", "detect_trash", "image"),
    (f"分析这张照片：{SAMPLES / '000017.png'}", "detect_trash", "image"),
    (f"图中有什么垃圾？路径：{SAMPLES / '000023.png'}", "detect_trash", "image"),
    (f"检测这张图片：{SAMPLES / '000005.png'}", "detect_trash", "image"),
]


def main() -> None:
    agent = build_agent()
    results = []
    for i, (query, expect, kind) in enumerate(CASES, 1):
        t0 = time.time()
        reply, trace, _results = chat(agent, query)
        latency = round(time.time() - t0, 2)
        called = [t.split("(")[0].replace("调用 ", "") for t in trace if t.startswith("调用 ")]
        ok = expect in called
        results.append({"round": i, "type": kind, "query": query[:40],
                        "expect": expect, "called": called, "ok": ok, "latency_s": latency})
        print(f"[{i:>2}] {'✓' if ok else '✗'} {kind:<5} 期望 {expect:<13} 实际 {called}  {latency}s")

    acc = sum(r["ok"] for r in results) / len(results)
    by_type = {}
    for kind in ("text", "image"):
        rows = [r for r in results if r["type"] == kind]
        by_type[kind] = {
            "accuracy": sum(r["ok"] for r in rows) / len(rows),
            "avg_latency_s": round(sum(r["latency_s"] for r in rows) / len(rows), 2),
        }
    print(f"\n总体工具选择准确率：{acc:.0%}（10 轮，目标 ≥90%）")
    print(f"文本类：准确率 {by_type['text']['accuracy']:.0%}，平均延迟 {by_type['text']['avg_latency_s']}s")
    print(f"图像类：准确率 {by_type['image']['accuracy']:.0%}，平均延迟 {by_type['image']['avg_latency_s']}s")

    out = Path(__file__).parent / "outputs" / "tool_accuracy.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"accuracy": acc, "by_type": by_type, "rounds": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"明细已写入 {out}")


if __name__ == "__main__":
    main()
