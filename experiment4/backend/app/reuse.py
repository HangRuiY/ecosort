"""复用实验一的数据处理逻辑。

直接导入 experiment1/experiment1.py（只依赖 numpy / PyYAML / Pillow；单独运行 experiment4 时导入 assets 中的副本），
使用其中的类别中文名、目标框裁剪 clean_box 和文本清洗 + 字符 TF-IDF prepare_documents。
导入失败时（例如单独部署后端、没有实验一目录）使用逐行一致的本地副本，保证服务可启动。
"""
from __future__ import annotations

import html
import importlib.util
import logging
import math
import re
import unicodedata
from collections import Counter

from .config import EXP1_SCRIPT

log = logging.getLogger("ecosort")
_exp1 = None
try:
    _spec = importlib.util.spec_from_file_location("experiment1", EXP1_SCRIPT)
    if _spec and _spec.loader and EXP1_SCRIPT.is_file():
        _exp1 = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_exp1)
except Exception as exc:  # pragma: no cover
    log.warning("无法导入 experiment1.py，改用本地副本：%s", exc)
    _exp1 = None

SOURCE = "experiment1.py" if _exp1 else "local-copy"

if _exp1:
    CLASS_NAMES_ZH = list(_exp1.CLASS_NAMES_ZH)
    clean_box = _exp1.clean_box
    prepare_documents = _exp1.prepare_documents
else:  # pragma: no cover - 与 experiment1.py 保持一致的副本
    CLASS_NAMES_ZH = ['塑料', '纸及纸板', '金属', '玻璃', '食物残余']

    def clean_box(box, width, height):
        try:
            values = list(map(float, box))
        except (TypeError, ValueError):
            return None
        if len(values) != 4 or not all(math.isfinite(x) for x in values):
            return None
        x, y, w, h = values
        if w <= 0 or h <= 0:
            return None
        x1, y1 = max(0., x), max(0., y)
        x2, y2 = min(float(width), x + w), min(float(height), y + h)
        return [x1, y1, x2 - x1, y2 - y1] if x2 > x1 and y2 > y1 else None

    def prepare_documents(documents):
        records, seen = [], set()
        for record in documents:
            text = html.unescape(re.sub(r'<[^>]*>', '', record['text']))
            text = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text)).strip()
            if 35 <= len(text) <= 1500 and text not in seen:
                records.append({**record, 'text': text})
                seen.add(text)
        bags = [Counter(text[i:i+n] for n in (2, 3, 4) for i in range(len(text)-n+1))
                for text in (r['text'].lower() for r in records)]
        frequencies, total = Counter(), Counter()
        for bag in bags:
            frequencies.update(bag.keys())
            total.update(bag)
        vocabulary = sorted(total, key=lambda t: (-total[t], t))[:6000]
        positions = {token: index for index, token in enumerate(vocabulary)}
        vectors = []
        for bag in bags:
            vector = {positions[t]: n * (1 + math.log((1 + len(records)) / (1 + frequencies[t])))
                      for t, n in bag.items() if t in positions}
            norm = math.sqrt(sum(v * v for v in vector.values())) or 1.
            vectors.append({str(i): round(v / norm, 8) for i, v in vector.items()})
        return {'input_records': len(documents), 'output_records': len(records), 'records': records,
                'tfidf': {'method': 'character 2-4 grams, smoothed IDF, L2 normalization',
                          'vocabulary': vocabulary, 'sparse_rows': vectors}}

# 实验二交接（五类体系）：检测模型升级为 YOLO11s，数据集合并为
# 塑料 / 纸及纸板 / 金属 / 玻璃 / 食物残余 五类（详见 experiment2 交接文档）。
# 类别表不再沿用 experiment1.py 的十类定义，这里统一覆盖；
# clean_box / prepare_documents 仍复用实验一，不受影响。
CLASS_NAMES_ZH = ['塑料', '纸及纸板', '金属', '玻璃', '食物残余']
CLASS_KEYS = ["plastic", "paper_cardboard", "metal", "glass", "food_waste"]
