"""Route alignment checks for output-side validation.

The planner should not only understand the user's request but also verify that
the generated route still matches the intent. This module keeps that logic
small, reusable, and easy to regression-test.
"""

from __future__ import annotations

from typing import Any

from core.route_policy import ROUTE_POLICY
from core.schemas import ParsedIntent, RouteStop


def _stop_poi(stop: RouteStop) -> Any:
    return getattr(stop, "poi", None)


def _route_categories(stops: list[RouteStop]) -> set[str]:
    categories: set[str] = set()
    for stop in stops:
        poi = _stop_poi(stop)
        if poi is None:
            continue
        category = getattr(poi, "category", None)
        if category:
            categories.add(str(category))
    return categories


def _route_category_counts(stops: list[RouteStop]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for stop in stops:
        poi = _stop_poi(stop)
        if poi is None:
            continue
        category = getattr(poi, "category", None)
        if category:
            key = str(category)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _route_text(stops: list[RouteStop]) -> str:
    pieces: list[str] = []
    for stop in stops:
        poi = _stop_poi(stop)
        if poi is None:
            continue
        pieces.extend(
            [
                str(getattr(poi, "name", "") or ""),
                str(getattr(poi, "description", "") or ""),
                " ".join(getattr(poi, "tags", []) or []),
                " ".join(getattr(poi, "review_keywords", []) or []),
                " ".join(getattr(poi, "suitable_for", []) or []),
            ]
        )
    return " ".join(piece for piece in pieces if piece)


def _signal_context_warnings(signal_context: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    gaps: list[str] = []
    if not isinstance(signal_context, dict):
        return warnings, gaps

    ugc_summary = signal_context.get("ugc_signal_summary")
    if isinstance(ugc_summary, dict):
        signal_quality = float(ugc_summary.get("signal_quality", 0.0) or 0.0)
        noise_risk = str(ugc_summary.get("noise_risk", "") or "")
        warning_ratio = float(ugc_summary.get("warning_ratio", 0.0) or 0.0)
        if noise_risk == "high" or signal_quality < 0.6:
            warnings.append("UGC 证据偏弱，当前只适合作为软参考。")
            gaps.append("ugc_signal_weak")
        elif warning_ratio >= 0.55:
            warnings.append("UGC 中风险提示偏多，建议保留更多回旋空间。")
            gaps.append("ugc_signal_noisy")

    heat_summary = signal_context.get("heat_signal_summary")
    if isinstance(heat_summary, dict):
        high_queue_count = int(heat_summary.get("high_queue_count", 0) or 0)
        max_heat_score = float(heat_summary.get("max_heat_score", 0.0) or 0.0)
        if high_queue_count >= 2 or max_heat_score >= 0.85:
            warnings.append("热度或排队信号偏高，建议预留缓冲时间。")
            gaps.append("heat_signal_hot")

    return warnings, gaps


def evaluate_route_alignment(
    intent: ParsedIntent,
    stops: list[RouteStop],
    stats: dict[str, Any] | None = None,
    signal_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a compact route quality report."""

    stats = stats or {}
    route_categories = _route_categories(stops)
    route_category_counts = _route_category_counts(stops)
    route_text = _route_text(stops)
    warnings: list[str] = []
    strengths: list[str] = []
    gaps: list[str] = []
    signal_warnings, signal_gaps = _signal_context_warnings(signal_context)
    warnings.extend(signal_warnings)
    gaps.extend(signal_gaps)

    required_categories = list(dict.fromkeys(getattr(intent, "required_categories", []) or []))
    missing_categories = [item for item in required_categories if item not in route_categories]
    category_caps = dict(getattr(intent, "category_caps", {}) or {})
    category_min_counts = dict(getattr(intent, "category_min_counts", {}) or {})
    for category, minimum in category_min_counts.items():
        if route_category_counts.get(category, 0) < int(minimum or 0):
            warnings.append(f"路线里 {category} 类站点还不够，和你的主目标还可以再贴近一点。")
            gaps.append(f"category_min_missing:{category}")
    for category, cap in category_caps.items():
        if route_category_counts.get(category, 0) > int(cap or 0):
            warnings.append(f"路线里 {category} 类站点偏多，支持型需求不该抢主线。")
            gaps.append(f"category_cap_exceeded:{category}")
    if missing_categories:
        warnings.append(f"路线还没有完全覆盖你想要的类别：{'、'.join(missing_categories)}。")
        gaps.extend([f"missing_category:{item}" for item in missing_categories])
    elif required_categories:
        strengths.append("required_categories_covered")

    preferences = set(getattr(intent, "preferences", []) or [])
    if "food" in preferences and not ({"food", "coffee"} & route_categories or "吃饭" in route_text or "小吃" in route_text):
        warnings.append("你提到想吃饭，但当前路线里还没有明显的餐饮停点。")
        gaps.append("missing_food_stop")
    if "night_view" in preferences and "night" not in route_categories and "夜景" not in route_text:
        warnings.append("你提到想看夜景，但当前路线里还没有夜景节点。")
        gaps.append("missing_night_view")
    if "culture" in preferences and not ({"museum", "exhibition"} & route_categories or any(token in route_text for token in ("博物馆", "展览", "美术馆"))):
        warnings.append("你提到文化或看展，但当前路线里的文化站点还不够明确。")
        gaps.append("missing_culture_stop")
    if "local_feature" in preferences and not any(token in route_text for token in ("老字号", "本地", "地道", "烟火气", "老城")):
        warnings.append("你想要的本地感还可以再加强一点。")
        gaps.append("weak_local_feature")
    if "premium" in preferences:
        premium_stops = [
            stop
            for stop in stops
            if float(getattr(_stop_poi(stop), "price", 0) or 0) >= 120
            or float(getattr(_stop_poi(stop), "rating", 0) or 0) >= 4.6
        ]
        if not premium_stops:
            warnings.append("你提到想要更高端精致的体验，但当前路线的品质感还不够明显。")
            gaps.append("weak_premium_match")
    if "rainy_day" in preferences and any(getattr(_stop_poi(stop), "indoor_outdoor", "") == "outdoor" for stop in stops):
        warnings.append("路线里仍包含户外点，下雨时体验会下降。")
        gaps.append("rainy_outdoor_mix")
    if getattr(intent, "avoid_queue", False) and any(int(getattr(_stop_poi(stop), "queue_level", 3) or 3) >= 4 for stop in stops):
        warnings.append("当前路线仍有较热门的点，排队风险还在。")
        gaps.append("queue_risk_remains")
    if getattr(intent, "avoid_crowded", False) and any(int(getattr(_stop_poi(stop), "queue_level", 3) or 3) >= 4 for stop in stops):
        warnings.append("你说想避开拥挤，但当前路线里还保留了高热度站点。")
        gaps.append("crowd_risk_remains")

    budget = getattr(intent, "budget", None)
    route_cost = float(stats.get("total_cost", 0) or 0)
    if budget is not None and route_cost > float(budget) * 1.1:
        warnings.append("当前路线花费略超预算，后续可再压缩一版。")
        gaps.append("budget_overrun")
    elif budget is not None and route_cost <= float(budget):
        strengths.append("budget_fit")

    available = max(float(getattr(intent, "available_time", 0) or 0), 1.0)
    travel_time = float(stats.get("total_travel", 0) or 0)
    total_time = float(stats.get("total_duration", 0) or 0) + travel_time
    travel_ratio = travel_time / max(total_time, 1.0)
    if getattr(intent, "pace", "normal") == "slow" and travel_ratio > 0.35:
        warnings.append("路线转场偏多，和“慢一点/松弛点”的诉求还有一点偏差。")
        gaps.append("slow_pace_mismatch")
    if getattr(intent, "pace", "normal") == "fast" and total_time > available * 1.05:
        warnings.append("路线总时长仍偏长，和“高效/尽快”的诉求不完全一致。")
        gaps.append("fast_pace_mismatch")

    matched_preferences: list[str] = []
    if "photo" in preferences and any(float(getattr(_stop_poi(stop), "photo_score", 0) or 0) >= 4 for stop in stops):
        matched_preferences.append("photo")
    if "quiet" in preferences and any(int(getattr(_stop_poi(stop), "queue_level", 3) or 3) <= 2 for stop in stops):
        matched_preferences.append("quiet")
    if "value" in preferences and route_cost <= float(budget or route_cost):
        matched_preferences.append("value")
    if "premium" in preferences and any(float(getattr(_stop_poi(stop), "price", 0) or 0) >= 120 for stop in stops):
        matched_preferences.append("premium")
    if "citywalk" in preferences and any(getattr(_stop_poi(stop), "indoor_outdoor", "") == "outdoor" for stop in stops):
        matched_preferences.append("citywalk")

    denominator = max(len(required_categories) + len(preferences), 1)
    alignment_score = round(
        max(
            0.0,
            min(
                1.0,
                0.28
                + 0.28 * (len(required_categories) - len(missing_categories)) / max(len(required_categories), 1)
                + 0.24 * len(matched_preferences) / denominator
                + 0.10 * len(strengths)
                - float(ROUTE_POLICY["verification"]["min_gap_penalty"]) * len(gaps),
            ),
        ),
        3,
    )

    return {
        "alignment_score": alignment_score,
        "route_categories": sorted(route_categories),
        "route_category_counts": route_category_counts,
        "required_categories": required_categories,
        "category_caps": category_caps,
        "category_min_counts": category_min_counts,
        "missing_categories": missing_categories,
        "matched_preferences": matched_preferences,
        "warnings": warnings,
        "strengths": strengths,
        "gaps": gaps,
        "budget": budget,
        "route_cost": route_cost,
        "travel_ratio": round(travel_ratio, 2),
    }


def critique_route(
    intent: ParsedIntent,
    stops: list[RouteStop],
    stats: dict[str, Any] | None = None,
    signal_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Turn alignment checks into a small output-side critique."""

    report = evaluate_route_alignment(intent, stops, stats, signal_context)
    gaps = list(report.get("gaps", []) or [])
    warnings = list(report.get("warnings", []) or [])
    recommendations: list[str] = []
    reasons: list[str] = []

    def add_recommendation(reason: str, recommendation: str) -> None:
        if recommendation not in recommendations:
            recommendations.append(recommendation)
        if reason not in reasons:
            reasons.append(reason)

    for gap in gaps:
        if gap.startswith("missing_category:"):
            category = gap.split(":", 1)[1]
            add_recommendation(
                f"缺少 {category} 类主线",
                f"补一个 {category} 类站点，或者把当前路线里最弱的支线换成它。",
            )
        elif gap.startswith("category_min_missing:"):
            category = gap.split(":", 1)[1]
            add_recommendation(
                f"{category} 类数量不足",
                f"至少再增加 1 个 {category} 类节点，直到满足数量约束。",
            )
        elif gap.startswith("category_cap_exceeded:"):
            category = gap.split(":", 1)[1]
            add_recommendation(
                f"{category} 类偏多",
                f"减少 {category} 类支持站点，避免它盖过主体体验。",
            )
        elif gap == "missing_food_stop":
            add_recommendation("缺少餐饮节点", "补一个更自然的餐饮或早茶节点，并放在更合适的节奏位置。")
        elif gap == "missing_night_view":
            add_recommendation("缺少夜景节点", "把夜景类站点放到更靠后的时段，强化收尾体验。")
        elif gap == "missing_culture_stop":
            add_recommendation("文化体验不够明确", "增加博物馆、展览，或更有内容感的文化站点。")
        elif gap == "weak_local_feature":
            add_recommendation("本地特色不足", "优先用老字号、本地街区，或更有城市气质的点补强。")
        elif gap == "weak_premium_match":
            add_recommendation("品质感偏弱", "提高整体站点的评分、价格带，或精品属性。")
        elif gap == "queue_risk_remains":
            add_recommendation("排队风险还在", "替换热门站点，优先选热度更低、更稳的候选。")
        elif gap == "crowd_risk_remains":
            add_recommendation("拥挤风险还在", "减少高热度站点，优先保留更舒展的路线形状。")
        elif gap == "budget_overrun":
            add_recommendation("预算超了", "切换到更紧凑的版本，压缩高价站点或转场成本。")
        elif gap == "slow_pace_mismatch":
            add_recommendation("节奏不够松弛", "减少转场和冗余站点，让路线更轻松。")
        elif gap == "fast_pace_mismatch":
            add_recommendation("节奏还不够快", "缩短总时长，优先保留命中率最高的主点。")
        elif gap == "ugc_signal_weak":
            add_recommendation("UGC 信号偏弱", "当前只把评论信号作为软参考，优先依赖结构化 POI 事实。")
        elif gap == "ugc_signal_noisy":
            add_recommendation("UGC 风险提示较多", "保守使用评论信号，避免让噪声主导路线取舍。")
        elif gap == "heat_signal_hot":
            add_recommendation("热度偏高", "为热门站点预留缓冲，或换成更平稳的近似体验。")

    if not recommendations:
        if float(report.get("alignment_score", 0.0) or 0.0) >= 0.78:
            decision = "accept"
            priority = "keep"
        else:
            decision = "review"
            priority = "refine"
    else:
        decision = "repair" if len(gaps) <= 2 else "replan"
        priority = "coverage" if any(item.startswith("missing_category:") for item in gaps) else "constraint"

    should_replan = decision == "replan" or float(report.get("alignment_score", 0.0) or 0.0) < 0.62
    return {
        **report,
        "decision": decision,
        "priority": priority,
        "critical_gaps": gaps[:3] if should_replan else gaps[:2],
        "recommendations": recommendations[:4],
        "reasons": reasons[:4],
        "should_replan": should_replan,
        "warning_count": len(warnings),
    }
