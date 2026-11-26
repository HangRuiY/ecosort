"""文本问答：材质判断 + 知识库检索。

- 材质判断：项目实验一至三没有训练文本模型，这里用可解释的关键词基线（最长匹配 + 平滑归一化），
  输出与图像模型相同的五类材质，便于图文比对。后续可替换为蒸馏 BERT，接口不变。
- 知识库：实验一清洗后的 21 条辅助文本（data/split/summary.json → text_processing.records），
  复用实验一 prepare_documents 的字符 2-4 gram TF-IDF，余弦相似度检索。
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter

from .advice import advise
from .disposal_rules import disposal_rule
from .config import SUMMARY_JSON
from .reuse import CLASS_KEYS, CLASS_NAMES_ZH, prepare_documents

log = logging.getLogger("ecosort")

# 实验2交接后为五类体系：旧十类中软质/形态不明塑料并入塑料，复合包装按主要材质
# 分入纸及纸板（纸基：牛奶盒/纸杯等）或塑料（塑基：薯片袋/铝箔袋等）；
# 五类以外的烟蒂、电池等由独立投放规则处理，不添加或伪造视觉材质类别。
LEXICON: dict[int, list[str]] = {
    0: ["塑料瓶", "矿泉水瓶", "饮料瓶", "洗洁精", "洗发水", "沐浴露", "清洁剂", "塑料盒", "餐盒", "外卖盒", "塑料杯",
        "瓶盖", "塑料桶", "塑料盆", "衣架", "塑料", "塑料袋", "保鲜膜", "保鲜袋", "包装袋", "食品袋", "薄膜",
        "快递袋", "气泡膜", "垃圾袋", "塑料碎片", "碎塑料", "塑料片", "泡沫", "泡沫塑料", "薯片袋", "零食袋",
        "铝箔袋", "bottle", "plastic", "bag", "film", "wrap"],
    1: ["纸箱", "纸盒", "快递盒", "快递纸箱", "报纸", "书本", "旧书", "纸张", "杂志", "纸板", "纸袋", "传单", "纸巾",
        "卫生纸", "餐巾纸", "纸", "牛奶盒", "利乐包", "饮料盒", "果汁盒", "酸奶盒", "纸杯", "咖啡杯", "奶茶杯",
        "复合包装", "cardboard", "paper", "carton"],
    2: ["易拉罐", "罐头", "铝罐", "铁罐", "金属", "铁皮", "铝箔", "钉子", "铁丝", "锅", "can", "tin", "metal"],
    3: ["玻璃", "酒瓶", "玻璃瓶", "玻璃杯", "镜子", "罐头瓶", "glass"],
    4: ["果皮", "剩饭", "剩菜", "菜叶", "骨头", "蛋壳", "茶叶", "水果", "食物", "面包", "瓜皮", "香蕉皮", "苹果核",
        "菜渣", "外卖剩", "food"],
}
# 有固定结论的物品：材质虽是纸，但不可回收
FORCE_CONTAMINATED = ["纸巾", "卫生纸", "餐巾纸"]
DIRTY = re.compile(r"油|脏|污|沾|没洗|未清洗|没冲|残留|湿")
CLEAN = re.compile(r"干净|洗过|冲洗|清洗过|清空")
# 检索时为类别补充知识库中的表述
EXPANSION = {0: "塑料 可回收物 污损塑料袋", 1: "纸盒 纸张 可回收物 纸塑铝复合包装 纸杯 专项回收",
             2: "金属罐 可回收物", 3: "玻璃制品 尖锐边角", 4: "食物残余 湿垃圾 包装"}

_MATCHERS = sorted(((kw.lower(), cid) for cid, kws in LEXICON.items() for kw in kws), key=lambda x: -len(x[0]))


def _bag(text: str) -> Counter:
    text = text.lower()
    return Counter(text[i:i + n] for n in (2, 3, 4) for i in range(len(text) - n + 1))


class KnowledgeBase:
    def __init__(self):
        self.records: list[dict] = []
        self.vocab: dict[str, int] = {}
        self.rows: list[dict[int, float]] = []
        self.df: Counter = Counter()
        self.error: str | None = None
        self._load()

    def _load(self):
        try:
            summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
            source = summary["text_processing"]["records"]
            prepared = prepare_documents(source)  # 复用实验一：清洗、去重、字符 TF-IDF
            self.records = prepared["records"]
            self.vocab = {t: i for i, t in enumerate(prepared["tfidf"]["vocabulary"])}
            self.rows = [{int(k): v for k, v in row.items()} for row in prepared["tfidf"]["sparse_rows"]]
            for r in self.records:
                self.df.update(_bag(r["text"]).keys())
        except Exception as exc:
            self.error = f"知识库加载失败：{exc}"
            log.warning(self.error)

    def search(self, query: str, k: int = 3) -> list[dict]:
        if not self.records:
            return []
        n = len(self.records)
        vec = {self.vocab[t]: c * (1 + math.log((1 + n) / (1 + self.df[t]))) for t, c in _bag(query).items() if t in self.vocab}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        scored = []
        for rec, row in zip(self.records, self.rows):
            s = sum(v * row.get(i, 0.0) for i, v in vec.items()) / norm
            if s > 0.02:
                scored.append((s, rec))
        scored.sort(key=lambda x: -x[0])
        return [{"id": r["id"], "text": r["text"], "region": r.get("region"), "label": r.get("label"),
                 "source_url": r.get("source_url"), "is_synthetic": r.get("is_synthetic", False),
                 "score": round(s, 4)} for s, r in scored[:k]]


_kb: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


def classify(text: str) -> dict:
    low = text.lower()
    taken: list[tuple[int, int]] = []
    scores = [0.0] * len(CLASS_KEYS)
    matched = []
    for kw, cid in _MATCHERS:  # 最长匹配优先，被长词覆盖的短词不重复计分
        for m in re.finditer(re.escape(kw), low):
            span = (m.start(), m.end())
            if any(not (span[1] <= a or span[0] >= b) for a, b in taken):
                continue
            taken.append(span)
            scores[cid] += len(kw)
            matched.append({"keyword": text[span[0]:span[1]], "class_id": cid})
    recognized = any(scores)
    alpha = 0.15
    total = sum(scores) + alpha * len(CLASS_KEYS)
    probs = [(s + alpha) / total for s in scores]
    ranking = sorted(({"class_id": i, "name": CLASS_KEYS[i], "name_zh": CLASS_NAMES_ZH[i], "prob": round(p, 4)}
                      for i, p in enumerate(probs)), key=lambda r: -r["prob"])
    contaminated = bool(DIRTY.search(text)) and not (CLEAN.search(text) and not re.search("油", text))
    if any(w in text for w in FORCE_CONTAMINATED):
        contaminated = True
    return {"recognized": recognized, "ranking": ranking, "matched": matched, "contaminated": contaminated}


def answer(text: str, region: str = "general") -> dict:
    special = disposal_rule(text, region)
    if special:
        return {
            "text": text,
            "method": "item-disposal-rule + char-tfidf-retrieval",
            "recognized": False,
            "disposal_recognized": True,
            "disposal_item": special["item"],
            "top": None,
            "ranking": [],
            "matched_keywords": [{"keyword": word, "class_id": None} for word in special["keywords"]],
            "contaminated": False,
            "advice": special["advice"],
            "rule_source": special["source"],
            "evidence": get_kb().search(text + " " + special["item"]),
        }
    c = classify(text)
    top = c["ranking"][0]
    advice = advise(top["class_id"], c["contaminated"], region) if c["recognized"] else None
    query = text + (" " + top["name_zh"] + " " + EXPANSION[top["class_id"]] if c["recognized"] else "")
    if c["contaminated"]:
        query += " 沾污 污染"
    return {
        "text": text,
        "method": "lexicon-baseline + char-tfidf-retrieval",
        "recognized": c["recognized"],
        "top": top if c["recognized"] else None,
        "ranking": c["ranking"][:5],
        "matched_keywords": c["matched"],
        "contaminated": c["contaminated"],
        "advice": advice,
        "evidence": get_kb().search(query),
    }
