"""实验五：构建大模型微调指令数据集（make_finetune_data.py）。

任务书要求"从实验 1 的 text_data.json 抽取 100 条文本"，但本项目实验 1 的文本是
21 条知识库记录（11 条 TACO 英文文档 + 10 条中文指引，见 data/split/summary.json），
属于文档型知识库而非分类数据集，无法直接抽取。因此数据方案做如下本地化适配：

- 任务：五类材质分类（塑料/纸及纸板/金属/玻璃/食物残余，与实验二新模型的
  data.yaml 类别顺序、实验四 /text 接口完全对齐）；
- 种子：实验四 text_service.py 的 LEXICON 关键词表（与线上判断同一词表）；
- 生成：中文物品描述 × 句式模板 × 污染/地区变体；输出标签复刻 advice.py 规则
 （含"沾污可回收物改投其他垃圾"逻辑），保证与实验四后端判定一致；
- 规模：每类 20 条训练 + 1 条测试 = 100 条训练（agent_finetune_data.json）
        + 5 条测试（agent_finetune_test.json，未参与微调，用于零样本/微调后对比）。

运行：python make_finetune_data.py
输出：experiment5/data/agent_finetune_data.json      （100 条训练集）
      experiment5/data/agent_finetune_test.json      （10 条测试集）
"""
from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 20261108
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data"

# 实验二交接（五类体系）：与新版 YOLO11s 检测模型的 data.yaml 类别顺序一致
CLASS_NAMES_ZH = ["塑料", "纸及纸板", "金属", "玻璃", "食物残余"]

# 与实验四 advice.py 的五类 MATERIAL_RULES 一致：class_id -> (默认去向, 是否需核查, 说明)
MATERIAL_RULES = {
    0: ("recyclable", False, "塑料容器/包装清空、冲洗后可回收；沾污塑料投其他垃圾"),
    1: ("recyclable", False, "纸及纸板保持干燥清洁可回收；油污纸张投其他垃圾"),
    2: ("recyclable", False, "金属罐冲洗后可回收"),
    3: ("recyclable", False, "玻璃轻放，尖锐边角包裹后投放"),
    4: ("kitchen", False, "食物残余与包装分离后投放"),
}

BINS = {
    "recyclable": {"general": "可回收物", "shanghai": "可回收物"},
    "kitchen": {"general": "厨余垃圾", "shanghai": "湿垃圾"},
    "hazardous": {"general": "有害垃圾", "shanghai": "有害垃圾"},
    "other": {"general": "其他垃圾", "shanghai": "干垃圾"},
}

# 来自实验四 text_service.py 的五类 LEXICON（仅保留中文词，作为描述生成的种子）
LEXICON: dict[int, list[str]] = {
    0: ["塑料瓶", "矿泉水瓶", "饮料瓶", "洗洁精瓶", "洗发水瓶", "塑料盒", "外卖餐盒", "塑料杯", "瓶盖", "塑料桶",
        "塑料盆", "衣架", "塑料袋", "保鲜膜", "快递袋", "气泡膜", "垃圾袋", "泡沫塑料", "碎塑料", "薯片袋",
        "零食袋", "铝箔袋"],
    1: ["纸箱", "纸盒", "快递盒", "报纸", "旧书", "纸张", "杂志", "纸板", "纸袋", "传单", "纸巾", "卫生纸",
        "餐巾纸", "牛奶盒", "利乐包", "果汁盒", "酸奶盒", "纸杯", "咖啡杯", "奶茶杯", "复合包装"],
    2: ["易拉罐", "罐头盒", "铝罐", "铁罐", "铁皮", "铝箔", "钉子", "铁丝", "旧锅"],
    3: ["玻璃瓶", "酒瓶", "玻璃杯", "镜子", "罐头瓶"],
    4: ["果皮", "剩饭", "剩菜", "菜叶", "骨头", "蛋壳", "茶叶渣", "香蕉皮", "苹果核", "瓜皮", "面包"],
}

