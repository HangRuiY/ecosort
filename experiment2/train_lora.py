"""实验二：neck 卷积 LoRA + 检测头微调 + AMP。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from functools import partial
from pathlib import Path

import torch
import ultralytics
import yaml
from ultralytics import YOLO

from src.lora_layers import LoRAConv2d
from src.model_factory import (
    LoRADetectionTrainer,
    export_best_model,
)


SCRIPT_DIR = Path(__file__).resolve().parent


def read_yaml(path):
    with Path(path).open("r", encoding="utf-8") as file:
        result = yaml.safe_load(file)
    if not isinstance(result, dict):
        raise ValueError(f"配置必须是字典：{path}")
    return result


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class TrainingMonitor:
    """记录训练显存、优化器更新和 LoRA 参数变化。"""

    def __init__(self):
        self.peak_allocated_mb = 0.0
        self.adapter_updated = False

    def epoch_start(self, trainer):
        if trainer.device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(trainer.device)

    def batch_end(self, trainer):
        if trainer.device.type == "cuda":
            peak = (
                torch.cuda.max_memory_allocated(trainer.device)
                / (1024 ** 2)
            )
            self.peak_allocated_mb = max(
                self.peak_allocated_mb, peak
            )

    def epoch_end(self, trainer):
        adapters = [
            module
            for module in trainer.model.modules()
            if isinstance(module, LoRAConv2d)
        ]

        if not adapters:
            raise RuntimeError("训练模型中的 LoRA 层消失了")

        for module in adapters:
            if not (
                torch.isfinite(module.lora_A.detach()).all().item()
                and torch.isfinite(module.lora_B.detach()).all().item()
            ):
                raise RuntimeError("LoRA 参数出现 NaN 或 Inf")

        max_b = max(
            module.lora_B.detach().abs().max().item()
            for module in adapters
        )

        self.adapter_updated = (
            self.adapter_updated or max_b > 0
        )

        attempts = getattr(trainer, "optimizer_step_attempts", 0)
        successes = getattr(trainer, "optimizer_step_successes", 0)
        skips = getattr(trainer, "optimizer_step_skips", 0)

        print(
            f"\n[LoRA诊断] epoch={trainer.epoch + 1}"
            f" | 累计更新尝试={attempts}"
            f" | 未被AMP跳过={successes}"
            f" | AMP跳过={skips}"
            f" | scale={trainer.scaler.get_scale():.1f}"
            f" | B最大绝对值={max_b:.8e}"
            f" | 已更新={self.adapter_updated}"
        )

        # 给 AMP 初始缩放调整留出时间，
        # 但不允许完全没有更新的模型被当作成功。
        if not self.adapter_updated:
            if trainer.epoch + 1 >= 3:
                raise RuntimeError(
                    "连续3个epoch后LoRA仍未更新。"
                    "请反馈上面的LoRA诊断日志，暂不进行完整训练。"
                )

            print("LoRA暂未更新，继续观察下一轮。")


def main():
    parser = argparse.ArgumentParser(description="EcoSort LoRA 训练")
    parser.add_argument(
        "--config",
        default="configs/lora_amp.yaml",
    )
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = SCRIPT_DIR / config_path
    config_path = config_path.resolve()

    config = read_yaml(config_path)
    config_dir = config_path.parent

    data_path = Path(config["data"])
    if not data_path.is_absolute():
        data_path = config_dir / data_path
    data_path = data_path.resolve()

    if not data_path.is_file():
        raise FileNotFoundError(f"找不到数据配置：{data_path}")
    if not torch.cuda.is_available():
        raise RuntimeError("当前 PyTorch 未检测到 CUDA GPU")

    model_value = str(config["model"])
    model_path = Path(model_value)

    if model_path.is_absolute():
        model_value = str(model_path)
    else:
        # 优先查找项目内已有权重，找不到则由 Ultralytics 下载。
        for candidate in (
            config_dir / model_path,
            SCRIPT_DIR / model_path,
            SCRIPT_DIR.parent / model_path,
        ):
            if candidate.is_file():
                model_value = str(candidate.resolve())
                break

    train_args = dict(config["train"])
    if train_args.get("resume"):
        raise ValueError("当前版本暂不支持 resume")
    if train_args.get("optimizer") != "AdamW":
        raise ValueError("此次对照请保持 optimizer: AdamW")

    device = str(train_args.get("device", 0))
    if not device.isdigit():
        raise ValueError("当前版本请使用单张 GPU，例如 device: 0")

    device_index = int(device)
    if device_index >= torch.cuda.device_count():
        raise ValueError(f"GPU 编号不存在：{device_index}")

    torch.cuda.set_device(device_index)

    project_path = Path(config["run"]["project"])
    if not project_path.is_absolute():
        project_path = config_dir / project_path
    project_path = project_path.resolve()

    run_name = str(config["run"]["name"])

    if args.smoke_test:
        run_name += "_smoke"
        train_args.update({
            "epochs": 3,
            "fraction": 0.02,
            "patience": 3,
            "plots": False,
            "close_mosaic": 0,

            # 仅冒烟测试使用：batch=16 时每个 batch 更新一次。
            # 正式训练仍沿用默认 nbs=64。
            "nbs": 16,
        })

    train_args.update({
        "data": str(data_path),
        "project": str(project_path),
        "name": run_name,
        "exist_ok": bool(config["run"].get("exist_ok", False)),
        "compile": False,
    })

    model = YOLO(model_value)

    # 保留实际使用的预训练文件身份，便于实验追踪。
    base_checkpoint = Path(model.ckpt_path).resolve()
    base_hash = sha256(base_checkpoint)

    monitor = TrainingMonitor()
    model.add_callback("on_train_epoch_start", monitor.epoch_start)
    model.add_callback("on_train_batch_end", monitor.batch_end)
    model.add_callback("on_train_epoch_end", monitor.epoch_end)

    trainer_factory = partial(
        LoRADetectionTrainer,
        lora_config=config["lora"],
    )

    print(f"配置：{config_path}")
    print(f"预训练权重：{base_checkpoint}")
    print(f"数据：{data_path}")
    print(f"GPU：{torch.cuda.get_device_name(device_index)}")
    print(f"LoRA：{config['lora']}")
    print(f"模式：{'冒烟测试' if args.smoke_test else '完整训练'}")

    start = time.perf_counter()
    model.train(trainer=trainer_factory, **train_args)
    duration = time.perf_counter() - start

    trainer = model.trainer
    save_dir = Path(trainer.save_dir).resolve()

    completed_epochs = 0
    if trainer.csv.is_file():
        with trainer.csv.open("r", encoding="utf-8-sig") as file:
            completed_epochs = len(list(csv.DictReader(file)))

    # 只处理本次新生成的 LoRA 结果目录。
    # 原始基线目录完全不变。
    export_info = export_best_model(Path(trainer.best))

    resolved_config = {
        "config_path": str(config_path),
        "data": str(data_path),
        "model": str(base_checkpoint),
        "lora": config["lora"],
        "run": {
            "project": str(project_path),
            "name": save_dir.name,
        },
        "train": train_args,
    }

    with (save_dir / "resolved_config.yaml").open(
        "w", encoding="utf-8"
    ) as file:
        yaml.safe_dump(
            resolved_config,
            file,
            allow_unicode=True,
            sort_keys=False,
        )

    summary = {
        "status": "completed",
        "method": "neck_conv_lora_plus_full_detection_head",
        "smoke_test": args.smoke_test,
        "duration_seconds": duration,
        "duration_minutes": duration / 60,
        "duration_scope": "model.train包含准备、训练和最终验证；不含权重导出",
        "completed_epochs": completed_epochs,
        "save_dir": str(save_dir),
        "base_checkpoint": str(base_checkpoint),
        "base_checkpoint_sha256": base_hash,
        "data_yaml_sha256": sha256(data_path),
        "last_checkpoint": str(trainer.last),
        "lora": config["lora"],
        "adapter_updated": monitor.adapter_updated,
        "optimizer_step_attempts": getattr(
            trainer, "optimizer_step_attempts", 0
        ),
        "optimizer_step_successes": getattr(
            trainer, "optimizer_step_successes", 0
        ),
        "optimizer_step_skips": getattr(
            trainer, "optimizer_step_skips", 0
        ),
        "amp_requested": train_args.get("amp"),
        "amp_enabled": bool(trainer.amp),
        "training_peak_allocated_memory_mb": monitor.peak_allocated_mb,
        "memory_scope": "训练批次阶段PyTorch峰值已分配显存",
        "parameter_report": trainer.parameter_report,
        "metrics": {
            key: float(value)
            for key, value in trainer.metrics.items()
        },
        "config": resolved_config,
        "environment": {
            "torch": str(torch.__version__),
            "cuda": torch.version.cuda,
            "ultralytics": ultralytics.__version__,
            "device": device,
            "gpu_name": torch.cuda.get_device_name(device_index),
        },
        **export_info,
    }

    write_json(save_dir / "train_summary.json", summary)
    write_json(
        save_dir / "environment.json",
        summary["environment"],
    )

    print("\nLoRA 训练完成")
    print(f"结果目录：{save_dir}")
    print(f"训练耗时：{duration / 60:.2f} 分钟")
    print(
        "训练阶段峰值显存："
        f"{monitor.peak_allocated_mb:.2f} MB"
    )
    print(f"适配器已更新：{monitor.adapter_updated}")
    print(f"普通YOLO最佳权重：{export_info['best_checkpoint']}")
    print(f"摘要：{save_dir / 'train_summary.json'}")


if __name__ == "__main__":
    main()