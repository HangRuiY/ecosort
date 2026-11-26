"""Shared result IO, training metadata and append-only registry entries."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from .metrics import finite_float

def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)

def write_json(path: Path, value: dict, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w", encoding="utf-8") as file:
        json.dump(
            value,
            file,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )

def write_csv(path: Path, rows: list[dict], *, fieldnames=None, exclusive: bool = False) -> None:
    """UTF-8 BOM，便于在 Excel 中直接打开中文。"""
    if not rows and fieldnames is None:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames if fieldnames is not None else list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def collect_training_metadata(run_dir: Path, summary: dict, training_args: dict) -> dict:
    """Read training measurements; absent historical measurements remain null."""
    parameter_report = summary.get("parameter_report") or {}
    report_path = run_dir / "parameter_report.json"
    if not parameter_report and report_path.is_file():
        parameter_report = read_json(report_path)
    completed_epochs = summary.get("completed_epochs")
    csv_path = run_dir / "results.csv"
    if completed_epochs is None and csv_path.is_file():
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            epochs = [
                int(float(row["epoch"])) for raw in csv.DictReader(handle)
                if (row := {key.strip(): value for key, value in raw.items()}).get("epoch")
            ]
        completed_epochs = max(epochs) if epochs else None
    return {
        "training_method": summary.get("method"),
        "training_duration_seconds": summary.get("duration_seconds"),
        "training_planned_epochs": training_args.get("epochs"),
        "training_completed_epochs": completed_epochs,
        "training_amp_enabled": summary.get("amp_enabled"),
        "training_peak_memory_mb": finite_float(summary.get("training_peak_allocated_memory_mb")),
        "training_peak_reserved_memory_mb": finite_float(summary.get("training_peak_reserved_memory_mb")),
        "training_memory_scope": summary.get("memory_scope"),
        "training_parameter_report": parameter_report,
        "training_lora": summary.get("lora", {}),
        "training_dataset": summary.get("dataset", {}),
        "training_base_checkpoint_sha256": summary.get("base_checkpoint_sha256"),
        "training_optimizer_steps": {
            name: summary.get("optimizer_step_" + name)
            for name in ("attempts", "successes", "skips")
        },
        "training_fixed_budget_completed": summary.get("fixed_budget_completed"),
    }

def evaluation_flat_record(record: dict, summary_path: Path) -> dict:
    """Preserve the established evaluation registry CSV columns."""
    run_dir = Path(record["run_dir"])
    evaluation_id = record["evaluation_id"]
    training_args = record["training_args"]
    overall = record["overall"]
    config = record["evaluation_config"]
    return {
        "evaluation_id": evaluation_id,
        "run_name": run_dir.name,
        "split": record["split"],
        "checkpoint": record["checkpoint"],
        "checkpoint_sha256": record["checkpoint_sha256"],
        "dataset_yaml": record["dataset_yaml"],
        "base_model": training_args.get("model"),
        "training_epochs": training_args.get("epochs"),
        "training_batch": training_args.get("batch"),
        "training_completed_epochs": record["training_completed_epochs"],
        "training_amp_requested": training_args.get("amp"),
        "training_amp": record["training_amp_enabled"],
        "training_method": record["training_method"],
        "training_data_view": record["training_dataset"].get("view"),
        "training_base_checkpoint_sha256": record["training_base_checkpoint_sha256"],
        "trainable_parameters": record["training_parameter_report"].get("trainable_parameters"),
        "total_training_model_parameters": record["training_parameter_report"].get("total_parameters"),
        "lora_parameters": record["training_parameter_report"].get("lora_parameters"),
        "lora_rank": record["training_lora"].get("rank"),
        "lora_alpha": record["training_lora"].get("alpha"),
        "optimizer_step_attempts": record["training_optimizer_steps"]["attempts"],
        "optimizer_step_successes": record["training_optimizer_steps"]["successes"],
        "optimizer_step_skips": record["training_optimizer_steps"]["skips"],
        "fixed_budget_completed": record["training_fixed_budget_completed"],
        "training_seed": training_args.get("seed"),
        "training_seconds": record["training_duration_seconds"],
        "training_peak_memory_mb": record["training_peak_memory_mb"],
        "training_peak_reserved_memory_mb": record["training_peak_reserved_memory_mb"],
        "evaluation_imgsz": config["imgsz"],
        "evaluation_batch": config["batch"],
        "evaluation_precision": "FP32",
        "evaluation_seconds": record["evaluation_duration_seconds"],
        "evaluation_peak_allocated_memory_mb": record["evaluation_peak_allocated_memory_mb"],
        **overall,
        "evaluation_summary": str(summary_path),
    }

def register_record(registry_dir: Path, record_id: str, record: dict, flat_record: dict):
    """Create an independent JSON/CSV pair; never replace an existing record."""
    if not record_id or Path(record_id).name != record_id or record_id in (".", ".."):
        raise ValueError("Registry ID must be a single filename component")
    registry_dir = Path(registry_dir)
    registry_dir.mkdir(parents=True, exist_ok=True)
    json_path = registry_dir / f"{record_id}.json"
    csv_path = registry_dir / f"{record_id}.csv"
    if json_path.exists() or csv_path.exists():
        raise FileExistsError(f"Registry entry already exists: {record_id}")
    write_json(json_path, record, exclusive=True)
    write_csv(csv_path, [flat_record], exclusive=True)
    return json_path, csv_path
