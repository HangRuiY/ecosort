"""循智 EcoSort 后端入口。

    cd experiment4/backend
    uvicorn app.main:app --host 0.0.0.0 --port 8000

接口文档：http://localhost:8000/docs
若 experiment4/frontend/dist 存在（npm run build 之后），同一端口直接提供前端页面。
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__, config
from .detector import get_detector
from .errors import install_handlers
from .proxy_agent import router as agent_proxy_router
from .routers import detect, match, meta, tasks, text
from .text_service import get_kb

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ecosort")


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_detector().load_all()  # 启动时加载并预热实验三模型
    get_kb()
    yield


app = FastAPI(
    title="循智 EcoSort API",
    version=__version__,
    description="多目标垃圾检测服务。模型：实验二 YOLO11n（A 组 best.pt），实验三 TensorRT FP16 / ONNX 加速。"
                "所有接口返回统一格式 {code, result, msg}。",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time"],
)
install_handlers(app)


@app.middleware("http")
async def timing(request: Request, call_next):
    t = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{(time.perf_counter() - t) * 1000:.1f}ms"
    # The entry document selects the hashed JS bundle. Always fetch a fresh copy
    # after an update instead of mixing a cached UI with a newer API.
    if request.url.path in {"/", "/index.html"}:
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


API = "/api/v1"
for r in (meta.router, detect.router, text.router, match.router, tasks.router):
    app.include_router(r, prefix=API)
app.include_router(agent_proxy_router)  # 生产单端口部署：/agent-api/* → 8001

_dist = config.BACKEND_DIR.parent / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
else:
    @app.get("/", include_in_schema=False)
    def root():
        return {"code": 200, "result": {"docs": "/docs", "api": API}, "msg": "EcoSort API 运行中；前端请运行 npm run dev"}
