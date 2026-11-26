"""实验五：Agent 服务 API（agent_api.py，任务 5.4.1）。

将 Agent 封装为 FastAPI 服务，端口 8001，路径与实验四的 /api/v1 版本规范对齐。

接口：
  POST /api/v1/agent/chat
      JSON  {"message": str, "history": [{"role","content"}, ...]}
      multipart  message + history(JSON字符串) + file(可选，JPG/PNG，≤10MB)
      → {"code": 200, "result": {"reply", "tool_calls", "tool_results", "latency_ms"}, "msg": "ok"}
  GET  /api/v1/agent/health → 服务与依赖状态

规范对齐（任务书"重点关注"）：
- 返回体沿用实验四统一结构 {code, result, msg}；
- 错误码：400 参数错、404 ToolNotFound、500 服务器错；
- 工具层已内置 3 次重试（见 tools.py），本层记录详细日志（用户查询 + 工具响应）；
- CORS 允许实验四前端来源（localhost:5173 / 3000 / 8080）。

运行：conda run -n agent uvicorn agent_api:app --host 0.0.0.0 --port 8001
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import build_agent, chat
from env import load_env, require_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("agent_api.log", encoding="utf-8")],
)
log = logging.getLogger("agent_api")

MAX_MESSAGE_LEN = 1000
MAX_HISTORY = 20          # 最多携带最近 20 条历史，防止上下文无限膨胀
MAX_IMAGE_MB = 10         # 与实验四单图上限一致
ALLOWED_EXTS = {".jpg", ".jpeg", ".png"}
UPLOAD_DIR = Path(__file__).resolve().parent / "storage" / "uploads"

app = FastAPI(title="EcoSort Agent API", version="1.1.0",
              description="实验五：大模型 Agent 服务（基于 LangChain + DeepSeek，工具来自实验四 API，支持图片上传）")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000",
                   "http://localhost:8080", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

_agent = None
_llm = None
_advice_llm = None


def _get_llm():
    """文本问答页的解读模型：直接调用 DeepSeek，不经过工具。"""
    global _llm
    if _llm is None:
        from langchain_openai import ChatOpenAI
        env = load_env()
        _llm = ChatOpenAI(
            model=env.get("DEEPSEEK_MODEL", "deepseek-chat"),
            api_key=require_key(),
            base_url=env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            timeout=60,
            max_retries=1,
        )
    return _llm


def fail(code: int, msg: str, result: dict | None = None) -> dict:
    return {"code": code, "result": result or {}, "msg": msg}


def _get_advice_llm():
    global _advice_llm
    if _advice_llm is None:
        from langchain_openai import ChatOpenAI
        env = load_env()
        _advice_llm = ChatOpenAI(
            model=env.get("DEEPSEEK_MODEL", "deepseek-chat"), api_key=require_key(),
            base_url=env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            timeout=30, max_retries=0, temperature=0,
        )
    return _advice_llm


class DisposalQuery(BaseModel):
    text: str = Field(..., min_length=1, max_length=300)
    region: Literal["general", "shanghai"] = "general"


@app.post("/api/v1/agent/answer")
async def agent_answer(body: DisposalQuery):
    """本地规则没有答案时，直接生成物品回收建议，不再循环调用本地分类工具。"""
    from fastapi.concurrency import run_in_threadpool
    from llm_disposal import generate_advice
    text = body.text.strip()
    if not text:
        return fail(400, "请描述要处理的物品")
    t0 = time.time()
    try:
        result = await run_in_threadpool(lambda: generate_advice(_get_advice_llm(), text, body.region))
    except Exception:
        log.exception("直接 AI 问答失败")
        return fail(503, "AI 问答暂时不可用，请稍后重试")
    result["latency_ms"] = round((time.time() - t0) * 1000, 1)
    return {"code": 200, "msg": "ok", "result": result}


@app.on_event("startup")
def _startup():
    global _agent
    t0 = time.time()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    _agent = build_agent()
    log.info("Agent 初始化完成，耗时 %.1fs（加载 LangChain/DeepSeek 配置）", time.time() - t0)


async def _parse_request(request: Request) -> tuple[str | None, list[dict], Path | None, str | None]:
    """统一解析 JSON / multipart 两种请求体，返回 (message, history, 保存的图片路径, 错误信息)。"""
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/"):
        form = await request.form()
        message = str(form.get("message") or "")
        try:
            history = json.loads(form.get("history") or "[]")
        except Exception:
            return None, [], None, "history 字段不是合法 JSON"
        upload = form.get("file")
        if upload is None or isinstance(upload, str):
            return message, history, None, None
        ext = Path(str(upload.filename) or "").suffix.lower()
        if ext not in ALLOWED_EXTS:
            return None, [], None, f"图片格式 {ext or '未知'} 不支持，请上传 JPG/PNG"
        data = await upload.read()
        if len(data) > MAX_IMAGE_MB * 1024 * 1024:
            return None, [], None, f"图片大小 {len(data) / 1048576:.1f} MB，超过 {MAX_IMAGE_MB} MB 上限"
        if not data:
            return None, [], None, "图片内容为空"
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        path = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
        path.write_bytes(data)
        return message, history, path, None
    body = await request.json()
    return str(body.get("message") or ""), body.get("history") or [], None, None


@app.post("/api/v1/agent/chat")
async def agent_chat(request: Request):
    from fastapi.concurrency import run_in_threadpool

    message, history, image_path, err = await _parse_request(request)
    if err:
        return fail(400, err)
    message = (message or "").strip()
    if not message and image_path is None:
        return fail(400, "消息为空，请输入内容或上传图片")
    if len(message) > MAX_MESSAGE_LEN:
        return fail(400, f"消息长度 {len(message)} 字，超过 {MAX_MESSAGE_LEN} 字上限")
    history = [h for h in history[-MAX_HISTORY:]
               if isinstance(h, dict) and h.get("role") in ("user", "assistant") and h.get("content")]

    # 上传的图片落盘后，把路径附进消息，让大模型调用 detect_trash 工具
    if image_path is not None:
        hint = f"（用户上传了一张图片，本地路径：{image_path}）"
        message = f"{message} {hint}".strip() if message else f"请检测这张图片 {hint}"

    t0 = time.time()
    try:
        # chat() 含同步 LLM/HTTP 调用，放线程池执行，避免阻塞事件循环
        # （否则聊天期间健康检查等所有请求都会超时）
        reply, trace, tool_results = await run_in_threadpool(chat, _agent, message, history)
    except Exception as exc:
        text = str(exc)
        if "ToolNotFound" in text or "tool_not_found" in text:
            log.error("工具未找到：%s", text)
            return fail(404, "请求的工具不存在（ToolNotFound）")
        if "timeout" in text.lower() or "timed out" in text.lower():
            log.error("Agent 推理超时：%s", text)
            return fail(500, "助手思考超时，请稍后重试")
        log.exception("Agent 推理失败")
        return fail(500, "服务暂时不可用，请稍后重试")
    finally:
        if image_path is not None:
            try:  # 推理完成后清理临时上传文件
                image_path.unlink(missing_ok=True)
            except Exception:
                pass

    latency_ms = round((time.time() - t0) * 1000, 1)
    log.info("查询: %s | 工具轨迹: %s | 延迟: %sms", message[:80], " -> ".join(trace) or "无", latency_ms)
    return {"code": 200, "msg": "ok",
            "result": {"reply": reply, "tool_calls": trace,
                       "tool_results": tool_results, "latency_ms": latency_ms}}


class ExplainQuery(BaseModel):
    text: str = Field(..., description="用户的物品描述")
    name_zh: str | None = Field(default=None, description="系统判定的材质中文名")
    bin_zh: str | None = Field(default=None, description="系统给出的投放建议")
    prob: float | None = Field(default=None, description="判定置信度")
    contaminated: bool = Field(default=False, description="是否检测到污染语义")
    evidence: list[str] = Field(default_factory=list, description="知识库依据条目")


@app.post("/api/v1/agent/explain")
async def agent_explain(body: ExplainQuery):
    """为文本问答结果生成一段自然的 AI 解读（直接调用 DeepSeek，无工具）。"""
    from fastapi.concurrency import run_in_threadpool

    desc = (body.text or "").strip()
    if not desc:
        return fail(400, "text 为空")
    facts = [f"用户描述：{desc}"]
    if body.name_zh:
        facts.append(f"系统判定材质：{body.name_zh}" + (f"（置信度{body.prob:.0%}）" if body.prob else ""))
    if body.bin_zh:
        facts.append(f"系统投放建议：{body.bin_zh}")
    if body.contaminated:
        facts.append("描述中提到污染，系统已按污染规则调整建议")
    if body.evidence:
        facts.append("知识库依据：" + "；".join(body.evidence[:3]))
    prompt = (
        "你是垃圾分类助手。以下是与用户描述相关的系统判定事实，请据此用2~4句话"
        "给普通用户一段友好、口语化的解读：确认结论、解释为什么这样投放、给一个"
        "实用的投放小贴士。只能依据给出的事实，不要编造系统没有的结论。\n"
        + "\n".join(facts)
    )
    t0 = time.time()
    try:
        reply = await run_in_threadpool(lambda: _get_llm().invoke(prompt).content)
    except Exception as exc:
        log.exception("AI 解读失败：%s", exc)
        return fail(500, "AI 解读暂时不可用，请稍后再试")
    return {"code": 200, "msg": "ok",
            "result": {"explain": reply if isinstance(reply, str) else str(reply),
                       "latency_ms": round((time.time() - t0) * 1000, 1)}}


class InterpretQuery(BaseModel):
    text: str = Field(..., description="用户的原始物品描述")


@app.post("/api/v1/agent/interpret")
async def agent_interpret(body: InterpretQuery):
    """口语/品牌描述 → 系统词表可匹配的物品名词（DeepSeek 归一化，无工具）。"""
    from fastapi.concurrency import run_in_threadpool

    desc = (body.text or "").strip()
    if not desc:
        return fail(400, "text 为空")
    prompt = (
        "你是垃圾分类系统的语义归一化器。把用户的物品描述改写为具体的物品名词短语，"
        "去掉品牌、数量、场景等修饰，并尽量点明材质。\n"
        "规则：只输出改写后的物品名词本身，不要任何解释、标点或多余文字；"
        "描述已经是具体物品名词时原样输出；与垃圾无关时原样输出。\n"
        "示例：\n"
        "一瓶农夫山泉 → 塑料矿泉水瓶\n"
        "刚拆完快递的盒子 → 快递纸箱\n"
        "喝剩的可乐罐 → 易拉罐\n"
        "酸奶盒 → 酸奶盒\n"
        "昨晚吃剩的鸡腿骨头 → 骨头\n"
        f"现在处理：{desc} →"
    )
    t0 = time.time()
    try:
        reply = await run_in_threadpool(lambda: _get_llm().invoke(prompt).content)
    except Exception as exc:
        log.exception("AI 归一化失败：%s", exc)
        return fail(500, "AI 理解暂时不可用")
    normalized = (reply if isinstance(reply, str) else str(reply)).strip().strip('"“”').splitlines()[0][:50]
    return {"code": 200, "msg": "ok",
            "result": {"normalized": normalized or desc, "original": desc,
                       "latency_ms": round((time.time() - t0) * 1000, 1)}}


@app.get("/api/v1/agent/health")
def agent_health():
    import requests as _rq
    upstream = "unknown"
    try:
        upstream = "ok" if _rq.get("http://localhost:8000/api/v1/health",
                                   timeout=3).status_code == 200 else "degraded"
    except Exception:
        upstream = "unreachable"
    return {"code": 200, "msg": "ok",
            "result": {"agent": "ready" if _agent else "starting",
                       "upstream_backend": upstream,
                       "note": "upstream=实验四检测/文本服务(8000)"}}
