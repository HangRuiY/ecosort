"""材质 → 投放建议。

模型输出的是视觉材质，不等于投放结论（见 data/README.md 与知识库 project_city / project_special）。
这里给出通用的四分类建议，并对被污染的可回收物标记为需人工核查。
实验二交接后检测体系为五类（塑料 / 纸及纸板 / 金属 / 玻璃 / 食物残余）。
"""
from __future__ import annotations

BINS = {
    "recyclable": {"general": "可回收物", "shanghai": "可回收物"},
    "kitchen": {"general": "厨余垃圾", "shanghai": "湿垃圾"},
    "hazardous": {"general": "有害垃圾", "shanghai": "有害垃圾"},
    "other": {"general": "其他垃圾", "shanghai": "干垃圾"},
}
REGIONS = {"general": "通用（GB/T 19095-2019）", "shanghai": "上海"}

# class_id -> (默认去向, 是否需核查, 说明)。实验二交接后为五类体系。
MATERIAL_RULES = {
    0: ("recyclable", False, "塑料容器/包装清空、冲洗后可回收；沾污塑料投其他垃圾"),
    1: ("recyclable", False, "纸及纸板保持干燥清洁可回收；油污纸张投其他垃圾"),
    2: ("recyclable", False, "金属罐冲洗后可回收"),
    3: ("recyclable", False, "玻璃轻放，尖锐边角包裹后投放"),
    4: ("kitchen", False, "食物残余与包装分离后投放"),
}


def advise(class_id: int, contaminated: bool = False, region: str = "general") -> dict:
    region = region if region in REGIONS else "general"
    bin_key, review, reason = MATERIAL_RULES.get(class_id, ("other", True, "未知类别"))
    if contaminated and bin_key == "recyclable":
        bin_key, reason = "other", "描述提到被油污或食物污染，可回收材质按其他垃圾处理"
    return {"bin": bin_key, "bin_zh": BINS[bin_key][region], "needs_review": review, "reason": reason}


def count_bins(advices: list[dict]) -> dict:
    counts = {k: 0 for k in BINS}
    review = 0
    for a in advices:
        counts[a["bin"]] += 1
        review += a["needs_review"]
    return {"counts": counts, "needs_review": review}
