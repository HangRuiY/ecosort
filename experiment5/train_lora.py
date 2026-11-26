"""实验五：基座模型 LoRA 参数高效微调（train_lora.py，在云 GPU 服务器上运行）。

与实验二 LoRA 的复用关系：
- 实验二（configs/lora_amp.yaml）：rank=8、alpha=16，作用于 YOLO neck 卷积；
- 本实验沿用 rank=8、alpha=16，目标层适配为大模型注意力投影
  （q_proj/k_proj/v_proj/o_proj），体现"同参数、异结构"的参数高效微调；
- 量化策略复用实验三思路：bitsandbytes 4-bit(NF4) 加载基座 + 梯度累积 8 步，
  控制显存占用，避免 OOM。

用法：
  pip install "transformers>=4.40" peft datasets accelerate trl bitsandbytes modelscope
  python train_lora.py                          # 默认 Qwen2.5-1.5B-Instruct
  python train_lora.py --model Qwen/Qwen2.5-0.5B-Instruct

输出：
  outputs/lora_adapter/      LoRA 权重（下载回本机）
  outputs/train_log.json     训练日志（loss 曲线，写报告用）
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

ROOT = Path(__file__).resolve().parent
DATA_JSON = ROOT / "data" / "agent_finetune_data.json"
OUT_DIR = ROOT / "outputs"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    p.add_argument("--data", default=str(DATA_JSON))
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch", type=int, default=2, help="单卡 batch，配合梯度累积 8")
    p.add_argument("--grad-accum", type=int, default=8, help="梯度累积步数（任务书要求 8）")
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--rank", type=int, default=8, help="LoRA 秩（复用实验二）")
    p.add_argument("--alpha", type=int, default=16, help="LoRA 缩放（复用实验二）")
    p.add_argument("--max-len", type=int, default=256)
    p.add_argument("--no-quant", action="store_true",
                   help="不用 4-bit 量化（Windows 下 bitsandbytes 安装/运行失败时的后备）")
    return p.parse_args()


def load_dataset(path: str, tokenizer) -> Dataset:
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    texts = []
    for r in records:
        msgs = [
            {"role": "system", "content": "你是垃圾分类助手，按指令判断物品材质并给出投放建议。"},
            {"role": "user", "content": f"{r['instruction']}\n物品描述：{r['input']}"},
            {"role": "assistant", "content": r["output"]},
        ]
        texts.append(tokenizer.apply_chat_template(msgs, tokenize=False))
    return Dataset.from_dict({"text": texts})


def main() -> None:
    args = parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    train_ds = load_dataset(args.data, tokenizer)
    print(f"模型：{args.model}；训练样本：{len(train_ds)}")

    # 实验3量化思路：4-bit NF4 加载控制显存；--no-quant 时用 bf16（后备方案）
    if args.no_quant:
        model = AutoModelForCausalLM.from_pretrained(
            args.model, torch_dtype=torch.bfloat16, device_map="auto"
        )
        quant_desc = "bf16（未量化，后备模式）"
    else:
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        model = AutoModelForCausalLM.from_pretrained(
            args.model, quantization_config=bnb, device_map="auto"
        )
        model = prepare_model_for_kbit_training(model)
        quant_desc = "4-bit NF4"
    print(f"加载方式：{quant_desc}")

    # 复用实验二的 rank/alpha，目标层换成大模型注意力投影
    lora = LoraConfig(
        r=args.rank,
        lora_alpha=args.alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    cfg_kwargs = dict(
        output_dir=str(OUT_DIR / "lora_adapter"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        logging_steps=1,
        save_strategy="no",
        bf16=True,
        max_length=args.max_len,
        dataset_text_field="text",
        packing=False,
        report_to=[],
    )
    try:  # 兼容不同版本 TRL 的参数名（旧版叫 max_seq_length）
        cfg = SFTConfig(**cfg_kwargs)
    except TypeError:
        cfg_kwargs["max_seq_length"] = cfg_kwargs.pop("max_length")
        cfg = SFTConfig(**cfg_kwargs)

    trainer = SFTTrainer(model=model, train_dataset=train_ds, args=cfg, tokenizer=tokenizer)
    trainer.train()

    adapter_dir = OUT_DIR / "lora_adapter" / "final"
    trainer.save_model(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))

    history = trainer.state.log_history
    log = {
        "model": args.model,
        "lora": {"rank": args.rank, "alpha": args.alpha,
                 "target_modules": lora.target_modules},
        "quantization": f"{quant_desc} + 梯度累积{args.grad_accum}步",
        "epochs": args.epochs,
        "samples": len(train_ds),
        "train_seconds": round(time.time() - t0, 1),
        "loss_curve": [{"step": h.get("step"), "loss": h.get("loss")}
                       for h in history if "loss" in h],
    }
    (OUT_DIR / "train_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成：adapter 在 {adapter_dir}；日志在 {OUT_DIR / 'train_log.json'}")


if __name__ == "__main__":
    main()
