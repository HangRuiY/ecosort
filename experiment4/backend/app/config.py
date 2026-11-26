"""集中配置。所有路径都相对项目根目录推导，可用环境变量覆盖。"""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(os.getenv("ECOSORT_ROOT", BACKEND_DIR.parents[1])).resolve()
EXP1_DIR = PROJECT_ROOT / "experiment1"
EXP3_DIR = PROJECT_ROOT / "experiment3"
# experiment4 单独拷贝/上传时使用的内置副本（模型、知识库、示例图、experiment1.py）
ASSETS_DIR = BACKEND_DIR / "assets"
STORAGE_DIR = Path(os.getenv("ECOSORT_STORAGE", BACKEND_DIR / "storage")).resolve()

# Ultralytics 的设置与缓存放在 backend 目录，避免写入实验一至三。
for _d in (".ultralytics",):
    (BACKEND_DIR / _d).mkdir(exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(BACKEND_DIR / ".ultralytics"))
os.environ.setdefault("YOLO_OFFLINE", "1")
os.environ.setdefault("YOLO_AUTOINSTALL", "false")


def _first_existing(*paths: Path) -> Path:
    for p in paths:
        if p.is_file():
            return p
    return paths[0]


def _first_dir(*paths: Path) -> Path:
    for p in paths:
        if p.is_dir():
            return p
    return paths[0]


# 优先使用完整项目中的原始文件；只有 experiment4 时使用 assets 中的副本
SUMMARY_JSON = _first_existing(PROJECT_ROOT / "data" / "split" / "summary.json", ASSETS_DIR / "knowledge.json")
EXP1_SCRIPT = _first_existing(EXP1_DIR / "experiment1.py", ASSETS_DIR / "experiment1.py")


# 三种推理后端，均来自实验二 A 组 best.pt 及实验三的转换结果。
# TensorRT 引擎与显卡架构绑定：优先使用本机用 scripts/build_engine.py 重建的引擎。
MODEL_PATHS: dict[str, Path] = {
    "tensorrt_fp16": Path(os.getenv("ECOSORT_ENGINE", "")) if os.getenv("ECOSORT_ENGINE") else _first_existing(
        BACKEND_DIR / "models" / "baseline.engine", EXP3_DIR / "models" / "baseline.engine"),
    "onnx_fp32": Path(os.getenv("ECOSORT_ONNX", "")) if os.getenv("ECOSORT_ONNX") else _first_existing(
        EXP3_DIR / "models" / "baseline.onnx", ASSETS_DIR / "baseline.onnx"),
    "pytorch_fp32": Path(os.getenv("ECOSORT_PT", "")) if os.getenv("ECOSORT_PT") else _first_existing(
        EXP3_DIR / "models" / "baseline.pt", ASSETS_DIR / "baseline.pt"),
}
BACKEND_LABELS = {"tensorrt_fp16": "TensorRT FP16", "onnx_fp32": "ONNX Runtime", "pytorch_fp32": "PyTorch FP32"}
BACKEND_ORDER = [b.strip() for b in os.getenv("ECOSORT_BACKENDS", "tensorrt_fp16,pytorch_fp32,onnx_fp32").split(",") if b.strip()]
DEFAULT_BACKEND = os.getenv("ECOSORT_DEFAULT_BACKEND", "tensorrt_fp16")
DEVICE = os.getenv("ECOSORT_DEVICE", "auto")  # auto / cpu / 0

# 与实验三统一的推理参数
IMG_SIZE = 640
NMS_IOU = 0.7
MAX_DET = 300
DEFAULT_CONF = 0.25

# 输入限制
MAX_UPLOAD_MB = float(os.getenv("ECOSORT_MAX_UPLOAD_MB", "10"))
MAX_TASK_FILE_MB = float(os.getenv("ECOSORT_MAX_TASK_FILE_MB", "30"))
MAX_BATCH_FILES = int(os.getenv("ECOSORT_MAX_BATCH", "64"))
MAX_TEXT_LEN = 300
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png"}

# 示例图片（v4权重实测验证过的五类样例，每类一张）
SAMPLE_DIR = Path(os.getenv("ECOSORT_SAMPLE_DIR", "")) if os.getenv("ECOSORT_SAMPLE_DIR") else _first_dir(
    ASSETS_DIR / "samples", EXP3_DIR / "data" / "images" / "val")
SAMPLE_IDS = ["taco_011368", "taco_ea9381dbc1515bddb3", "taco_e688938a3563e96ed6", "taco_c523abee7055731f00"]

# 跨域：开发环境允许本机前端；生产环境用 ECOSORT_CORS 指定域名
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "ECOSORT_CORS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080").split(",") if o.strip()]

# 可选的简单访问密钥；设置后所有 /api/v1 写操作需带 X-API-Key
API_KEY = os.getenv("ECOSORT_API_KEY", "")

# 异步任务：auto=有 Redis 且有 Celery worker 时用 Celery，否则用进程内线程池
TASK_MODE = os.getenv("ECOSORT_TASK_MODE", "auto")
REDIS_URL = os.getenv("ECOSORT_REDIS_URL", "redis://localhost:6379/0")
