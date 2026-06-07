"""Map service wrapper with Tianditu Web API support and local fallback."""

from __future__ import annotations

import math
import os
import json
from typing import Any
import xml.etree.ElementTree as ET

from core.map_schemas import MapApiResponse, MapStatusResponse, RouteInfo
from core.schemas import POI
from services.tianditu_client import TiandituClient


TDT_KEY = (
    os.getenv("TDT_SERVER_KEY")
    or os.getenv("TDT_SERVICE_KEY")
    or os.getenv("TDT_WEB_KEY")
    or os.getenv("TDT_TOKEN", "")
)
TDT_BASE_URL = (
    os.getenv("TDT_SERVER_BASE_URL")
    or os.getenv("TDT_SERVICE_BASE_URL")
    or os.getenv("TDT_WEB_BASE_URL")
    or "http://api.tianditu.gov.cn"
).rstrip("/")
TDT_TIMEOUT_SECONDS = float(os.getenv("TDT_WEB_TIMEOUT_SECONDS", "10"))
TDT_REFERER = os.getenv("TDT_REFERER") or os.getenv("TDT_HTTP_REFERER") or ""

_CLIENT = TiandituClient(
    key=TDT_KEY,
    base_url=TDT_BASE_URL,
    timeout_seconds=TDT_TIMEOUT_SECONDS,
    referer=TDT_REFERER,
)
_ROUTE_CACHE: dict[tuple[str, str, float, float, float, float], RouteInfo] = {}
_MARKER_RESOLVE_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}
_API_CALL_COUNT: dict[str, int] = {"search_v2": 0, "geocode": 0, "reverse_geocode": 0, "drive": 0}
_LAST_API_ERRORS: dict[str, str] = {}
_LAST_API_RESPONSES: dict[str, str] = {}


def is_enabled() -> bool:
    return bool(TDT_KEY)


def _record_tdt_call(service: str) -> None:
    _API_CALL_COUNT[service] = _API_CALL_COUNT.get(service, 0) + 1


def _record_tdt_error(service: str, error: Exception | str) -> None:
    _LAST_API_ERRORS[service] = str(error)


def _record_tdt_response(service: str, raw: Any) -> None:
    text = str(raw or "").strip().replace("\n", " ")
    if len(text) > 500:
        text = f"{text[:500]}..."
    _LAST_API_RESPONSES[service] = text


def get_diagnostics() -> dict[str, Any]:
    return {
        "calls": dict(_API_CALL_COUNT),
        "last_errors": dict(_LAST_API_ERRORS),
        "last_responses": dict(_LAST_API_RESPONSES),
        "route_cache_size": len(_ROUTE_CACHE),
        "marker_resolve_cache_size": len(_MARKER_RESOLVE_CACHE),
    }


def get_status() -> MapStatusResponse:
    return MapStatusResponse(
        provider="tdt",
        enabled=is_enabled(),
        has_key=bool(TDT_KEY),
        base_url=TDT_BASE_URL,
        supported_modes=["walking", "driving"],
        diagnostics=get_diagnostics(),
        note=None
        if is_enabled()
        else "TDT_SERVER_KEY/TDT_SERVICE_KEY/TDT_WEB_KEY/TDT_TOKEN is not configured; local fallback is used.",
    )


def _api_response(
    *,
    success: bool,
    data: dict[str, Any] | None = None,
    message: str | None = None,
    enabled: bool | None = None,
    provider: str = "tdt",
) -> MapApiResponse:
    return MapApiResponse(
        provider=provider,
        enabled=is_enabled() if enabled is None else enabled,
        success=success,
        message=message,
        data=data or {},
    )


def _parse_location(value: Any) -> tuple[float | None, float | None]:
    if not isinstance(value, str) or "," not in value:
        return None, None
    try:
        lng, lat = [float(part) for part in value.split(",", 1)]
        return lat, lng
    except (TypeError, ValueError):
        return None, None


def _parse_tdt_location(raw: dict[str, Any]) -> tuple[float | None, float | None]:
    location = raw.get("location") or (raw.get("result") or {}).get("location") or {}
    if not isinstance(location, dict):
        return None, None
    try:
        lng = float(location.get("lon") if location.get("lon") is not None else location.get("lng"))
        lat = float(location.get("lat"))
        return lat, lng
    except (TypeError, ValueError):
        return None, None


