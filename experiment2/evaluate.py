"""
实验二：统一目标检测评估

默认评估验证集：
    python evaluate.py --run outputs/baseline/yolo11n_baseline_amp

方案确定后评估测试集：
    python evaluate.py --run outputs/baseline/yolo11n_baseline_amp --split test

所有命令行相对路径均相对于本脚本所在目录。
"""

from __future__ import annotations

import argparse
import platform
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import torch
import ultralytics
import yaml
from ultralytics import YOLO
from ultralytics.cfg import DEFAULT_CFG_DICT

from src.metrics import collect_per_class, finite_float, normalize_names
from src.experiment_registry import (
    collect_training_metadata, evaluation_flat_record, read_json,
    register_record, sha256, write_csv, write_json,
)


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent


def resolve_path(value: str) -> Path:
    """相对路径始终基于 evaluate.py 所在目录。"""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = SCRIPT_DIR / path
    return path.resolve()


def read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        result = yaml.safe_load(file)

    if not isinstance(result, dict):
        raise ValueError(f"YAML 内容必须是字典：{path}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="EcoSort 检测模型统一评估")

    parser.add_argument(
        "--run",
        default="outputs/baseline/yolo11n_baseline_amp",
        help="训练结果目录，相对于 evaluate.py",
    )
    parser.add_argument(
        "--data",
        default=None,
        help="数据配置，相对于 evaluate.py；默认沿用新训练摘要，旧记录使用 ../data/split/data.yaml",
    )
    parser.add_argument("--split", choices=["val", "test"], default="val")
    parser.add_argument("--weights", choices=["best", "last"], default="best")
    parser.add_argument("--device", default="0", help="单张GPU编号或 cpu")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--workers", type=int, default=4)

    args = parser.parse_args()

    run_dir = resolve_path(args.run)
    summary_path = run_dir / "train_summary.json"
    training_summary = read_json(summary_path) if summary_path.is_file() else {}
    recorded_data = training_summary.get("dataset", {}).get("yaml_relative_to_experiment2")
    data_path = resolve_path(args.data or recorded_data or "../data/split/data.yaml")
    checkpoint = run_dir / "weights" / f"{args.weights}.pt"

    if not checkpoint.is_file():
        raise FileNotFoundError(f"找不到模型权重：{checkpoint}")
    if not data_path.is_file():
        raise FileNotFoundError(f"找不到数据配置：{data_path}")

    # 此脚本使用实验一的固定目录约定：
    # data.yaml 与 images、labels、train.json 等位于同一目录。
    dataset_root = data_path.parent
    dataset_config = read_yaml(data_path)

    expected_split_path = f"images/{args.split}"
    if dataset_config.get(args.split) != expected_split_path:
        raise ValueError(
            f"当前脚本要求 {args.split}: {expected_split_path}，"
            "请保持实验一的 EcoSort 数据目录结构。"
        )

    image_dir = dataset_root / "images" / args.split
    label_dir = dataset_root / "labels" / args.split
    annotation_path = dataset_root / f"{args.split}.json"

    for path in (image_dir, label_dir):
        if not path.is_dir():
            raise FileNotFoundError(f"找不到数据目录：{path}")

    names = normalize_names(dataset_config["names"])
    if set(names) != set(range(len(names))):
        raise ValueError("类别 ID 必须从 0 开始连续编号")

    cuda_device = None
    if args.device != "cpu":
        if not args.device.isdigit():
            raise ValueError("--device 请填写单张 GPU 编号，例如 0，或 cpu")
        if not torch.cuda.is_available():
            raise RuntimeError("当前 PyTorch 未检测到 CUDA GPU")

        index = int(args.device)
        if index >= torch.cuda.device_count():
            raise ValueError(f"GPU 编号不存在：{index}")

        cuda_device = torch.device(f"cuda:{index}")
        torch.cuda.set_device(cuda_device)

    # 使用唯一目录保存每次评估，避免覆盖已有结果。
    now = datetime.now(timezone(timedelta(hours=8)))
    evaluation_id = (
        f"{args.split}_{args.weights}_"
        f"{now:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    )
    output_dir = run_dir / "evaluation" / evaluation_id
    output_dir.mkdir(parents=True, exist_ok=False)

    # 只在评估输出中生成本机路径配置。
    # 不修改实验一原有 data.yaml，也不依赖旧电脑的绝对路径。
    dataset_config["path"] = dataset_root.as_posix()
    runtime_yaml = output_dir / "dataset_resolved.yaml"
    with runtime_yaml.open("w", encoding="utf-8") as file:
        yaml.safe_dump(
            dataset_config,
            file,
            allow_unicode=True,
            sort_keys=False,
        )

    model = YOLO(str(checkpoint))
    if model.task != "detect":
        raise ValueError(f"当前脚本只支持目标检测，模型任务为：{model.task}")

    if normalize_names(model.names) != names:
        raise ValueError("模型的类别顺序或名称与 data.yaml 不一致")

    # 这是加载后模型的参数量，不代表训练时可训练参数量。
    loaded_parameter_count = sum(
        parameter.numel() for parameter in model.model.parameters()
    )

    val_args = {
        "data": str(runtime_yaml),
        "split": args.split,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": args.device,
        "workers": args.workers,
        "conf": 0.001,
        "iou": 0.7,
        "max_det": 300,
        "rect": True,
        "augment": False,
        "single_cls": False,
        "agnostic_nms": False,
        "classes": None,
        "fraction": 1.0,
        "plots": True,
        "save_json": False,
        "save_txt": False,
        "verbose": True,
        "project": str(output_dir.parent),
        "name": output_dir.name,
        "exist_ok": True,
    }

    # 新版用 quantize 指定计算精度，旧版使用 half。
    # 这里的 quantize=32 表示 FP32 计算，不是 INT8 模型量化。
    if "quantize" in DEFAULT_CFG_DICT:
        val_args["quantize"] = 32
    else:
        val_args["half"] = False

    print(f"模型：{checkpoint}")
    print(f"数据：{data_path}")
    print(f"评估子集：{args.split}")
    print("评估精度：FP32")
    print(f"输出目录：{output_dir}")

    if cuda_device is not None:
        torch.cuda.synchronize(cuda_device)
        torch.cuda.reset_peak_memory_stats(cuda_device)

    start = time.perf_counter()
    metrics = model.val(**val_args)

    if cuda_device is not None:
        torch.cuda.synchronize(cuda_device)

    evaluation_seconds = time.perf_counter() - start

    evaluation_peak_memory_mb = (
        torch.cuda.max_memory_allocated(cuda_device) / (1024 ** 2)
        if cuda_device is not None else None
    )

    precision, recall, map50, map50_95 = (
        finite_float(value)
        for value in metrics.box.mean_results()
    )

    overall = {
        "precision": precision,
        "recall": recall,
        "map50": map50,
        "map50_95": map50_95,
    }
    per_class = collect_per_class(metrics, names)

    # args.yaml 包含训练时实际使用的完整参数。
    args_path = run_dir / "args.yaml"
    training_args = read_yaml(args_path) if args_path.is_file() else {}
    training_metadata = collect_training_metadata(run_dir, training_summary, training_args)

    metadata_hashes = {"data_yaml": sha256(data_path)}
    for key, path in (
        ("split_coco_json", annotation_path),
        ("dataset_summary", dataset_root / "summary.json"),
    ):
        if path.is_file():
            metadata_hashes[key] = sha256(path)

    device_name = (
        torch.cuda.get_device_name(cuda_device)
        if cuda_device is not None else "CPU"
    )

    record = {
        "evaluation_id": evaluation_id,
        "created_at": now.isoformat(),
        "status": "completed",
        "task": "detect",
        "run_dir": str(run_dir),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "dataset_yaml": str(data_path),
        "dataset_root": str(dataset_root),
        "split": args.split,
        # 这些哈希用于追踪配置和标注版本，
        # 不应解释为全部图像文件的内容哈希。
        "dataset_metadata_sha256": metadata_hashes,
        "loaded_model_parameters": loaded_parameter_count,
        "training_args": training_args,
        **training_metadata,
        "evaluation_config": val_args,
        "evaluation_precision": "FP32",
        "evaluation_duration_seconds": evaluation_seconds,
        "evaluation_peak_allocated_memory_mb": evaluation_peak_memory_mb,
        "speed_ms_per_image": {
            key: finite_float(value)
            for key, value in metrics.speed.items()
        },
        "overall": overall,
        "per_class": per_class,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": str(torch.__version__),
            "cuda": torch.version.cuda,
            "ultralytics": ultralytics.__version__,
            "device": args.device,
            "device_name": device_name,
        },
        "metric_notes": {
            "units": "指标使用0到1的数值；乘100转换为百分数",
            "aggregation": "总体P、R和mAP使用Ultralytics的类别平均指标",
            "precision_recall": "P、R、F1使用框架选择的置信度工作点",
            "confidence": "conf=0.001用于保留预测并计算PR曲线和AP",
            "iou": "iou=0.7是NMS阈值，不是AP的匹配阈值",
            "memory": "显存单位为 MiB；训练显存来自训练摘要，评估显存不能替代训练显存；历史缺失值为 null",
        },
    }

    write_json(output_dir / "evaluation_summary.json", record)
    write_csv(output_dir / "per_class_metrics.csv", per_class)

    flat_record = evaluation_flat_record(record, output_dir / "evaluation_summary.json")

    registry_dir = SCRIPT_DIR / "outputs" / "registry"
    registry_name = f"{run_dir.name}_{evaluation_id}"
    register_record(registry_dir, registry_name, record, flat_record)

    print("\n评估完成")
    for name, value in overall.items():
        print(f"{name}: {value:.6f} ({value * 100:.2f}%)")

    print(f"评估耗时：{evaluation_seconds:.2f} 秒")
    print(f"详细结果：{output_dir / 'evaluation_summary.json'}")
    print(f"逐类指标：{output_dir / 'per_class_metrics.csv'}")
    print(f"关联记录：{registry_dir / (registry_name + '.csv')}")


if __name__ == "__main__":
    main()