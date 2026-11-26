"""
实验二：YOLO 基线模型训练

功能：
1. 读取 baseline.yaml
2. 加载预训练 YOLO 检测模型
3. 使用实验一生成的数据集进行训练
4. 记录 CUDA、PyTorch、显存和训练时间信息
5. 保存解析后的配置和训练摘要

运行方式：

完整训练：
    python train_baseline.py --config configs/baseline.yaml

先进行小规模冒烟测试：
    python train_baseline.py --config configs/baseline.yaml --smoke-test
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

import torch
import yaml
from ultralytics import YOLO

from src.train_utils import RecordedDetectionTrainer, TrainingRecorder


def load_yaml(path: Path) -> dict[str, Any]:
    """读取 YAML 配置文件。"""
    with path.open("r", encoding="utf-8") as file:
        value = yaml.safe_load(file)

    if not isinstance(value, dict):
        raise ValueError(f"配置文件必须是对象结构：{path}")

    return value


def resolve_existing_path(base_dir: Path, value: str) -> str:
    """
    将相对路径解析为绝对路径。

    如果 value 是模型名称，例如 yolo11n.pt，
    且当前目录中不存在同名文件，则保留原字符串，
    交由 Ultralytics 按模型名称处理。
    """
    path = Path(value)

    if path.is_absolute():
        return str(path)

    candidate = (base_dir / path).resolve()

    if candidate.exists():
        return str(candidate)

    return value


def resolve_required_path(base_dir: Path, value: str, field_name: str) -> str:
    """解析必须存在的路径。"""
    path = Path(value)

    if not path.is_absolute():
        path = (base_dir / path).resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"{field_name} 不存在：{path}\n"
            f"请检查配置文件中的路径：{value}"
        )

    return str(path)


def get_gpu_info() -> dict[str, Any]:
    """收集 CUDA 和 GPU 信息。"""
    result: dict[str, Any] = {
        "cuda_available": bool(torch.cuda.is_available()),
        "torch_version": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "device_count": int(torch.cuda.device_count()),
    }

    if torch.cuda.is_available():
        devices = []

        for index in range(torch.cuda.device_count()):
            properties = torch.cuda.get_device_properties(index)

            devices.append(
                {
                    "index": index,
                    "name": torch.cuda.get_device_name(index),
                    "total_memory_gb": round(
                        properties.total_memory / (1024**3),
                        2,
                    ),
                    "major": properties.major,
                    "minor": properties.minor,
                }
            )

        result["devices"] = devices

    return result


def get_system_info() -> dict[str, Any]:
    """收集基础系统信息。"""
    result = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "python_executable": sys.executable,
    }

    try:
        import psutil

        memory = psutil.virtual_memory()
        result["system_memory_gb"] = round(memory.total / (1024**3), 2)
    except ImportError:
        result["system_memory_gb"] = None

    return result


def write_json(path: Path, value: dict[str, Any]) -> None:
    """写入 UTF-8 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)


