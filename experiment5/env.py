"""实验五：.env 配置加载（无第三方依赖）。"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_env() -> dict[str, str]:
    """读取 experiment5/.env；系统环境变量优先于文件值。"""
    env: dict[str, str] = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    for k in list(env):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def require_key() -> str:
    key = load_env().get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise SystemExit("缺少 DEEPSEEK_API_KEY：请在 experiment5/.env 中配置")
    return key
