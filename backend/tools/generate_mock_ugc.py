"""Generate realistic mixed UGC fields for local POI records.

The output is deterministic by default and intentionally includes positive,
neutral, and negative signals. It is meant for development data, not for
pretending the comments are real user reviews.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "pois.json"
DEFAULT_OUTPUT = ROOT / "pois.with_ugc.json"


CATEGORY_PROFILES: dict[str, dict[str, Any]] = {
    "coffee": {
        "keywords": ["咖啡", "聊天", "出片", "座位", "甜品"],
        "positive": [
            "咖啡品质比较稳定，适合短暂停留和聊天。",
            "店内拍照角度还不错，下午光线更舒服。",
            "位置顺路，作为路线中途休息点比较合适。",
        ],
        "neutral": [
            "空间不算大，适合停留四十分钟左右。",
            "工作日体验更稳定，周末需要看具体客流。",
        ],
        "negative": [
            "热门时段座位紧张，可能需要等一会儿。",
            "价格不算低，只适合作为轻量补充点。",
        ],
    },
    "food": {
        "keywords": ["正餐", "本地味", "排队", "服务", "性价比"],
        "positive": [
            "菜品整体稳定，适合作为路线里的正餐节点。",
            "本地特色比较明显，外地游客也容易接受。",
            "多人同行点菜更划算，体验会更完整。",
        ],
        "neutral": [
            "用餐时间建议预留充足，翻台速度不一定稳定。",
            "口味偏大众，不是特别小众的隐藏店。",
        ],
        "negative": [
            "饭点排队风险偏高，临时去可能要等位。",
            "环境会比较热闹，不适合特别安静的约会。",
            "人均价格有波动，预算紧时需要控制点菜。",
        ],
    },
    "exhibition": {
        "keywords": ["看展", "室内", "文艺", "动线", "拍照"],
        "positive": [
            "室内空间稳定，雨天或炎热天气也比较友好。",
            "内容和拍照兼顾，适合作为下午的主站。",
            "整体节奏较慢，适合不赶时间的路线。",
        ],
        "neutral": [
            "展览内容会随档期变化，体验不完全固定。",
            "如果只想吃逛，停留时间可以适当缩短。",
        ],
        "negative": [
            "热门展期可能需要预约或排队入场。",
            "部分展区拍照限制较多，不一定每处都出片。",
        ],
    },
    "museum": {
        "keywords": ["博物馆", "历史", "室内", "预约", "亲子"],
        "positive": [
            "内容密度高，适合文化向或亲子路线。",
            "室内停留舒适，天气影响较小。",
        ],
        "neutral": [
            "需要一定浏览耐心，走马观花会比较可惜。",
        ],
        "negative": [
            "节假日预约和排队压力会明显上升。",
            "展厅之间步行较多，体力一般时不宜安排太满。",
        ],
    },
    "street": {
        "keywords": ["citywalk", "街区", "拍照", "小店", "步行"],
        "positive": [
            "适合边走边看，路线氛围比较自然。",
            "街区小店多，适合临时加咖啡或小吃。",
        ],
        "neutral": [
            "体验受天气影响比较大，雨天需要备选室内点。",
            "适合慢逛，不适合特别赶时间的安排。",
        ],
        "negative": [
            "周末热门路段人会比较多，拍照需要等空档。",
            "步行距离容易拉长，老人或带娃时要控制站点数。",
        ],
    },
    "park": {
        "keywords": ["散步", "户外", "绿地", "亲子", "天气"],
        "positive": [
            "开阔度不错，适合散步和降低路线强度。",
            "免费或低成本，预算压力小。",
        ],
        "neutral": [
            "更适合天气好的时候安排。",
        ],
        "negative": [
            "雨天和高温时体验会下降。",
            "如果周边补给少，停留时间不宜过长。",
        ],
    },
    "night": {
        "keywords": ["夜景", "拍照", "人流", "江景", "收尾"],
        "positive": [
            "适合作为路线收尾，夜间氛围比较明显。",
            "拍照记忆点强，适合情侣或朋友同行。",
        ],
        "neutral": [
            "夜景效果受天气和能见度影响。",
        ],
        "negative": [
            "热门观景位人流集中，可能不太安静。",
            "夜间转场需要预留交通时间。",
        ],
    },
    "shopping": {
        "keywords": ["商场", "室内", "餐饮", "空调", "人流"],
        "positive": [
            "室内配套完整，吃饭、休息和购物都方便。",
            "天气不好时作为兜底点比较稳。",
        ],
        "neutral": [
            "体验偏商业化，不一定有本地特色。",
        ],
        "negative": [
            "周末和饭点人流较大，安静感一般。",
            "容易产生额外消费，预算紧时要注意。",
        ],
    },
    "scene": {
        "keywords": ["景点", "拍照", "游客", "地标", "排队"],
        "positive": [
            "识别度高，适合第一次到访或拍照打卡。",
            "作为地标节点比较容易规划集合点。",
        ],
        "neutral": [
            "更适合短停，不一定需要安排太久。",
        ],
        "negative": [
            "游客多的时候体验会明显下降。",
            "商业化配套较多，想要小众感时不一定合适。",
        ],
    },
}


DEFAULT_PROFILE = {
    "keywords": ["稳定", "顺路", "人流", "体验"],
    "positive": ["整体体验比较稳，适合作为路线中的补充点。"],
    "neutral": ["具体体验会受时段和客流影响。"],
    "negative": ["高峰时段可能没有想象中轻松。"],
}


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _rng_for_poi(poi: dict[str, Any], seed: int) -> random.Random:
    raw = f"{seed}:{poi.get('id')}:{poi.get('name')}:{poi.get('city')}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:12], 16))


def _score(value: Any, default: float = 3.0, scale: float = 5.0) -> float:
    try:
        return _clamp(float(value) / scale)
    except (TypeError, ValueError):
        return _clamp(default / scale)


def _queue_risk(poi: dict[str, Any]) -> float:
    queue_level = _score(poi.get("queue_level"), default=3.0)
    rating = _score(poi.get("rating"), default=4.2)
    price = float(poi.get("price") or 0)
    price_pressure = 0.08 if price >= 120 else 0.0
    popularity_pressure = 0.12 if rating >= 0.9 else 0.0
    return _clamp(queue_level + popularity_pressure + price_pressure)


def _crowd_risk(poi: dict[str, Any], queue_risk: float) -> float:
    category = str(poi.get("category") or "")
    category_bonus = 0.12 if category in {"night", "scene", "shopping", "street"} else 0.0
    return _clamp(queue_risk * 0.75 + category_bonus)


def _build_signals(poi: dict[str, Any]) -> dict[str, float]:
    queue = _queue_risk(poi)
    crowd = _crowd_risk(poi, queue)
    indoor = str(poi.get("indoor_outdoor") or "") == "indoor"
    price = float(poi.get("price") or 0)
    category = str(poi.get("category") or "")

    signals = {
        "photo": _score(poi.get("photo_score")),
        "date": _score(poi.get("date_score")),
        "food": _score(poi.get("food_score")),
        "culture": _score(poi.get("culture_score")),
        "local_feature": _score(poi.get("local_feature_score")),
        "rainy_day": _score(poi.get("rainy_day_score")),
        "quiet": _clamp(0.75 - crowd * 0.55 + (0.08 if indoor else -0.05)),
        "queue_risk": queue,
        "crowd_risk": crowd,
        "value": _clamp(0.85 - price / 260.0 + (0.12 if price == 0 else 0.0)),
        "route_friction": _clamp(crowd * 0.45 + queue * 0.35 + (0.12 if category in {"street", "park"} else 0.0)),
    }
    return {key: round(value, 3) for key, value in signals.items()}


def _pick_many(rng: random.Random, values: list[str], minimum: int, maximum: int) -> list[str]:
    if not values:
        return []
    upper = min(maximum, len(values))
    lower = min(minimum, upper)
    count = rng.randint(lower, upper)
    return rng.sample(values, count)


def enrich_poi(poi: dict[str, Any], seed: int) -> dict[str, Any]:
    rng = _rng_for_poi(poi, seed)
    category = str(poi.get("category") or "")
    profile = CATEGORY_PROFILES.get(category, DEFAULT_PROFILE)
    signals = _build_signals(poi)

    keywords = list(dict.fromkeys([
        *list(poi.get("review_keywords") or []),
        *_pick_many(rng, list(profile["keywords"]), 2, 4),
    ]))

    positive = _pick_many(rng, list(profile["positive"]), 2, 3)
    neutral = _pick_many(rng, list(profile["neutral"]), 1, 2)

    negative_pool = list(profile["negative"])
    negative_count = 0
    if signals["queue_risk"] >= 0.7 or signals["crowd_risk"] >= 0.7:
        negative_count += 1
    if signals["value"] <= 0.45:
        negative_pool.append("性价比不算突出，预算敏感时需要权衡。")
    if signals["rainy_day"] <= 0.35:
        negative_pool.append("遇到下雨或高温时体验会打折。")
    if signals["queue_risk"] >= 0.82 or signals["crowd_risk"] >= 0.82:
        negative_count += 1
    if negative_count == 0 and rng.random() < 0.35:
        negative_count = 1
    negative = _pick_many(rng, negative_pool, 1, min(3, len(negative_pool))) if negative_count else []
    negative = negative[: min(negative_count, 2)]

    enriched = dict(poi)
    enriched["review_keywords"] = keywords
    enriched["positive_reviews"] = positive
    enriched["neutral_reviews"] = neutral
    enriched["negative_reviews"] = negative
    enriched["review_signals"] = signals
    enriched["ugc_summary"] = (
        f"模拟UGC：{len(positive)}条偏正向、{len(neutral)}条中性、"
        f"{len(negative)}条风险反馈；仅用于本地排序和演示。"
    )
    return enriched


def load_pois(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("POI file must contain a JSON list.")
    return [dict(item) for item in data if isinstance(item, dict)]


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate mixed mock UGC for local POI records.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input POI JSON file.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output POI JSON file with UGC.")
    parser.add_argument("--seed", type=int, default=20260605, help="Deterministic generation seed.")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the input file after generation.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = args.input.resolve()
    output_path = input_path if args.in_place else args.output.resolve()

    pois = load_pois(input_path)
    enriched = [enrich_poi(poi, args.seed) for poi in pois]
    save_json(output_path, enriched)

    negative_reviews = sum(len(item.get("negative_reviews") or []) for item in enriched)
    positive_reviews = sum(len(item.get("positive_reviews") or []) for item in enriched)
    summary = {
        "input": str(input_path),
        "output": str(output_path),
        "total_pois": len(enriched),
        "positive_reviews": positive_reviews,
        "negative_reviews": negative_reviews,
        "seed": args.seed,
        "in_place": bool(args.in_place),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