# 句式模板：(格式串, 是否含污染语义, 地区)。污染变体会改变正确投放建议（复刻 advice 逻辑）。
TEMPLATES: list[tuple[str, bool, str]] = [
    ("{}", False, "general"),
    ("用过的{}", False, "general"),
    ("废弃的{}", False, "general"),
    ("干净的{}", False, "general"),
    ("{}，应该投到哪个垃圾桶？", False, "general"),
    ("{}还能回收吗？", False, "general"),
    ("请分类：{}", False, "general"),
    ("在上海，{}怎么投放？", False, "shanghai"),
    ("{}，在上海属于什么垃圾？", False, "shanghai"),
    ("沾了油的{}", True, "general"),
    ("没洗的{}", True, "general"),
    ("{}，已经弄脏了", True, "general"),
]

# 指令变体：让模型学会对多种问法稳定输出
INSTRUCTIONS = [
    "你是垃圾分类助手。请判断物品描述对应的材质类别（五类之一：塑料、纸及纸板、金属、玻璃、食物残余），并给出投放建议。",
    "请分析下面的物品描述，输出材质类别与对应的垃圾投放建议。",
    "判断该物品的材质类别和垃圾投放去向。",
]


def advise(class_id: int, contaminated: bool, region: str) -> tuple[str, str]:
    """复刻实验四 advice.py 的判定逻辑，返回 (bin_zh, reason)。"""
    bin_key, _review, reason = MATERIAL_RULES[class_id]
    if contaminated and bin_key == "recyclable":
        bin_key, reason = "other", "描述提到被油污或食物污染，可回收材质按其他垃圾处理"
    return BINS[bin_key][region], reason


def format_output(class_id: int, contaminated: bool, region: str) -> str:
    bin_zh, reason = advise(class_id, contaminated, region)
    return f"材质：{CLASS_NAMES_ZH[class_id]}；投放建议：{bin_zh}；说明：{reason}"


def pick_combos(class_id: int, need: int, rng: random.Random) -> list[tuple[str, bool, str]]:
    """为一类材质生成 need 个不重复的（描述, 污染, 地区）组合。"""
    kws = [k for k in LEXICON[class_id] if not k.isascii()]
    rng.shuffle(kws)
    templates = TEMPLATES[:]
    rng.shuffle(templates)
    combos: list[tuple[str, bool, str]] = []
    seen: set[str] = set()
    for kw in kws:  # 词优先轮换，保证同词不同句式、同句式不同词
        for fmt, cont, region in templates:
            desc = fmt.format(kw)
            if desc not in seen:
                combos.append((desc, cont, region))
                seen.add(desc)
            if len(combos) >= need:
                return combos
    raise RuntimeError(f"类别 {class_id} 的关键词/模板组合不足 {need} 条")


def build() -> tuple[list[dict], list[dict]]:
    rng = random.Random(SEED)
    train: list[dict] = []
    test: list[dict] = []
    for cid, name in enumerate(CLASS_NAMES_ZH):
        combos = pick_combos(cid, 21, rng)  # 20 训练 + 1 测试，五类合计 100 条训练
        for i, (desc, cont, region) in enumerate(combos):
            rec = {
                "instruction": rng.choice(INSTRUCTIONS),
                "input": desc,
                "output": format_output(cid, cont, region),
                "meta": {"class_id": cid, "class_name": name,
                         "contaminated": cont, "region": region},
            }
            if i == 0:  # 每类第一条进测试集（与训练组合不重复）
                test.append(rec)
            else:
                train.append(rec)
    rng.shuffle(train)
    return train, test


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    train, test = build()

    train_path = OUT / "agent_finetune_data.json"
    test_path = OUT / "agent_finetune_test.json"
    train_path.write_text(json.dumps(train, ensure_ascii=False, indent=2), encoding="utf-8")
    test_path.write_text(json.dumps(test, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"训练集 {len(train)} 条 -> {train_path}")
    print(f"测试集 {len(test)} 条 -> {test_path}")
    by_class: dict[int, int] = {}
    for r in train:
        by_class[r["meta"]["class_id"]] = by_class.get(r["meta"]["class_id"], 0) + 1
    print("训练集每类条数:", by_class)
    print("\n样例（训练集前2条）:")
    for r in train[:2]:
        print(json.dumps({k: r[k] for k in ("instruction", "input", "output")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
