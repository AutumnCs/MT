"""Validate and enrich local POIs with GaoDe Web API facts."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.amap_client import AmapClient


DEFAULT_INPUT = ROOT / "pois.json"
DEFAULT_OUTPUT = ROOT / "pois.amap.enriched.json"
DEFAULT_REPORT = ROOT / "pois.amap.report.json"


def _norm(text: Any) -> str:
    return "".join(str(text or "").lower().split())


def _similarity(left: Any, right: Any) -> float:
    left_text = _norm(left)
    right_text = _norm(right)
    if not left_text and not right_text:
        return 1.0
    if not left_text or not right_text:
        return 0.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class SyncResult:
    id: str
    name: str
    city: str
    status: str
    confidence: float
    amap_id: str | None = None
    amap_name: str | None = None
    amap_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    adcode: str | None = None
    notes: str | None = None


def _choose_search_hit(records: list[dict[str, Any]], poi: dict[str, Any]) -> dict[str, Any] | None:
    if not records:
        return None
    best = None
    best_score = -1.0
    for record in records:
        score = 0.0
        score += _similarity(record.get("name"), poi.get("name")) * 0.55
        score += _similarity(record.get("address"), poi.get("address")) * 0.30
        score += _similarity(record.get("cityname"), poi.get("city")) * 0.15
        if score > best_score:
            best_score = score
            best = record
    if best_score < 0.55:
        return None
    return best


def _parse_location(value: str | None) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    try:
        lng, lat = [float(part) for part in value.split(",", 1)]
        return lat, lng
    except Exception:
        return None, None


def _geocode_record(client: AmapClient, poi: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    address = str(poi.get("address") or "").strip()
    if not address:
        return None, "missing address"

    response = client.geocode(address, city=str(poi.get("city") or "").strip() or None)
    geocodes = response.get("geocodes") or []
    if not geocodes:
        return None, "no geocode result"
    hit = geocodes[0]
    lat, lng = _parse_location(hit.get("location"))
    return (
        {
            "provider": "amap",
            "provider_poi_id": hit.get("id"),
            "adcode": hit.get("adcode"),
            "amap_name": hit.get("formatted_address") or poi.get("name"),
            "amap_address": hit.get("formatted_address") or poi.get("address"),
            "latitude": lat,
            "longitude": lng,
            "geocoded_confidence": 0.85 if lat is not None and lng is not None else 0.6,
            "source_updated_at": _now_iso(),
        },
        "geocode",
    )


def _search_record(client: AmapClient, poi: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    keyword = str(poi.get("name") or "").strip()
    if not keyword:
        return None, "missing name"
    response = client.search_poi(keyword, city=str(poi.get("city") or "").strip() or None)
    pois = response.get("pois") or []
    hit = _choose_search_hit(pois, poi)
    if not hit:
        return None, "no search match"
    lat, lng = _parse_location(hit.get("location"))
    return (
        {
            "provider": "amap",
            "provider_poi_id": hit.get("id"),
            "adcode": hit.get("adcode"),
            "amap_name": hit.get("name"),
            "amap_address": hit.get("address"),
            "latitude": lat,
            "longitude": lng,
            "geocoded_confidence": 0.9 if lat is not None and lng is not None else 0.7,
            "source_updated_at": _now_iso(),
        },
        "search",
    )


def enrich_poi(client: AmapClient, poi: dict[str, Any]) -> tuple[dict[str, Any], SyncResult]:
    enriched = dict(poi)
    status = "dry-run"
    confidence = 0.0
    amap_payload: dict[str, Any] | None = None
    notes: list[str] = []

    if client.enabled:
        search_payload, search_note = _search_record(client, poi)
        geocode_payload, geocode_note = _geocode_record(client, poi)

        candidates = [payload for payload in (search_payload, geocode_payload) if payload]
        if candidates:
            amap_payload = max(candidates, key=lambda item: float(item.get("geocoded_confidence") or 0.0))
            status = "matched"
            confidence = float(amap_payload.get("geocoded_confidence") or 0.0)
            notes.append(search_note if amap_payload is search_payload else geocode_note)
        else:
            status = "unmatched"
            notes.extend([search_note, geocode_note])
    else:
        notes.append("gaode key not configured; dry-run only")

    if amap_payload:
        for key in ("provider", "provider_poi_id", "adcode", "latitude", "longitude", "geocoded_confidence", "source_updated_at"):
            value = amap_payload.get(key)
            if value is not None:
                enriched[key] = value
        for key in ("amap_name", "amap_address"):
            value = amap_payload.get(key)
            if value:
                enriched[key] = value

    result = SyncResult(
        id=str(poi.get("id") or ""),
        name=str(poi.get("name") or ""),
        city=str(poi.get("city") or ""),
        status=status,
        confidence=round(confidence, 4),
        amap_id=str(amap_payload.get("provider_poi_id")) if amap_payload and amap_payload.get("provider_poi_id") else None,
        amap_name=str(amap_payload.get("name")) if amap_payload and amap_payload.get("name") else None,
        amap_address=str(amap_payload.get("address")) if amap_payload and amap_payload.get("address") else None,
        latitude=amap_payload.get("latitude") if amap_payload else None,
        longitude=amap_payload.get("longitude") if amap_payload else None,
        adcode=str(amap_payload.get("adcode")) if amap_payload and amap_payload.get("adcode") else None,
        notes="; ".join(note for note in notes if note),
    )
    return enriched, result


def load_pois(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("POI file must contain a JSON list.")
    return data


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and enrich local POIs with GaoDe facts.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input POI JSON file.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output enriched POI JSON file.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Output sync report JSON file.")
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N records.")
    parser.add_argument("--dry-run", action="store_true", help="Do not call GaoDe even if a key exists.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pois = load_pois(args.input)
    if args.limit and args.limit > 0:
        pois = pois[: args.limit]

    client = AmapClient()
    if args.dry_run:
        client = AmapClient(key="")

    enriched_pois: list[dict[str, Any]] = []
    report: list[dict[str, Any]] = []
    matched = 0
    unmatched = 0
    dry = 0

    for poi in pois:
        enriched, result = enrich_poi(client, poi)
        enriched_pois.append(enriched)
        report.append(asdict(result))
        if result.status == "matched":
            matched += 1
        elif result.status == "dry-run":
            dry += 1
        else:
            unmatched += 1

    summary = {
        "input": str(args.input),
        "output": str(args.output),
        "report": str(args.report),
        "total": len(pois),
        "matched": matched,
        "unmatched": unmatched,
        "dry_run": dry,
        "amap_enabled": client.enabled,
    }
    save_json(args.output, enriched_pois)
    save_json(args.report, {"summary": summary, "items": report})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