def _tdt_success(raw: dict[str, Any]) -> bool:
    status = raw.get("status")
    if status is None:
        return bool(raw)
    return str(status) in {"0", "200", "OK", "success"}


def _parse_tdt_poi_location(record: dict[str, Any]) -> tuple[float | None, float | None]:
    for lng_key, lat_key in (("lon", "lat"), ("longitude", "latitude"), ("lng", "lat")):
        try:
            if record.get(lng_key) is not None and record.get(lat_key) is not None:
                return float(record[lat_key]), float(record[lng_key])
        except (TypeError, ValueError):
            pass
    location = record.get("lonlat") or record.get("location")
    if isinstance(location, str):
        return _parse_location(location)
    return None, None


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _is_supported_city(city: str) -> bool:
    text = _normalize_text(city)
    return "上海" in text or "广州" in text


def _coord_value(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result == 0:
        return None
    return result


def _candidate_score(record: dict[str, Any], marker: dict[str, Any]) -> int:
    marker_name = _normalize_text(marker.get("name"))
    marker_address = _normalize_text(marker.get("address"))
    marker_city = _normalize_text(marker.get("city"))
    record_name = _normalize_text(record.get("name"))
    record_address = _normalize_text(record.get("address"))
    record_area = _normalize_text(record.get("county") or record.get("area") or record.get("city"))

    score = 0
    if marker_name and record_name:
        if marker_name == record_name:
            score += 8
        elif marker_name in record_name or record_name in marker_name:
            score += 4
    if marker_address and record_address:
        if marker_address == record_address:
            score += 5
        elif marker_address in record_address or record_address in marker_address:
            score += 2
    if marker_city and (marker_city in record_address or marker_city in record_area):
        score += 2
    if _parse_tdt_poi_location(record) != (None, None):
        score += 1
    return score


def _resolve_marker_with_tdt(marker: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(marker)
    resolved["coordinate_source"] = "local"
    resolved["resolved_by"] = "local"

    if not is_enabled():
        return resolved

    city = _normalize_text(marker.get("city"))
    name = _normalize_text(marker.get("name"))
    address = _normalize_text(marker.get("address"))
    if not name or not city or not _is_supported_city(city):
        return resolved

    cache_key = (city, name, address)
    if cache_key in _MARKER_RESOLVE_CACHE:
        cached = dict(_MARKER_RESOLVE_CACHE[cache_key])
        cached["label"] = marker.get("label")
        cached["id"] = marker.get("id")
        cached["category"] = marker.get("category")
        return cached

    original_lat = _coord_value(marker.get("latitude"))
    original_lng = _coord_value(marker.get("longitude"))
    if original_lat is not None and original_lng is not None:
        resolved["original_latitude"] = original_lat
        resolved["original_longitude"] = original_lng

    try:
        _record_tdt_call("search_v2")
        raw = _CLIENT.search_poi(name, city=city, offset=8)
        records = raw.get("pois") or []
        candidates = [record for record in records if isinstance(record, dict)]
        candidates.sort(key=lambda record: _candidate_score(record, marker), reverse=True)
        for record in candidates:
            lat, lng = _parse_tdt_poi_location(record)
            if lat is None or lng is None:
                continue
            resolved.update(
                {
                    "latitude": lat,
                    "longitude": lng,
                    "address": record.get("address") or address,
                    "district": record.get("county") or record.get("area"),
                    "provider": "tdt",
                    "provider_poi_id": record.get("hotPointID") or record.get("id"),
                    "coordinate_source": "tdt_search",
                    "resolved_by": "tdt_search",
                    "resolved_name": record.get("name") or name,
                }
            )
            _MARKER_RESOLVE_CACHE[cache_key] = dict(resolved)
            return resolved
    except Exception as exc:
        _record_tdt_error("search_v2", exc)

    try:
        geocode_keyword = address or name
        _record_tdt_call("geocode")
        raw = _CLIENT.geocode(geocode_keyword, city)
        lat, lng = _parse_tdt_location(raw)
        if lat is not None and lng is not None:
            result = raw.get("result") if isinstance(raw.get("result"), dict) else {}
            resolved.update(
                {
                    "latitude": lat,
                    "longitude": lng,
                    "address": result.get("formatted_address") or result.get("address") or address,
                    "provider": "tdt",
                    "coordinate_source": "tdt_geocode",
                    "resolved_by": "tdt_geocode",
                }
            )
            _MARKER_RESOLVE_CACHE[cache_key] = dict(resolved)
            return resolved
    except Exception as exc:
        _record_tdt_error("geocode", exc)

    _MARKER_RESOLVE_CACHE[cache_key] = dict(resolved)
    return resolved


def _parse_route_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        digits = "".join(ch for ch in text if ch.isdigit() or ch == ".")
        try:
            return float(digits) if digits else None
        except ValueError:
            return None


def _parse_route_polyline(value: Any) -> list[dict[str, float]]:
    if not value:
        return []
    text = str(value).replace("|", ";").strip()
    points: list[dict[str, float]] = []
    for chunk in text.split(";"):
        if "," not in chunk:
            continue
        try:
            lng, lat = [float(part) for part in chunk.split(",", 1)]
        except ValueError:
            continue
        points.append({"latitude": lat, "longitude": lng})
    return points


def _collect_route_values(value: Any, values: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    if values is None:
        values = {}
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                _collect_route_values(item, values)
            elif item is not None:
                values.setdefault(str(key).lower(), []).append(str(item))
    elif isinstance(value, list):
        for item in value:
            _collect_route_values(item, values)
    return values


def _route_info_from_values(values: dict[str, list[str]]) -> RouteInfo:
    line_text = next(
        (
            item
            for key in ("routelatlon", "route_lnglats", "lnglats", "points", "path", "polyline")
            for item in values.get(key, [])
            if "," in item
        ),
        "",
    )
    polyline = _parse_route_polyline(line_text)

    distance = next(
        (
            _parse_route_number(item)
            for key in ("distance", "routedistance", "totaldistance", "dis")
            for item in values.get(key, [])
            if _parse_route_number(item) is not None
        ),
        None,
    )
    duration = next(
        (
            _parse_route_number(item)
            for key in ("duration", "time", "routetime", "totaltime")
            for item in values.get(key, [])
            if _parse_route_number(item) is not None
        ),
        None,
    )

    distance_km = 0.0
    if distance is not None:
        distance_km = round(distance / 1000.0, 2) if distance > 100 else round(distance, 2)

    duration_min = 0
    if duration is not None:
        duration_min = int(round(duration / 60.0)) if duration > 300 else int(round(duration))

    return RouteInfo(distance_km=distance_km, duration_min=duration_min, steps=[], polyline=polyline)


def _parse_tdt_drive_route(raw_text: str) -> RouteInfo:
    stripped = raw_text.strip()
    if not stripped:
        return RouteInfo()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return _route_info_from_values(_collect_route_values(json.loads(stripped)))
        except (TypeError, ValueError, json.JSONDecodeError):
            return RouteInfo()

    try:
        root = ET.fromstring(stripped)
    except ET.ParseError:
        return RouteInfo()

    values: dict[str, list[str]] = {}
    for element in root.iter():
        tag = element.tag.split("}")[-1].lower()
        text = (element.text or "").strip()
        if text:
            values.setdefault(tag, []).append(text)

    return _route_info_from_values(values)


def _tdt_drive_route(origin: POI, destination: POI) -> RouteInfo:
    if not is_enabled():
        return RouteInfo()
    try:
        _record_tdt_call("drive")
        raw = _CLIENT.driving_route(origin.lng, origin.lat, destination.lng, destination.lat)
        _record_tdt_response("drive", raw)
        route = _parse_tdt_drive_route(raw)
        if route.distance_km <= 0 and route.duration_min <= 0 and len(route.polyline) < 2:
            _record_tdt_error("drive", "Tianditu drive returned no usable route; see diagnostics.last_responses.drive.")
        return route
    except Exception as exc:
        _record_tdt_error("drive", exc)
        return RouteInfo()


def geocode(address: str, city: str | None = None) -> MapApiResponse:
    if not is_enabled():
        return _api_response(success=False, message="Tianditu key is not configured.", enabled=False)
    try:
        _record_tdt_call("geocode")
        raw = _CLIENT.geocode(address, city)
        lat, lng = _parse_tdt_location(raw)
        result = raw.get("result") if isinstance(raw.get("result"), dict) else {}
        items = []
        if lat is not None and lng is not None:
            items.append(
                {
                    "formatted_address": result.get("formatted_address") or result.get("address") or address,
                    "province": None,
                    "city": city,
                    "district": None,
                    "adcode": result.get("addressComponent", {}).get("county_code") if isinstance(result.get("addressComponent"), dict) else None,
                    "latitude": lat,
                    "longitude": lng,
                    "raw": raw,
                }
            )
        return _api_response(
            success=_tdt_success(raw) and bool(items),
            data={"items": items, "count": len(items), "raw_status": raw.get("status")},
            message=raw.get("msg") if not _tdt_success(raw) else None,
        )
    except Exception as exc:
        _record_tdt_error("geocode", exc)
        return _api_response(success=False, message=str(exc))


def reverse_geocode(longitude: float, latitude: float) -> MapApiResponse:
    if not is_enabled():
        return _api_response(success=False, message="Tianditu key is not configured.", enabled=False)
    try:
        _record_tdt_call("reverse_geocode")
        raw = _CLIENT.reverse_geocode(longitude, latitude)
        result = raw.get("result") if isinstance(raw.get("result"), dict) else {}
        return _api_response(
            success=_tdt_success(raw) and bool(result),
            data={
                "formatted_address": result.get("formatted_address") or result.get("formatted_address") or result.get("address"),
                "address_component": result.get("addressComponent") or {},
                "raw_status": raw.get("status"),
            },
            message=raw.get("msg") if not _tdt_success(raw) else None,
        )
    except Exception as exc:
        _record_tdt_error("reverse_geocode", exc)
        return _api_response(success=False, message=str(exc))


def search_poi(
    keyword: str,
    *,
    city: str | None = None,
    location: str | None = None,
    radius: int = 1000,
    types: str | None = None,
    limit: int = 10,
) -> MapApiResponse:
    if not is_enabled():
        return _api_response(success=False, message="Tianditu key is not configured.", enabled=False)
    try:
        _record_tdt_call("search_v2")
        raw = _CLIENT.search_poi(
            keyword,
            city=city,
            offset=max(1, min(limit, 25)),
            location=location,
            radius=radius,
        )
        records = raw.get("pois") or []
        items: list[dict[str, Any]] = []
        for record in records[:limit]:
            lat, lng = _parse_tdt_poi_location(record)
            items.append(
                {
                    "provider": "tdt",
                    "provider_poi_id": record.get("hotPointID") or record.get("id"),
                    "name": record.get("name"),
                    "type": record.get("typeName") or record.get("type"),
                    "typecode": record.get("typeCode"),
                    "city": city,
                    "district": record.get("county") or record.get("area"),
                    "address": record.get("address"),
                    "adcode": record.get("countyCode"),
                    "latitude": lat,
                    "longitude": lng,
                    "raw": record,
                }
            )
        return _api_response(
            success=_tdt_success(raw) and bool(items),
            data={"items": items, "count": len(items), "raw_status": raw.get("status")},
            message=raw.get("msg") if not _tdt_success(raw) else None,
        )
    except Exception as exc:
        _record_tdt_error("search_v2", exc)
        return _api_response(success=False, message=str(exc))


def get_route(origin: POI, destination: POI) -> RouteInfo:
    cache_key = (
        origin.id,
        destination.id,
        round(origin.lat, 6),
        round(origin.lng, 6),
        round(destination.lat, 6),
        round(destination.lng, 6),
    )
    if cache_key in _ROUTE_CACHE:
        return _ROUTE_CACHE[cache_key]

    result = _tdt_drive_route(origin, destination)
    if result.distance_km <= 0 and result.duration_min <= 0 and len(result.polyline) < 2:
        result = _fallback_estimate(origin, destination)
        if is_enabled():
            return result
    _ROUTE_CACHE[cache_key] = result
    return result


def estimate_travel_between_pois(origin: POI, destination: POI, mode: str = "walking") -> dict[str, Any]:
    route = get_route(origin, destination)
    return {
        "provider": "tdt" if is_enabled() and route.polyline else "local",
        "enabled": is_enabled(),
        "success": True,
        "message": None,
        "travel": {
            "mode": mode or "walking",
            "distance_km": route.distance_km,
            "duration_min": route.duration_min,
            "cost": 0,
            "source": "tdt_drive" if is_enabled() and route.polyline else "local",
            "steps": route.steps,
            "polyline": route.polyline,
            "diagnostics": get_diagnostics(),
        },
    }


def _fallback_estimate(origin: POI, destination: POI) -> RouteInfo:
    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        value = (math.sin(delta_phi / 2) ** 2) + (
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))

    dist_km = haversine(origin.lat, origin.lng, destination.lat, destination.lng)
    return RouteInfo(distance_km=round(dist_km, 2), duration_min=int(round(dist_km * 12)), steps=[])


def _route_stops(route: Any) -> list[Any]:
    if route is None:
        return []
    if isinstance(route, dict):
        stops = route.get("main_stops") or route.get("stops") or []
        return list(stops) if isinstance(stops, list) else []
    main_stops = getattr(route, "main_stops", None)
    if main_stops:
        return list(main_stops)
    extra = getattr(route, "model_extra", None) or {}
    stops = extra.get("main_stops") or extra.get("stops") or []
    return list(stops) if isinstance(stops, list) else []


def _poi_from_stop(stop: Any) -> dict[str, Any]:
    if isinstance(stop, dict):
        poi = stop.get("poi") or {}
    else:
        poi = getattr(stop, "poi", None)
    if hasattr(poi, "model_dump"):
        return poi.model_dump(mode="json")
    return dict(poi) if isinstance(poi, dict) else {}


def _value_from_stop(stop: Any, key: str, default: Any = None) -> Any:
    if isinstance(stop, dict):
        return stop.get(key, default)
    return getattr(stop, key, default)


def _bounds(markers: list[dict[str, Any]]) -> dict[str, float | None]:
    lats = [float(item["latitude"]) for item in markers if item.get("latitude") is not None]
    lngs = [float(item["longitude"]) for item in markers if item.get("longitude") is not None]
    if not lats or not lngs:
        return {"min_latitude": None, "max_latitude": None, "min_longitude": None, "max_longitude": None}
    return {
        "min_latitude": min(lats),
        "max_latitude": max(lats),
        "min_longitude": min(lngs),
        "max_longitude": max(lngs),
    }


def _route_preview_polyline(markers: list[dict[str, Any]]) -> tuple[list[dict[str, float]], str]:
    if is_enabled():
        route_points: list[dict[str, float]] = []
        real_segments = 0
        approximate_segments = 0
        valid = [
            item
            for item in markers
            if item.get("latitude") is not None and item.get("longitude") is not None
        ]
        for index in range(len(valid) - 1):
            origin = _marker_to_poi(valid[index], f"route-origin-{index}")
            destination = _marker_to_poi(valid[index + 1], f"route-destination-{index}")
            route = get_route(origin, destination)
            segment_points = route.polyline
            if len(segment_points) < 2:
                segment_points = _approximate_segment_polyline(valid[index], valid[index + 1], index)
                approximate_segments += 1
            else:
                real_segments += 1
            if route_points and segment_points:
                route_points.extend(segment_points[1:])
            else:
                route_points.extend(segment_points)
        if len(route_points) > 1:
            if real_segments and approximate_segments:
                return route_points, "tdt_drive_mixed"
            if real_segments:
                return route_points, "tdt_drive"
            return route_points, "local_approx"

    points: list[dict[str, float]] = []
    valid_markers = [
        item
        for item in markers
        if item.get("latitude") is not None and item.get("longitude") is not None
    ]

    for index, start in enumerate(valid_markers):
        start_point = {
            "latitude": float(start["latitude"]),
            "longitude": float(start["longitude"]),
        }
        if not points:
            points.append(start_point)

        if index >= len(valid_markers) - 1:
            continue

        end = valid_markers[index + 1]
        points.extend(_approximate_segment_polyline(start, end, index)[1:])

    return points, "local_approx"


def _marker_to_poi(marker: dict[str, Any], fallback_id: str) -> POI:
    return POI(
        id=str(marker.get("id") or fallback_id),
        name=str(marker.get("name") or fallback_id),
        category=str(marker.get("category") or "custom"),
        city=str(marker.get("city") or ""),
        address=str(marker.get("address") or ""),
        latitude=float(marker["latitude"]),
        longitude=float(marker["longitude"]),
    )


def _approximate_segment_polyline(
    start: dict[str, Any],
    end: dict[str, Any],
    index: int,
) -> list[dict[str, float]]:
    start_lat = float(start["latitude"])
    start_lng = float(start["longitude"])
    end_lat = float(end["latitude"])
    end_lng = float(end["longitude"])
    delta_lat = end_lat - start_lat
    delta_lng = end_lng - start_lng
    elbow_lng = start_lng + delta_lng * (0.42 if index % 2 == 0 else 0.58)
    elbow_lat = start_lat + delta_lat * (0.58 if index % 2 == 0 else 0.42)
    return [
        {"latitude": start_lat, "longitude": start_lng},
        {"latitude": start_lat, "longitude": elbow_lng},
        {"latitude": elbow_lat, "longitude": elbow_lng},
        {"latitude": elbow_lat, "longitude": start_lng + delta_lng * 0.84},
        {"latitude": end_lat, "longitude": end_lng},
    ]


def _preview_coordinate_source(markers: list[dict[str, Any]]) -> str:
    sources = {_normalize_text(marker.get("coordinate_source")) for marker in markers}
    sources.discard("")
    if not sources:
        return "local"
    if sources == {"tdt_search"}:
        return "tdt_search"
    if sources <= {"tdt_search", "tdt_geocode"} and sources:
        return "tdt_resolved"
    if any(source.startswith("tdt_") for source in sources):
        return "tdt_mixed"
    return "local"


def build_route_preview(route: Any) -> dict[str, Any]:
    stops = _route_stops(route)
    markers: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []

    for index, stop in enumerate(stops):
        poi = _poi_from_stop(stop)
        lat = poi.get("latitude")
        lng = poi.get("longitude")
        marker = {
            "id": poi.get("id") or f"point-{index + 1}",
            "name": poi.get("name") or f"Point {index + 1}",
            "category": poi.get("category") or "custom",
            "city": poi.get("city") or "",
            "latitude": lat,
            "longitude": lng,
            "label": index + 1,
            "address": poi.get("address") or "",
        }
        markers.append(_resolve_marker_with_tdt(marker))

        if index > 0:
            previous = stops[index - 1]
            segments.append(
                {
                    "mode": "walking",
                    "distance_km": _value_from_stop(previous, "travel_to_next_km", 0.0),
                    "duration_min": _value_from_stop(previous, "travel_to_next_min", 0),
                    "cost": 0,
                    "source": "local",
                }
            )

    polyline, polyline_source = _route_preview_polyline(markers)

    center = None
    if polyline:
        center = {
            "latitude": sum(item["latitude"] for item in polyline) / len(polyline),
            "longitude": sum(item["longitude"] for item in polyline) / len(polyline),
        }

    title = getattr(route, "title", None) if route is not None else None
    summary = getattr(route, "summary", None) if route is not None else None
    if isinstance(route, dict):
        title = route.get("title") or title
        summary = route.get("summary") or summary

    return {
        "provider": "tdt" if is_enabled() else "local",
        "enabled": is_enabled(),
        "mode": "driving" if is_enabled() else "walking",
        "polyline_source": polyline_source,
        "coordinate_source": _preview_coordinate_source(markers),
        "diagnostics": get_diagnostics(),
        "route_title": title or "route-preview",
        "route_summary": summary or "",
        "center": center,
        "bounds": _bounds(markers),
        "markers": markers,
        "polyline": polyline,
        "segments": segments,
        "point_count": len(markers),
    }
