from __future__ import annotations

from fastapi import Header

from . import config
from .errors import AuthError


def require_key(x_api_key: str | None = Header(default=None, description="设置 ECOSORT_API_KEY 后必填")):
    if config.API_KEY and x_api_key != config.API_KEY:
        raise AuthError("缺少或错误的 X-API-Key，无权调用此接口")
