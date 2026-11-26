"""Training audit for the full-finetuning and augmentation-control runs."""

from __future__ import annotations

import csv
import json
import math
import time
from pathlib import Path

import torch
from ultralytics.models.yolo.detect.train import DetectionTrainer


ONLINE_IMAGE_AUGMENTATIONS = (
    "hsv_h", "hsv_s", "hsv_v", "degrees", "translate", "scale", "shear",
    "perspective", "flipud", "fliplr", "bgr", "mosaic", "mixup", "cutmix", "copy_paste",
)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


class RecordedDetectionTrainer(DetectionTrainer):
    """Keep standard training behavior; count AMP step attempts and skips."""

    def optimizer_step(self):
        before = float(self.scaler.get_scale())
        super().optimizer_step()
        after = float(self.scaler.get_scale())
        self.optimizer_step_attempts = getattr(self, "optimizer_step_attempts", 0) + 1
        if after < before:
            self.optimizer_step_skips = getattr(self, "optimizer_step_skips", 0) + 1
        else:
            self.optimizer_step_successes = getattr(self, "optimizer_step_successes", 0) + 1


class TrainingRecorder:
    def __init__(self, expected_batch, expected_entries=None, fixed_budget=False):
        self.expected_batch = int(expected_batch)
        self.expected_entries = expected_entries
        self.fixed_budget = bool(fixed_budget)
        self.parameter_report = {}
        self.epochs = []
        self.peak_allocated_mb = 0.0
        self.peak_reserved_mb = 0.0
        self.batch_count = 0
        self.epoch_started = None

    def attach(self, model):
        model.add_callback("on_train_start", self.on_train_start)
        model.add_callback("on_train_epoch_start", self.on_epoch_start)
        model.add_callback("on_train_batch_end", self.on_batch_end)
        model.add_callback("on_train_epoch_end", self.on_epoch_end)

    def verify_fixed_budget(self, trainer):
        if not self.fixed_budget:
            return
        if int(trainer.batch_size) != self.expected_batch:
            raise RuntimeError(
                f"Fixed-budget batch changed: expected {self.expected_batch}, got {trainer.batch_size}. "
                "Use the same supported batch size in both control configurations."
            )
        if len(trainer.train_loader.dataset) != self.expected_entries:
            raise RuntimeError("Fixed-budget training entry count changed")
        if trainer.args.patience != 0 or trainer.args.fraction != 1.0:
            raise RuntimeError("Control runs require patience=0 and fraction=1.0")
        if getattr(trainer.args, "time", None) is not None:
            raise RuntimeError("A time limit would change the fixed training budget")
        if trainer.args.rect or trainer.args.multi_scale:
            raise RuntimeError("Control runs require rect=False and multi_scale=0")
        for key in ONLINE_IMAGE_AUGMENTATIONS:
            if float(getattr(trainer.args, key, 0.0)) != 0.0:
                raise RuntimeError(f"Online augmentation must be zero in both controls: {key}")

    def on_train_start(self, trainer):
        self.verify_fixed_budget(trainer)
        model = trainer.model
        parameters = list(model.named_parameters())
        total = sum(p.numel() for _, p in parameters)
        trainable = sum(p.numel() for _, p in parameters if p.requires_grad)
        optimizer_ids = {id(p) for group in trainer.optimizer.param_groups for p in group["params"]}
        if any(id(p) not in optimizer_ids for _, p in parameters if p.requires_grad):
            raise RuntimeError("Some trainable parameters are missing from the optimizer")
        self.parameter_report = {
            "total_parameters": total,
            "trainable_parameters": trainable,
            "frozen_parameters": total - trainable,
            "trainable_ratio": trainable / total,
            "lora_parameters": 0,
            "method": "full_finetune",
            "frozen_names": [name for name, p in parameters if not p.requires_grad],
        }
        write_json(Path(trainer.save_dir) / "parameter_report.json", self.parameter_report)
        write_json(Path(trainer.save_dir) / "training_resources.json", self.snapshot(trainer, "running"))
        print(f"\n[Training audit] trainable={trainable:,}/{total:,}, fixed_budget={self.fixed_budget}")

    def on_epoch_start(self, trainer):
        self.verify_fixed_budget(trainer)
        if trainer.device.type == "cuda":
            torch.cuda.synchronize(trainer.device)
            torch.cuda.reset_peak_memory_stats(trainer.device)
        self.epoch_started = time.perf_counter()
        self.batch_count = 0

    def on_batch_end(self, trainer):
        self.batch_count += 1

    def on_epoch_end(self, trainer):
        if trainer.device.type == "cuda":
            torch.cuda.synchronize(trainer.device)
            peak_allocated = torch.cuda.max_memory_allocated(trainer.device) / (1024 ** 2)
            peak_reserved = torch.cuda.max_memory_reserved(trainer.device) / (1024 ** 2)
        else:
            peak_allocated = peak_reserved = None
        duration = time.perf_counter() - self.epoch_started
        self.peak_allocated_mb = max(self.peak_allocated_mb, peak_allocated or 0.)
        self.peak_reserved_mb = max(self.peak_reserved_mb, peak_reserved or 0.)
        row = {
            "epoch": int(trainer.epoch) + 1,
            "training_seconds_excluding_validation": duration,
            "training_batches_seen": self.batch_count,
            "training_entries": len(trainer.train_loader.dataset),
            "batch_size": int(trainer.batch_size),
            "peak_allocated_mib": peak_allocated,
            "peak_reserved_mib": peak_reserved,
            "optimizer_step_attempts_cumulative": getattr(trainer, "optimizer_step_attempts", 0),
            "optimizer_step_successes_cumulative": getattr(trainer, "optimizer_step_successes", 0),
            "optimizer_step_skips_cumulative": getattr(trainer, "optimizer_step_skips", 0),
            "amp_scale": float(trainer.scaler.get_scale()),
        }
        self.epochs.append(row)
        csv_path = Path(trainer.save_dir) / "epoch_resources.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerows(self.epochs)
        write_json(Path(trainer.save_dir) / "training_resources.json", self.snapshot(trainer, "running"))
        print(
            f"\n[Training audit] epoch={row['epoch']}, train_seconds={duration:.2f}, "
            f"attempts={row['optimizer_step_attempts_cumulative']}, "
            f"AMP_skipped={row['optimizer_step_skips_cumulative']}"
        )

    def snapshot(self, trainer, status):
        cuda = trainer.device.type == "cuda"
        return {
            "status": status,
            "amp_enabled": bool(trainer.amp),
            "training_peak_allocated_memory_mb": self.peak_allocated_mb if cuda else None,
            "training_peak_reserved_memory_mb": self.peak_reserved_mb if cuda else None,
            "memory_units": "MiB (2**20 bytes); legacy field suffix is _mb",
            "memory_scope": "Training epoch only; excludes validation and startup checks",
            "optimizer_step_attempts": getattr(trainer, "optimizer_step_attempts", 0),
            "optimizer_step_successes": getattr(trainer, "optimizer_step_successes", 0),
            "optimizer_step_skips": getattr(trainer, "optimizer_step_skips", 0),
            "parameter_report": self.parameter_report,
            "fixed_budget_checks_enabled": self.fixed_budget,
            "epoch_observations": self.epochs,
        }

    def finish(self, trainer, completed_epochs):
        result = self.snapshot(trainer, "completed")
        result["completed_epochs"] = completed_epochs
        result["fixed_budget_completed"] = (
            completed_epochs == int(trainer.args.epochs)
            and len(self.epochs) == completed_epochs
            and all(
                row["training_batches_seen"] == math.ceil(row["training_entries"] / row["batch_size"])
                for row in self.epochs
            )
        ) if self.fixed_budget else None
        write_json(Path(trainer.save_dir) / "training_resources.json", result)
        return result