def make_json_safe(value: Any) -> Any:
    """将常见的 NumPy/PyTorch 类型转换为可写入 JSON 的类型。"""
    if value is None:
        return None

    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [make_json_safe(item) for item in value]

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def get_training_summary(
    model: YOLO,
    duration_seconds: float,
    config: dict[str, Any],
    save_dir: Path,
) -> dict[str, Any]:
    """收集训练完成后的基本信息。"""
    trainer = getattr(model, "trainer", None)

    metrics = {}
    best_checkpoint = None
    last_checkpoint = None

    if trainer is not None:
        trainer_metrics = getattr(trainer, "metrics", None)

        if trainer_metrics is not None:
            metrics = make_json_safe(trainer_metrics)

        best_value = getattr(trainer, "best", None)
        last_value = getattr(trainer, "last", None)

        if best_value is not None:
            best_checkpoint = str(best_value)

        if last_value is not None:
            last_checkpoint = str(last_value)

    return {
        "status": "completed",
        "duration_seconds": round(duration_seconds, 3),
        "duration_minutes": round(duration_seconds / 60, 3),
        "save_dir": str(save_dir),
        "best_checkpoint": best_checkpoint,
        "last_checkpoint": last_checkpoint,
        "metrics": metrics,
        "config": make_json_safe(config),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def completed_epochs_from_csv(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return max(
            (int(float(row["epoch"])) for raw in csv.DictReader(handle)
             if (row := {key.strip(): value for key, value in raw.items()}).get("epoch")),
            default=0,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="训练实验二 YOLO 基线模型"
    )

    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="训练配置文件路径，例如 configs/baseline.yaml",
    )

    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="只使用少量数据训练 1 个 epoch，用于检查环境和数据是否正常",
    )

    args = parser.parse_args()

    config_path = Path(args.config).resolve()

    if not config_path.is_file():
        raise FileNotFoundError(f"找不到配置文件：{config_path}")

    config_dir = config_path.parent
    config = load_yaml(config_path)

    if "data" not in config:
        raise KeyError("配置文件缺少 data 字段")

    if "model" not in config:
        raise KeyError("配置文件缺少 model 字段")

    data_path = resolve_required_path(
        config_dir,
        str(config["data"]),
        "数据配置文件",
    )

    model_name = resolve_existing_path(
        config_dir,
        str(config["model"]),
    )

    run_config = dict(config.get("run", {}))
    train_config = dict(config.get("train", {}))

    project_value = str(
        run_config.get("project", "../outputs/baseline")
    )
    project_path = Path(project_value)

    if not project_path.is_absolute():
        project_path = (config_dir / project_path).resolve()

    run_name = str(
        run_config.get("name", "yolo11n_baseline_amp")
    )

    exist_ok = bool(run_config.get("exist_ok", False))

    if args.smoke_test:
        run_name = f"{run_name}_smoke"
        train_config["epochs"] = 1
        train_config["fraction"] = 0.02
        train_config["patience"] = 1
        train_config["plots"] = False

    train_args = dict(train_config)
    train_args["data"] = data_path
    train_args["project"] = str(project_path)
    train_args["name"] = run_name
    train_args["exist_ok"] = exist_ok

    print("=" * 72)
    print("实验二 YOLO 基线训练")
    print("=" * 72)
    print(f"配置文件：{config_path}")
    print(f"数据配置：{data_path}")
    print(f"模型：{model_name}")
    print(f"输出目录：{project_path / run_name}")
    print(f"训练参数：{train_args}")
    print("-" * 72)

    gpu_info = get_gpu_info()
    system_info = get_system_info()

    print(json.dumps(gpu_info, ensure_ascii=False, indent=2))

    if not gpu_info["cuda_available"]:
        raise RuntimeError(
            "当前 PyTorch 没有检测到 CUDA GPU。\n"
            "请先确认 PyTorch CUDA 环境，再开始完整训练。"
        )

    dataset_root = Path(data_path).parent
    dataset_summary_path = dataset_root / "summary.json"
    dataset_summary = (
        json.loads(dataset_summary_path.read_text(encoding="utf-8"))
        if dataset_summary_path.is_file() else {}
    )
    fixed_budget = (
        dataset_summary.get("view") in ("no_augmentation", "experiment1_augmentation")
        and not args.smoke_test
    )
    metadata_hashes = {
        name: sha256(dataset_root / name)
        for name in ("data.yaml", "train.json", "summary.json")
        if (dataset_root / name).is_file()
    }

    model = YOLO(model_name)
    base_checkpoint = Path(getattr(model, "ckpt_path", None) or model_name).resolve()
    base_checkpoint_hash = sha256(base_checkpoint) if base_checkpoint.is_file() else None
    recorder = TrainingRecorder(
        expected_batch=int(train_config.get("batch", 16)),
        expected_entries=dataset_summary.get("training_entries"),
        fixed_budget=fixed_budget,
    )
    recorder.attach(model)

    start_time = time.perf_counter()

    model.train(trainer=RecordedDetectionTrainer, **train_args)

    duration_seconds = time.perf_counter() - start_time

    trainer = getattr(model, "trainer", None)

    if trainer is not None and getattr(trainer, "save_dir", None):
        save_dir = Path(trainer.save_dir).resolve()
    else:
        save_dir = (project_path / run_name).resolve()

    save_dir.mkdir(parents=True, exist_ok=True)

    resolved_config = {
        "config_path": str(config_path),
        "data": data_path,
        "model": model_name,
        "run": {
            "project": str(project_path),
            "name": run_name,
            "exist_ok": exist_ok,
        },
        "train": train_config,
    }

    with (save_dir / "resolved_config.yaml").open(
        "w",
        encoding="utf-8",
    ) as file:
        yaml.safe_dump(
            resolved_config,
            file,
            allow_unicode=True,
            sort_keys=False,
        )

    environment = {
        "system": system_info,
        "gpu": gpu_info,
    }

    write_json(save_dir / "environment.json", environment)

    summary = get_training_summary(
        model=model,
        duration_seconds=duration_seconds,
        config=resolved_config,
        save_dir=save_dir,
    )

    completed_epochs = completed_epochs_from_csv(save_dir / "results.csv")
    resources = recorder.finish(trainer, completed_epochs)
    summary.update(resources)
    summary.update({
        "method": "full_finetune",
        "smoke_test": args.smoke_test,
        "amp_requested": bool(train_config.get("amp", True)),
        "duration_scope": "model.train includes setup, training and final validation",
        "base_checkpoint": str(base_checkpoint),
        "base_checkpoint_sha256": base_checkpoint_hash,
        "dataset": {
            "yaml": data_path,
            "yaml_relative_to_experiment2": os.path.relpath(
                data_path, Path(__file__).resolve().parent
            ).replace("\\", "/"),
            "view": dataset_summary.get("view"),
            "summary": dataset_summary,
            "metadata_sha256": metadata_hashes,
        },
    })
    write_json(save_dir / "train_summary.json", summary)

    print("-" * 72)
    print("训练完成")
    print(f"结果目录：{save_dir}")
    print(f"训练耗时：{duration_seconds / 60:.2f} 分钟")
    print(f"摘要文件：{save_dir / 'train_summary.json'}")
    print(f"实际训练轮数：{completed_epochs}")
    print(f"训练峰值已分配显存：{resources['training_peak_allocated_memory_mb']:.2f} MiB")
    if fixed_budget:
        print(f"固定训练预算完成：{resources['fixed_budget_completed']}")
        if not resources["fixed_budget_completed"]:
            print("注意：本次未完整执行固定预算，请检查 epoch_resources.csv，暂不用于正式对照。")


if __name__ == "__main__":
    main()