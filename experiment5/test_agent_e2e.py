"""Agent 端到端推理测试（任务 5.3.2）：单轮文本、单轮图像、多轮上下文。

运行：conda run -n agent python test_agent_e2e.py
（需实验4后端已在 8000 端口运行）
"""
from __future__ import annotations

import time

from agent import build_agent, chat

SAMPLE = r"D:\AI全栈开发\ecosort\experiment4\backend\assets\samples\000005.png"


def run(agent, title: str, message: str, history=None):
    print(f"\n{'=' * 10} {title} {'=' * 10}")
    print(f"用户: {message}")
    t0 = time.time()
    reply, trace, _results = chat(agent, message, history)
    for t in trace:
        print(f"[工具] {t}")
    print(f"助手: {reply}")
    print(f"(端到端耗时 {time.time() - t0:.1f}s)")
    return {"role": "user", "content": message}, {"role": "assistant", "content": reply}


def main() -> None:
    agent = build_agent()

    # 场景 1：单轮文本 → 应调用 classify_text
    u1, a1 = run(agent, "场景1：单轮文本", "沾了油的外卖塑料餐盒应该扔哪个垃圾桶？")

    # 场景 2：单轮图像路径 → 应调用 detect_trash
    u2, a2 = run(agent, "场景2：单轮图像", f"帮我看看这张图里有什么垃圾：{SAMPLE}")

    # 场景 3：多轮上下文 → 指代“那张图”，不应再调工具也应答得上
    hist = [u1, a1, u2, a2]
    run(agent, "场景3：多轮上下文", "刚才那张图里的东西，总结一下该怎么投放？", hist)


if __name__ == "__main__":
    main()
