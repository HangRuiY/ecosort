"""Shared EcoSort class mappings and metric/result serialization."""
from __future__ import annotations

import math

CLASS_NAMES_ZH = {
    0: "硬质塑料",
    1: "软质塑料",
    2: "形态不明塑料",
    3: "纸及纸板",
    4: "复合包装",
    5: "金属",
    6: "玻璃",
    7: "食物残余",
    8: "烟蒂",
    9: "特殊及不明垃圾",
}

ECOSORT_NAMES = dict(enumerate((
    "plastic_rigid", "plastic_flexible", "plastic_unspecified", "paper_cardboard",
    "composite_packaging", "metal", "glass", "food_waste", "cigarette", "special_unknown",
)))

def finite_float(value):
    """将指标转为普通浮点数；不可用指标保留为 null。"""
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None

def normalize_names(names) -> dict[int, str]:
    if isinstance(names, list):
        return {i: str(name) for i, name in enumerate(names)}
    return {int(key): str(value) for key, value in names.items()}

def collect_per_class(metrics, names: dict[int, str]) -> list[dict]:
    """
    AP 数组按出现的类别排列，不一定直接等于类别 ID。
    必须通过 ap_class_index 建立对应关系。
    """
    index_by_class = {
        int(class_id): index
        for index, class_id in enumerate(metrics.box.ap_class_index)
    }

    rows = []

    for class_id, class_name in sorted(names.items()):
        instances = int(metrics.nt_per_class[class_id])
        images = int(metrics.nt_per_image[class_id])
        metric_index = index_by_class.get(class_id)

        if metric_index is None:
            precision = recall = ap50 = ap50_95 = f1 = None
        else:
            precision, recall, ap50, ap50_95 = (
                finite_float(value)
                for value in metrics.box.class_result(metric_index)
            )
            f1 = finite_float(metrics.box.f1[metric_index])

        if instances == 0:
            note = "无真值目标，不报告该类AP"
        elif instances < 20:
            note = "目标样本很少，指标解释需谨慎"
        else:
            note = ""

        rows.append({
            "class_id": class_id,
            "class_name": class_name,
            "class_name_zh": CLASS_NAMES_ZH.get(class_id, ""),
            "images_with_class": images,
            "instances": instances,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "ap50": ap50,
            "ap50_95": ap50_95,
            "note": note,
        })

    return rows

def detections_from_result(result, names: dict[int, str]) -> list[dict]:
    """Coordinates are original-image pixel xyxy; no ground-truth matching here."""
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return []
    coordinates = boxes.xyxy.detach().cpu().tolist()
    confidence = boxes.conf.detach().cpu().tolist()
    classes = boxes.cls.detach().cpu().tolist()
    rows = []
    for xyxy, score, class_value in zip(coordinates, confidence, classes):
        class_id = int(class_value)
        if class_id not in names or class_value != class_id:
            raise ValueError(f"Unexpected predicted class ID: {class_value}")
        values = [finite_float(value) for value in [score, *xyxy]]
        if len(xyxy) != 4 or any(value is None for value in values):
            raise ValueError("Nonfinite or invalid detection box")
        rows.append({
            "class_id": class_id,
            "class_name": names[class_id],
            "class_name_zh": CLASS_NAMES_ZH.get(class_id, ""),
            "confidence": values[0],
            "xyxy": values[1:],
        })
    return rows
