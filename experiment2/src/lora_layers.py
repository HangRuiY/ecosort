"""用于 YOLO neck 的 1×1 卷积 LoRA。"""

from __future__ import annotations

import copy
import math

import torch
from torch import nn
from torch.nn import functional as F


class LoRAConv2d(nn.Module):
    """
    对普通 1×1 卷积添加低秩更新。

    effective_weight = W0 + (alpha / rank) * B @ A

    原始权重的冻结规则由训练器统一设置。
    """

    def __init__(self, base: nn.Conv2d, rank: int, alpha: float):
        super().__init__()

        if base.kernel_size != (1, 1) or base.groups != 1:
            raise ValueError("此实现仅支持 groups=1 的 1×1 卷积")
        if base.padding_mode != "zeros":
            raise ValueError("此实现要求 padding_mode=zeros")
        if rank <= 0 or alpha <= 0:
            raise ValueError("rank 和 alpha 必须大于 0")
        if rank >= min(base.in_channels, base.out_channels):
            raise ValueError("rank 必须小于输入和输出通道数")

        self.base = base
        self.rank = int(rank)
        self.alpha = float(alpha)
        self.scaling = self.alpha / self.rank

        self.lora_A = nn.Parameter(
            torch.empty(
                self.rank,
                base.in_channels,
                device=base.weight.device,
                dtype=base.weight.dtype,
            )
        )
        self.lora_B = nn.Parameter(
            torch.zeros(
                base.out_channels,
                self.rank,
                device=base.weight.device,
                dtype=base.weight.dtype,
            )
        )

        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))

    def effective_weight(self):
        # 低秩矩阵乘法使用 FP32，减少 AMP 下的梯度溢出风险。
        # 外部卷积仍按训练器的 AMP 设置执行。
        with torch.autocast(
                device_type=self.base.weight.device.type,
                enabled=False,
        ):
            delta = (
                    self.lora_B.float() @ self.lora_A.float()
            ).reshape_as(self.base.weight)

            weight = (
                    self.base.weight.float()
                    + self.scaling * delta
            )

        return weight.to(dtype=self.base.weight.dtype)

    def forward(self, x):
        return F.conv2d(
            x,
            self.effective_weight(),
            self.base.bias,
            self.base.stride,
            self.base.padding,
            self.base.dilation,
            self.base.groups,
        )

    @torch.no_grad()
    def to_plain_conv(self) -> nn.Conv2d:
        """将低秩更新合并到普通卷积，用于推理和导出。"""
        conv = copy.deepcopy(self.base)
        conv.weight.copy_(self.effective_weight())
        conv.requires_grad_(False)
        return conv


def inject_neck_lora(model, rank: int, alpha: float) -> list[str]:
    """只替换 neck 中符合条件的 1×1 卷积。"""
    backbone_end = len(model.yaml["backbone"])
    head_index = len(model.model) - 1
    targets = []

    for index in range(backbone_end, head_index):
        layer = model.model[index]

        for local_name, module in list(layer.named_modules()):
            if not isinstance(module, nn.Conv2d):
                continue
            if module.kernel_size != (1, 1) or module.groups != 1:
                continue
            if module.padding_mode != "zeros":
                continue
            if rank >= min(module.in_channels, module.out_channels):
                continue

            # 只选低秩参数量小于原始权重参数量的层。
            adapter_parameters = rank * (
                module.in_channels + module.out_channels
            )
            if adapter_parameters >= module.weight.numel():
                continue

            full_name = f"model.{index}"
            if local_name:
                full_name += f".{local_name}"

            parent_name, child_name = full_name.rsplit(".", 1)
            parent = model.get_submodule(parent_name)

            setattr(
                parent,
                child_name,
                LoRAConv2d(module, rank=rank, alpha=alpha),
            )
            targets.append(full_name)

    if not targets:
        raise RuntimeError("没有找到可注入 LoRA 的 neck 卷积")

    return targets


def merge_lora_layers(module: nn.Module) -> int:
    """递归将 LoRA 卷积替换为普通卷积。"""
    count = 0

    for name, child in list(module.named_children()):
        if isinstance(child, LoRAConv2d):
            setattr(module, name, child.to_plain_conv())
            count += 1
        else:
            count += merge_lora_layers(child)

    return count