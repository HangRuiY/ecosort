"""在本机 GPU 上重建 TensorRT FP16 引擎。

实验三的 baseline.engine 是在 RTX 4070 SUPER + TensorRT 10.13 上构建的，TensorRT 引擎与显卡架构、
TensorRT 版本绑定，换到其他显卡（例如 RTX 5070 Laptop）后无法反序列化。
本脚本把实验二权重复制到 backend/models/ 后导出，不会改动 experiment3 中的任何文件。

    cd experiment4/backend
    python scripts/build_engine.py            # 约 5-12 分钟
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config  # noqa: E402  (设置 Ultralytics 缓存目录)
from app.detector import precision_args  # noqa: E402


def main():
    import torch
    from ultralytics import YOLO
    if not torch.cuda.is_available():
        sys.exit("需要 CUDA 版 PyTorch 和 NVIDIA GPU；当前 torch.cuda.is_available() 为 False")
    src = config.MODEL_PATHS["pytorch_fp32"]
    out_dir = config.BACKEND_DIR / "models"
    out_dir.mkdir(exist_ok=True)
    pt = out_dir / "baseline.pt"
    shutil.copy2(src, pt)
    gpu = torch.cuda.get_device_name(0)
    print(f"GPU: {gpu}\n从 {src} 导出 TensorRT FP16 引擎……")
    t0 = time.perf_counter()
    engine = YOLO(str(pt)).export(format="engine", imgsz=640, batch=32, dynamic=True, device=0, workspace=4,
                                  simplify=False, nms=False, **precision_args(True))
    seconds = time.perf_counter() - t0

    sample = config.SAMPLE_DIR / "000005.png"
    check = {}
    if sample.is_file():
        for name, path in (("pytorch_fp32", pt), ("tensorrt_fp16", engine)):
            r = YOLO(str(path), task="detect").predict(str(sample), imgsz=640, conf=0.25, iou=0.7, device=0,
                                                        verbose=False, **precision_args(name == "tensorrt_fp16"))[0]
            check[name] = [[int(c), round(float(s), 4)] for c, s in zip(r.boxes.cls, r.boxes.conf)]
    import tensorrt
    record = {"gpu": gpu, "tensorrt": tensorrt.__version__, "torch": torch.__version__, "engine": str(engine),
              "seconds": round(seconds, 1), "batch_profile_max": 32, "sample_check": check}
    (out_dir / "engine_build.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    print("完成。重启后端后 /api/v1/health 中 tensorrt_fp16 应为 available。")


if __name__ == "__main__":
    main()



