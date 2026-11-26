"""模型加载与推理（实验三优化模型的服务化封装）。

三种后端共享同一份实验二 A 组权重：
- tensorrt_fp16：实验三导出的 TensorRT FP16 引擎（与显卡架构绑定，换机器需重建）
- onnx_fp32：实验三导出的 ONNX 计算图，ONNX Runtime 执行
- pytorch_fp32：原始 best.pt
启动时逐个加载并预热，加载失败的后端记录原因后跳过，请求会自动回退到可用后端。
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

import numpy as np

from . import config
from .errors import ModelError
from .reuse import CLASS_KEYS

log = logging.getLogger("ecosort")


def _torch():
    import torch
    return torch


def resolve_device() -> str:
    if config.DEVICE != "auto":
        return config.DEVICE
    try:
        return "0" if _torch().cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def precision_args(half: bool) -> dict:
    """与实验三 run_experiment.precision_args 相同：兼容新旧 Ultralytics 的半精度参数名。"""
    from ultralytics.cfg import DEFAULT_CFG_DICT
    return {"quantize": 16 if half else 32} if "quantize" in DEFAULT_CFG_DICT else {"half": half}


@dataclass
class BackendState:
    name: str
    path: str
    available: bool = False
    error: str | None = None
    load_ms: float | None = None
    warmup_ms: float | None = None
    model: object = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def public(self):
        return {"name": self.name, "label": config.BACKEND_LABELS.get(self.name, self.name), "path": self.path,
                "available": self.available, "error": self.error,
                "load_ms": self.load_ms, "warmup_ms": self.warmup_ms}


class Detector:
    def __init__(self):
        self.device = resolve_device()
        self.backends: dict[str, BackendState] = {}
        self._loaded = False
        self._load_lock = threading.Lock()

    # ---------- 加载 ----------
    def load_all(self):
        with self._load_lock:
            if self._loaded:
                return
            for name in config.BACKEND_ORDER:
                path = config.MODEL_PATHS.get(name)
                st = BackendState(name=name, path=str(path))
                self.backends[name] = st
                if path is None or not path.is_file():
                    st.error = "模型文件不存在"
                    continue
                if name == "tensorrt_fp16" and self.device == "cpu":
                    st.error = "TensorRT 需要 NVIDIA GPU（当前为 CPU）"
                    continue
                self._load(st)
            self._loaded = True
            ok = [n for n, s in self.backends.items() if s.available]
            log.info("推理设备 %s；可用后端：%s", self.device, ok or "无")

    def _load(self, st: BackendState):
        from ultralytics import YOLO
        t0 = time.perf_counter()
        try:
            model = YOLO(st.path, task="detect")
            names = {int(k): v for k, v in model.names.items()} if isinstance(model.names, dict) else {}
            st.load_ms = round((time.perf_counter() - t0) * 1000, 1)
            st.model = model
            t1 = time.perf_counter()
            dummy = np.full((config.IMG_SIZE, config.IMG_SIZE, 3), 114, np.uint8)
            for _ in range(2):
                self._raw_predict(st, [dummy], conf=0.25)
            st.warmup_ms = round((time.perf_counter() - t1) * 1000, 1)
            # 引擎/ONNX 的 names 可能在首次推理后才可读，这里复查类别顺序
            names = {int(k): v for k, v in model.names.items()}
            if [names.get(i) for i in range(len(CLASS_KEYS))] != CLASS_KEYS:
                raise ValueError(f"类别映射与 EcoSort 五类不一致：{names}")
            st.available = True
        except Exception as exc:
            st.model = None
            msg = str(exc).strip().splitlines()[0][:200] if str(exc).strip() else exc.__class__.__name__
            if st.name == "tensorrt_fp16":
                msg += "（引擎可能由其他显卡/TensorRT 版本构建，请运行 scripts/build_engine.py 在本机重建）"
            st.error = msg
            log.warning("后端 %s 加载失败：%s", st.name, msg)

    # ---------- 推理 ----------
    def available(self) -> list[str]:
        return [n for n, s in self.backends.items() if s.available]

    def pick(self, requested: str | None) -> tuple[str, str | None]:
        avail = self.available()
        if not avail:
            raise ModelError("没有可用的推理模型，请检查 experiment3/models 下的权重文件与依赖安装")
        want = requested or config.DEFAULT_BACKEND
        if want in avail:
            return want, None
        fallback = avail[0]
        reason = self.backends.get(want).error if want in self.backends else "未知后端"
        return fallback, f"{config.BACKEND_LABELS.get(want, want)} 不可用（{reason}），已改用 {config.BACKEND_LABELS[fallback]}"

    def _raw_predict(self, st: BackendState, images: list[np.ndarray], conf: float):
        return st.model.predict(source=images, imgsz=config.IMG_SIZE, batch=len(images), device=self.device,
                                conf=conf, iou=config.NMS_IOU, max_det=config.MAX_DET, verbose=False,
                                **precision_args(st.name == "tensorrt_fp16"))

    def predict(self, images: list[np.ndarray], backend: str, conf: float):
        st = self.backends[backend]
        try:
            with st.lock:  # Ultralytics 模型对象非线程安全，同一后端串行推理
                t0 = time.perf_counter()
                results = self._raw_predict(st, images, conf)
                wall = (time.perf_counter() - t0) * 1000
        except Exception as exc:
            log.exception("推理失败")
            raise ModelError(f"模型推理失败：{exc.__class__.__name__}")
        out = []
        for r in results:
            boxes = r.boxes
            xyxy = boxes.xyxy.cpu().numpy().tolist() if len(boxes) else []
            cls = boxes.cls.cpu().numpy().astype(int).tolist() if len(boxes) else []
            scores = boxes.conf.cpu().numpy().tolist() if len(boxes) else []
            dets = [{"class_id": c, "confidence": float(s), "xyxy": b} for b, c, s in zip(xyxy, cls, scores)]
            dets.sort(key=lambda d: -d["confidence"])
            speed = {k: round(float(v), 3) for k, v in (r.speed or {}).items()}
            out.append((dets, speed))
        return out, round(wall, 3)

    def health(self):
        info = {"device": self.device, "cuda": False, "gpu": None}
        try:
            torch = _torch()
            info["cuda"] = bool(torch.cuda.is_available())
            if info["cuda"]:
                info["gpu"] = torch.cuda.get_device_name(0)
        except Exception:
            pass
        info["backends"] = [s.public() for s in self.backends.values()]
        info["default_backend"] = config.DEFAULT_BACKEND
        return info


_detector: Detector | None = None


def get_detector() -> Detector:
    global _detector
    if _detector is None:
        _detector = Detector()
    return _detector
