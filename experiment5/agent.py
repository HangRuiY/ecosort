"""实验五：大模型 Agent 核心（agent.py，任务 5.3.1 / 5.3.2）。

- 大脑：DeepSeek（deepseek-chat，OpenAI 兼容接口），密钥从 .env 读取；
- 骨架：LangChain create_agent（LangChain >= 1.0）；
- 工具：tools.py 封装的实验四 detect / text 接口；
- 记忆：对话历史由调用方维护并整段传入（无服务端状态），支持多轮上下文；
- 命令行可直接对话测试单轮/多轮（python agent.py）。

命令行用法：
  python agent.py                # 交互对话；输入 q 退出
  python agent.py "喝完的易拉罐属于什么垃圾？"
"""
from __future__ import annotations

import sys

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from env import load_env, require_key
from tools import TOOLS

SYSTEM_PROMPT = (
    "你是循智 EcoSort 的垃圾分类助手。系统支持五类材质：塑料、纸及纸板、金属、玻璃、食物残余。\n"
    "可用工具（都返回 JSON）：\n"
    "- detect_trash：用户上传图片或给出图片路径时调用，做垃圾检测；\n"
    "- classify_text：用户用文字描述物品时调用，判断材质与投放建议。\n"
    "规则：\n"
    "1. 需要判断材质/投放建议时必须调用工具获取结果，不要凭空编造；\n"
    "2. 工具返回 JSON。检测/分类的完整结果由前端渲染成卡片展示，"
    "你的文字回复只需给出简短自然的总结和注意事项（如需人工核查、清洗建议），"
    "不要逐条罗列全部目标或输出 markdown 表格；\n"
    "3. 回答要基于工具返回内容，简洁、面向普通用户；\n"
    "4. 即使用户询问的物品不在五类范围内（如电池、药品、烟蒂等），也必须调用"
    "classify_text工具获取系统的处理建议，并在回答中说明该物品不在当前五类"
    "检测范围内、建议按一般常识并咨询当地规定处理；\n"
    "5. 用户既没有图片也没有描述时，礼貌引导补充；\n"
    "6. 结合对话上下文理解指代（如“再看看这张”“刚才那个”）。\n"
    "JSON 中的字段含义：name_zh=材质中文名，confidence/prob=置信度(0~1)，"
    "bin_zh=投放建议，needs_review=true 表示需人工核查，evidence=知识库依据编号。"
)


def build_agent():
    env = load_env()
    llm = ChatOpenAI(
        model=env.get("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=require_key(),
        base_url=env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        timeout=60,
        max_retries=1,
    )
    return create_agent(llm, TOOLS, system_prompt=SYSTEM_PROMPT)


def chat(agent, message: str, history: list[dict] | None = None) -> tuple[str, list[str], list[dict]]:
    """发送一条消息，返回 (最终回复, 工具调用轨迹, 结构化工具结果)。

    history 结构：[{"role": "user"|"assistant", "content": str}, ...]
    tool_results：工具返回的 JSON 解析后的列表（前端用它渲染结果卡片）。
    """
    import json as _json

    msgs = [HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"])
            for m in (history or [])]
    msgs.append(HumanMessage(content=message))
    result = agent.invoke({"messages": msgs})

    trace: list[str] = []
    tool_results: list[dict] = []
    reply = ""
    for m in result["messages"]:
        if isinstance(m, AIMessage):
            for tc in getattr(m, "tool_calls", None) or []:
                trace.append(f"调用 {tc['name']}({tc['args']})")
        elif type(m).__name__ == "ToolMessage":
            trace.append(f"  ↳ 结果: {str(m.content)[:80]}")
            try:  # 工具输出是 JSON 字符串，提取结构化数据供前端渲染
                tool_results.append(_json.loads(m.content))
            except Exception:
                pass
    for m in reversed(result["messages"]):
        if isinstance(m, AIMessage) and m.content:
            reply = m.content if isinstance(m.content, str) else str(m.content)
            break
    return reply, trace, tool_results


def main() -> None:
    if len(sys.argv) > 1:  # 单条消息模式
        agent = build_agent()
        reply, trace = chat(agent, sys.argv[1])
        for t in trace:
            print(f"[工具] {t}")
        print(f"回复: {reply}")
        return

    print("循智 EcoSort Agent（输入 q 退出）")
    print("试试：喝完的易拉罐是什么垃圾？  或  帮我看看 <图片路径>")
    agent = build_agent()
    history: list[dict] = []
    while True:
        try:
            user = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user:
            continue
        if user.lower() in {"q", "quit", "exit"}:
            break
        reply, trace = chat(agent, user, history)
        for t in trace:
            print(f"[工具] {t}")
        print(f"助手: {reply}")
        history += [{"role": "user", "content": user},
                    {"role": "assistant", "content": reply}]


if __name__ == "__main__":
    main()
