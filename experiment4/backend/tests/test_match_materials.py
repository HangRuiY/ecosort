"""All five-class combinations must use the current material mapping."""
from itertools import product

import pytest

from app.routers.match import match
from app.text_service import answer

DESCRIPTIONS = ["塑料瓶", "纸箱", "金属罐", "玻璃瓶", "食物"]


def compare(image_ids, text):
    image = {
        "filename": "comparison.png", "count": len(image_ids),
        "detections": [{"class_id": cid, "confidence": 0.89} for cid in image_ids],
        "image": {}, "backend_used": "pytorch_fp32", "stage_ms": 0,
    }
    result = answer(text)
    result["stage_ms"] = 0
    return match(image=image, text=result)["result"]


@pytest.mark.parametrize("image_id,text_id", list(product(range(5), repeat=2)))
def test_all_five_material_pairs(image_id, text_id):
    result = compare([image_id], DESCRIPTIONS[text_id])
    assert result["verdict"] == ("consistent" if image_id == text_id else "inconsistent")
    assert result["score"] == (0.89 if image_id == text_id else 0.0)
    if image_id != text_id:
        assert "相近材质" not in result["reason"]


def test_glass_and_food_regression():
    result = compare([3], "食物")
    assert result["verdict"] == "inconsistent" and result["score"] == 0
    assert "食物残余" in result["reason"] and "玻璃" in result["reason"]


def test_matching_class_in_a_mixed_image_is_consistent():
    result = compare([3, 4], "食物")
    assert result["verdict"] == "consistent"


def test_empty_detection_is_not_a_match():
    assert compare([], "食物")["verdict"] == "inconsistent"


@pytest.mark.parametrize("description", ["烟头", "废电脑", "xyz123"])
def test_no_visual_material_is_reported_as_unknown(description):
    assert compare([3], description)["verdict"] == "unknown"
