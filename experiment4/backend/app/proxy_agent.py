"""把 /agent-api/* 转发到本机 Agent 服务（8001）。

生产部署没有 Vite 代理：前端 dist 由本服务托管在 8000，
浏览器请求 /agent-api/api/v1/agent/* 时由此转发到 127.0.0.1:8001 的同名路径，
实现单端口部署（8000 对外，8001 仅本机）。开发环境仍走 Vite 代理，互不影响。
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

log = logging.getLogger("ecosort")
router = APIRouter(tags=["Agent代理"], include_in_schema=False)

_TARGET = "http://127.0.0.1:8001"
# 异步客户端：转发时不阻塞本服务的事件循环（同步客户端会把 8000 整个卡住）
_CLIENT = httpx.AsyncClient(timeout=180)
_HOP_HEADERS = {"host", "content-length", "connection", "accept-encoding", "transfer-encoding"}


@router.api_route("/agent-api/{path:path}", methods=["GET", "POST"])
async def proxy_agent(path: str, request: Request):
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _HOP_HEADERS}
    try:
        resp = await _CLIENT.request(request.method, f"{_TARGET}/{path}",
                                     content=body, headers=headers)
    except Exception as exc:
        log.warning("Agent 服务转发失败：%s", exc)
        return Response(
            content='{"code":503,"result":{},"msg":"助手服务暂时不可用，请稍后再试"}',
            status_code=503, media_type="application/json")
    filtered = {k: v for k, v in resp.headers.items() if k.lower() not in _HOP_HEADERS}
    return Response(content=resp.content, status_code=resp.status_code,
                    headers=filtered, media_type=resp.headers.get("content-type"))
