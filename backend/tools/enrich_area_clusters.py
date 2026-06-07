"""Add route area clusters to local POI records.

The clusters are local-demo planning hints, not official administrative data.
They keep route generation compact before an external map provider is enabled.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "pois.json"


AREA_LABELS = {
    "gz_old_town": "广州老城",
    "gz_dongshan": "东山口",
    "gz_zhujiang_new_town": "珠江新城",
    "gz_haizhu_tower": "海珠广州塔",
    "gz_tianhe": "天河商圈",
    "gz_north": "广州北部户外",
    "sh_bund_people_square": "外滩人民广场",
    "sh_jingan": "静安南京西路",
    "sh_xuhui": "徐汇衡复",
    "sh_west_bund": "徐汇西岸",
    "sh_north_bund": "北外滩",
    "sh_pudong": "浦东陆家嘴",
    "sh_yangpu": "杨浦大学路",
    "sh_changning": "长宁愚园路",
}


def load_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("POI file must contain a JSON list.")
    return [dict(item) for item in data if isinstance(item, dict)]


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _text(poi: dict[str, Any]) -> str:
    values: list[str] = [
        str(poi.get("name") or ""),
        str(poi.get("district") or ""),
        str(poi.get("address") or ""),
        str(poi.get("description") or ""),
    ]
    values.extend(str(item or "") for item in poi.get("tags") or [])
    return " ".join(values)


def _cluster_guangzhou(poi: dict[str, Any]) -> str:
    text = _text(poi)
    district = str(poi.get("district") or "")
    lon = float(poi.get("longitude") or 0.0)
    lat = float(poi.get("latitude") or 0.0)

    if "白云" in district or "白云山" in text:
        return "gz_north"
    if any(token in text for token in ("广州塔", "海心沙", "T.I.T", "客村", "海珠湿地", "海珠区", "二沙岛")):
        if "江南西" in text or "工业大道" in text or "昌岗" in text:
            return "gz_haizhu_tower"
        return "gz_haizhu_tower"
    if any(token in text for token in ("珠江新城", "K11", "正佳", "体育西", "天河", "花城汇")):
        return "gz_zhujiang_new_town" if lon >= 113.32 or "珠江新城" in text else "gz_tianhe"
    if any(token in text for token in ("东山口", "东山", "庙前西")):
        return "gz_dongshan"
    if any(token in text for token in ("荔湾", "沙面", "永庆坊", "上下九", "泮塘", "西关", "恩宁", "西堤")):
        return "gz_old_town"
    if any(token in text for token in ("北京路", "海珠桥", "沿江", "越秀公园", "南越王", "麓湖", "解放北")):
        return "gz_old_town"
    if district == "天河区":
        return "gz_tianhe"
    if district == "海珠区":
        return "gz_haizhu_tower"
    if district in {"越秀区", "荔湾区"}:
        return "gz_old_town" if lat >= 23.11 else "gz_dongshan"
    return "gz_old_town"


def _cluster_shanghai(poi: dict[str, Any]) -> str:
    text = _text(poi)
    district = str(poi.get("district") or "")
    lon = float(poi.get("longitude") or 0.0)
    lat = float(poi.get("latitude") or 0.0)

    if "杨浦" in district or any(token in text for token in ("大学路", "杨浦滨江", "杨浦")):
        return "sh_yangpu"
    if "浦东" in district or any(token in text for token in ("陆家嘴", "东方明珠", "浦东", "世纪公园")):
        return "sh_pudong"
    if "虹口" in district or any(token in text for token in ("北外滩", "外白渡桥", "虹口", "四川北路")):
        return "sh_north_bund"
    if "长宁" in district or "愚园路" in text:
        return "sh_changning"
    if any(token in text for token in ("西岸", "龙腾大道", "徐汇滨江")):
        return "sh_west_bund"
    if "徐汇" in district or any(token in text for token in ("衡山路", "安福路", "武康路", "太原路", "徐家汇", "肇嘉浜")):
        return "sh_xuhui"
    if "静安" in district or any(token in text for token in ("静安", "南京西路", "昌平路", "张园")):
        return "sh_jingan"
    if "黄浦" in district:
        if lon >= 121.485 or lat >= 31.245:
            return "sh_north_bund"
        return "sh_bund_people_square"
    return "sh_jingan"


def assign_cluster(poi: dict[str, Any]) -> str:
    city = str(poi.get("city") or "")
    if city == "广州":
        return _cluster_guangzhou(poi)
    if city == "上海":
        return _cluster_shanghai(poi)
    return "unknown"


def enrich(pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for poi in pois:
        item = dict(poi)
        cluster = assign_cluster(item)
        label = AREA_LABELS.get(cluster, cluster)
        item["area_cluster"] = cluster
        item["area_label"] = label
        item["business_area"] = item.get("business_area") or label
        enriched.append(item)
    return enriched


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enrich POIs with local route area clusters.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_INPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pois = load_json(args.input)
    enriched = enrich(pois)
    save_json(args.output, enriched)
    counts: dict[str, int] = {}
    for item in enriched:
        cluster = str(item.get("area_cluster") or "unknown")
        counts[cluster] = counts.get(cluster, 0) + 1
    print(json.dumps({"input": str(args.input), "output": str(args.output), "total_pois": len(enriched), "clusters": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
