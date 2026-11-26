"""LoRA 检测模型、训练器和权重导出。"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import torch
import ultralytics
from torch import nn
from ultralytics import YOLO
from ultralytics.models.yolo.detect.train import DetectionTrainer
from ultralytics.nn.tasks import DetectionModel

from src.lora_layers import (
    LoRAConv2d,
    inject_neck_lora,
    merge_lora_layers,
)


class LoRADetectionModel(DetectionModel):
    def fuse(self, *args, **kwargs):
        """
        推理融合前，先合并 LoRA。

        避免框架融合卷积和 BatchNorm 时遗漏低秩更新。
        此操作针对推理模型；训练过程不调用它。
        """
        merge_lora_layers(self)
        return super().fuse(*args, **kwargs)


class LoRADetectionTrainer(DetectionTrainer):
    def __init__(self, *args, lora_config=None, **kwargs):
        self.lora_config = dict(
            lora_config or {"rank": 8, "alpha": 16}
        )
        self.parameter_report = {}
        super().__init__(*args, **kwargs)

        if self.resume:
            raise ValueError("此版本暂不支持 LoRA 断点续训")
        if self.world_size > 1:
            raise ValueError("此版本使用单张 CUDA GPU")
        if self.args.compile:
            raise ValueError("此版本请保持 compile=False")

    def get_model(self, cfg=None, weights=None, verbose=True):
        model = LoRADetectionModel(
            cfg,
            nc=self.data["nc"],
            ch=self.data.get("channels", 3),
            verbose=verbose,
        )

        # 与普通基线一致，先适配类别并加载预训练权重。
        if hasattr(self, "set_model_names_for_load"):
            model = self.set_model_names_for_load(model)

        if weights is not None:
            model.load(weights)

        rank = int(self.lora_config["rank"])
        alpha = float(self.lora_config["alpha"])

        # 不让额外的 A 初始化消耗训练使用的 CPU 随机数状态。
        with torch.random.fork_rng(devices=[]):
            targets = inject_neck_lora(model, rank, alpha)

        model.lora_metadata = {
            "rank": rank,
            "alpha": alpha,
            "targets": targets,
            "head_index": len(model.model) - 1,
            "strategy": "neck_conv_lora_plus_full_detection_head",
        }

        print(f"\nLoRA 已注入 {len(targets)} 个 neck 卷积")
        for name in targets:
            print(f"  {name}")

        return model

    @staticmethod
    def head_prefix(model) -> str:
        return f"model.{len(model.model) - 1}."

    def apply_training_policy(self, model):
        """只训练 LoRA 参数和检测头，DFL 固定权重除外。"""
        head_prefix = self.head_prefix(model)

        for name, parameter in model.named_parameters():
            is_adapter = name.endswith((".lora_A", ".lora_B"))
            is_head = name.startswith(head_prefix)
            is_dfl = ".dfl." in name

            parameter.requires_grad_(
                is_adapter or (is_head and not is_dfl)
            )

    def build_optimizer(
        self,
        model,
        name="auto",
        lr=0.001,
        momentum=0.9,
        decay=1e-5,
        iterations=1e5,
    ):
        # 框架在 setup 中可能重新启用被冻结的参数。
        # 因此在创建优化器的这一刻重新应用策略。
        self.apply_training_policy(model)

        optimizer = super().build_optimizer(
            model=model,
            name=name,
            lr=lr,
            momentum=momentum,
            decay=decay,
            iterations=iterations,
        )

        # 优化器只保留实际需要训练的参数。
        for group in optimizer.param_groups:
            group["params"] = [
                parameter
                for parameter in group["params"]
                if parameter.requires_grad
            ]

        expected = {
            id(parameter)
            for parameter in model.parameters()
            if parameter.requires_grad
        }
        actual = {
            id(parameter)
            for group in optimizer.param_groups
            for parameter in group["params"]
        }

        if not expected or expected != actual:
            raise RuntimeError("可训练参数与优化器参数不一致")

        total = sum(p.numel() for p in model.parameters())
        trainable = sum(
            p.numel() for p in model.parameters() if p.requires_grad
        )
        adapter = sum(
            p.numel()
            for name, p in model.named_parameters()
            if name.endswith((".lora_A", ".lora_B"))
        )

        self.parameter_report = {
            "total_parameters": total,
            "original_parameters": total - adapter,
            "trainable_parameters": trainable,
            "lora_parameters": adapter,
            "head_trainable_parameters": trainable - adapter,
            "frozen_parameters": total - trainable,
            "trainable_ratio": trainable / total,
            "lora_layers": model.lora_metadata["targets"],
        }

        report_path = Path(self.save_dir) / "parameter_report.json"
        report_path.write_text(
            json.dumps(
                self.parameter_report,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            f"\n可训练参数：{trainable:,} / {total:,}"
            f" ({100 * trainable / total:.2f}%)"
        )
        print(f"其中 LoRA 参数：{adapter:,}")
        print(f"其中检测头参数：{trainable - adapter:,}")

        return optimizer

    def _model_train(self):
        super()._model_train()

        # requires_grad=False 不会自动冻结 BN 运行统计。
        # 每次进入训练模式后，重新冻结 backbone 和 neck 的 BN。
        head_prefix = self.head_prefix(self.model)

        for name, module in self.model.named_modules():
            if (
                isinstance(module, nn.BatchNorm2d)
                and not name.startswith(head_prefix)
            ):
                module.eval()

    def optimizer_step(self):
        """记录 AMP 是否因非有限梯度跳过更新。"""
        scale_before = float(self.scaler.get_scale())

        super().optimizer_step()

        scale_after = float(self.scaler.get_scale())

        self.optimizer_step_attempts = (
            getattr(self, "optimizer_step_attempts", 0) + 1
        )

        # 默认 GradScaler 遇到非有限梯度时跳过更新并降低 scale。
        if scale_after < scale_before:
            self.optimizer_step_skips = (
                getattr(self, "optimizer_step_skips", 0) + 1
            )
        else:
            self.optimizer_step_successes = (
                getattr(self, "optimizer_step_successes", 0) + 1
            )

@torch.no_grad()
def export_best_model(checkpoint: Path) -> dict:
    """
    保存三份产物：
      best_lora.pt：保留 LoRA 结构的最佳模型
      adapter_and_head.pt：适配器及检测头状态
      best.pt：合并后的标准 YOLO 模型

    best.pt 可直接交给现有 evaluate.py。
    """
    checkpoint = Path(checkpoint)
    if not checkpoint.is_file():
        raise FileNotFoundError(f"找不到最佳权重：{checkpoint}")

    backup = checkpoint.with_name("best_lora.pt")
    shutil.copy2(checkpoint, backup)

    adapted = YOLO(str(backup)).model.cpu().float().eval()

    adapters = [
        module
        for module in adapted.modules()
        if isinstance(module, LoRAConv2d)
    ]
    if not adapters:
        raise RuntimeError("最佳模型中没有保留 LoRA 层")

    metadata = copy.deepcopy(adapted.lora_metadata)
    head_prefix = f"model.{metadata['head_index']}."

    adapter_state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in adapted.state_dict().items()
        if (
            name.endswith((".lora_A", ".lora_B"))
            or name.startswith(head_prefix)
        )
    }

    torch.save(
        {
            "metadata": metadata,
            "names": adapted.names,
            "state_dict": adapter_state,
        },
        checkpoint.with_name("adapter_and_head.pt"),
    )

    # 比较合并前后输出，防止导出时丢失低秩更新。
    generator = torch.Generator().manual_seed(20261003)
    sample = torch.rand(1, 3, 128, 128, generator=generator)

    before = adapted(sample)
    before = before[0] if isinstance(before, tuple) else before

    merged_layers = merge_lora_layers(adapted)

    # 构造标准 DetectionModel，不依赖自定义模型类。
    plain = DetectionModel(
        copy.deepcopy(adapted.yaml),
        ch=3,
        nc=len(adapted.names),
        verbose=False,
    )

    # load 会处理预训练分类分支的隐藏通道数。
    plain.load(adapted, verbose=False)
    plain.load_state_dict(adapted.state_dict(), strict=True)
    plain.names = copy.deepcopy(adapted.names)
    plain.args = copy.deepcopy(adapted.args)
    plain.lora_metadata = metadata
    plain.cpu().float().eval()

    after = plain(sample)
    after = after[0] if isinstance(after, tuple) else after

    torch.testing.assert_close(
        after,
        before,
        rtol=1e-4,
        atol=1e-4,
    )

    # 保留 FP32 合并权重，避免再次转 FP16 引入额外舍入。
    plain.requires_grad_(False)

    training_args = (
        vars(plain.args)
        if hasattr(plain.args, "__dict__")
        else dict(plain.args)
    )

    temporary = checkpoint.with_name("best_merged.tmp.pt")
    torch.save(
        {
            "model": plain,
            "ema": None,
            "optimizer": None,
            "epoch": -1,
            "train_args": training_args,
            "version": ultralytics.__version__,
            "lora_metadata": metadata,
        },
        temporary,
    )
    temporary.replace(checkpoint)

    return {
        "best_checkpoint": str(checkpoint),
        "best_lora_checkpoint": str(backup),
        "adapter_and_head": str(
            checkpoint.with_name("adapter_and_head.pt")
        ),
        "merged_layers": merged_layers,
        "merge_output_check_passed": True,
    }