"""统一异常与返回格式：{"code": 状态码, "result": 数据, "msg": 提示}。"""
from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("ecosort")


def ok(result=None, msg: str = "ok") -> dict:
    return {"code": 200, "result": result, "msg": msg}


class ApiError(Exception):
    status = 500
    kind = "server_error"

    def __init__(self, msg: str, status: int | None = None, detail=None):
        super().__init__(msg)
        self.msg = msg
        self.detail = detail
        if status:
            self.status = status


class InputError(ApiError):
    """输入错误：格式、大小、空文本等。"""
    status, kind = 400, "input_error"


class AuthError(ApiError):
    status, kind = 403, "permission_error"


class NotFoundError(ApiError):
    status, kind = 404, "not_found"


class PayloadTooLarge(ApiError):
    status, kind = 413, "payload_too_large"


class ModelError(ApiError):
    """模型错误：未加载、推理失败。"""
    status, kind = 500, "model_error"


class ServiceUnavailable(ApiError):
    status, kind = 503, "service_unavailable"


def _body(status: int, msg: str, kind: str, detail=None):
    return JSONResponse(status_code=status, content={
        "code": status, "result": {"error": kind, "detail": detail} if detail is not None else {"error": kind}, "msg": msg})


_FIELD_ZH = {"file": "图片文件", "text": "文本", "conf": "置信度阈值", "backend": "推理后端", "files": "图片文件"}


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError):
        return _body(exc.status, exc.msg, exc.kind, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errs = exc.errors()
        first = errs[0] if errs else {}
        field = str(first.get("loc", ["", "参数"])[-1])
        name = _FIELD_ZH.get(field, field)
        msg = f"缺少{name}" if first.get("type") == "missing" else f"{name}不合法：{first.get('msg', '')}"
        return _body(400, msg, "input_error", [{"loc": list(map(str, e.get("loc", []))), "msg": e.get("msg")} for e in errs])

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        msg = {404: "接口路径不存在，请检查 URL 和版本号（/api/v1）", 405: "请求方法不正确"}.get(exc.status_code, str(exc.detail))
        return _body(exc.status_code, msg, "not_found" if exc.status_code == 404 else "http_error")

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.error("未处理异常：%s\n%s", exc, traceback.format_exc())
        return _body(500, "服务器内部错误，请查看后端日志", "server_error")
