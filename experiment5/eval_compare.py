"""实验五：微调效果评估（eval_compare.py，云端或本机均可运行）。

用实验一转化的 10 条测试集（未参与微调）对比：
- 基座模型零样本准确率（任务 5.2.1 基线评估）
- LoRA 微调后准确率（任务 5.2.2 微调效果评估）

判定方式：模型回复中出现的第一个十类材质名作为预测类别；
同时统计"投放建议"是否正确（按 meta 里的污染/地区字段计算标准答案）。

用法：
  python eval_compare.py                                  # 只测零样本基线
  python eval_compare.py --adapter outputs/lora_adapter/final
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent
TEST_JSON = ROOT / "data" / "agent_finetune_test.json"

CLASS_NAMES_ZH = ["塑料", "纸及纸板", "金属", "玻璃", "食物残余"]

MATERIAL_RULES = {
    0: "recyclable", 1: "recyclable", 2: "recyclable", 3: "recyclable", 4: "kitchen",
}
BINS = {
    "recyclable": {"general": "可回收物", "shanghai": "可回收物"},
    "kitchen": {"general": "厨余垃圾", "shanghai": "湿垃圾"},
    "hazardous": {"general": "有害垃圾", "shanghai": "有害垃圾"},
    "other": {"general": "其他垃圾", "shanghai": "干垃圾"},
}


def expected_bin(class_id: int, contaminated: bool, region: str) -> str:
    bin_key = MATERIAL_RULES[class_id]
    if contaminated and bin_key == "recyclable":
        bin_key = "other"
    return BINS[bin_key][region]


def predict_material(text: str) -> str | None:
    """从回复中提取材质类别；取最先出现的类别名。"""
    hits = [(text.find(n), n) for n in CLASS_NAMES_ZH if n in text]
    return min(hits)[1] if hits else None


def parse_bin(text: str) -> str | None:
    marker = "投放建议："
    if marker not in text:
        return None
    seg = text.split(marker, 1)[1]
    for name in ["可回收物", "厨余垃圾", "湿垃圾", "有害垃圾", "其他垃圾", "干垃圾"]:
        if seg.startswith(name):
            return name
    return None


@torch.no_grad()
def run_eval(model, tokenizer, records: list[dict], max_new_tokens: int) -> list[dict]:
    results = []
    for r in records:
        msgs = [
            {"role": "system", "content": "你是垃圾分类助手，按指令判断物品材质并给出投放建议。"},
            {"role": "user", "content": f"{r['instruction']}\n物品描述：{r['input']}"},
        ]
        prompt = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        t0 = time.time()
        out = model.generate(**inputs, max_new_tokens=max_new_tokens,
                             do_sample=False, temperature=None)
        reply = tokenizer.decode(out[0][inputs["input_ids"].shape[1]:],
                                 skip_special_tokens=True)
        latency = round(time.time() - t0, 2)

        meta = r["meta"]
        pred = predict_material(reply)
        bin_pred = parse_bin(reply)
        bin_gold = expected_bin(meta["class_id"], meta["contaminated"], meta["region"])
        results.append({
            "input": r["input"],
            "gold": r["meta"]["class_name"],
            "pred": pred,
            "material_ok": pred == meta["class_name"],
            "bin_gold": bin_gold,
            "bin_pred": bin_pred,
            "bin_ok": bin_pred == bin_gold,
            "latency_s": latency,
            "reply": reply[:120],
        })
        flag = "✓" if results[-1]["material_ok"] else "✗"
        print(f"[{flag}] {r['input'][:24]:<26} 金标:{meta['class_name']:<8} 预测:{pred}  {latency}s")
    return results


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    p.add_argument("--adapter", default=None, help="LoRA adapter 目录；不传则只测零样本")
    p.add_argument("--data", default=str(TEST_JSON))
    p.add_argument("--max-new-tokens", type=int, default=64)
    args = p.parse_args()

    records = json.loads(Path(args.data).read_text(encoding="utf-8"))
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype="auto", device_map="auto")

    report: dict = {"model": args.model, "test_size": len(records)}

    print("=== 基座模型零样本 ===")
    zero = run_eval(model, tokenizer, records, args.max_new_tokens)
    report["zero_shot"] = {
        "material_acc": sum(r["material_ok"] for r in zero) / len(zero),
        "bin_acc": sum(r["bin_ok"] for r in zero) / len(zero),
        "avg_latency_s": round(sum(r["latency_s"] for r in zero) / len(zero), 2),
        "details": zero,
    }

    if args.adapter:
        print(f"\n=== LoRA 微调后（{args.adapter}）===")
        model = PeftModel.from_pretrained(model, args.adapter)
        tuned = run_eval(model, tokenizer, records, args.max_new_tokens)
        report["finetuned"] = {
            "adapter": args.adapter,
            "material_acc": sum(r["material_ok"] for r in tuned) / len(tuned),
            "bin_acc": sum(r["bin_ok"] for r in tuned) / len(tuned),
            "avg_latency_s": round(sum(r["latency_s"] for r in tuned) / len(tuned), 2),
            "details": tuned,
        }

    print("\n===== 汇总 =====")
    z, f = report["zero_shot"], report.get("finetuned")
    print(f"零样本：材质准确率 {z['material_acc']:.0%}，建议准确率 {z['bin_acc']:.0%}，"
          f"平均延迟 {z['avg_latency_s']}s")
    if f:
        print(f"微调后：材质准确率 {f['material_acc']:.0%}，建议准确率 {f['bin_acc']:.0%}，"
              f"平均延迟 {f['avg_latency_s']}s")

    out = ROOT / "outputs" / "eval_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"明细已写入 {out}")


if __name__ == "__main__":
    main()
