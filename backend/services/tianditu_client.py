"""Shared Tianditu Web API client helpers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # Local-only planning and offline evaluation do not need the web client.
    httpx = None


TDT_KEY = (
    os.getenv("TDT_SERVER_KEY")
    or os.getenv("TDT_SERVICE_KEY")
    or os.getenv("TDT_WEB_KEY")
    or os.getenv("TDT_TOKEN")
    or ""
)
TDT_BASE_URL = (
    os.getenv("TDT_SERVER_BASE_URL")
    or os.getenv("TDT_SERVICE_BASE_URL")
    or os.getenv("TDT_WEB_BASE_URL")
    or "http://api.tianditu.gov.cn"
).rstrip("/")
TDT_TIMEOUT_SECONDS = float(os.getenv("TDT_WEB_TIMEOUT_SECONDS", "10"))
TDT_REFERER = os.getenv("TDT_REFERER") or os.getenv("TDT_HTTP_REFERER") or ""
TDT_USER_AGENT = os.getenv(
    "TDT_USER_AGENT",
    "MT-Route-Planner/1.0 (+local-dev)",
)


@dataclass
class TiandituClient:
    key: str = TDT_KEY
    base_url: str = TDT_BASE_URL
    timeout_seconds: float = TDT_TIMEOUT_SECONDS
    referer: str = TDT_REFERER
    user_agent: str = TDT_USER_AGENT

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": self.user_agent}
        if self.referer:
            headers["Referer"] = self.referer
        return headers

    def _request(self, path: str, params: dict[str, Any]) -> httpx.Response:
        if not self.enabled:
            raise RuntimeError("Tianditu key is not configured.")
        if httpx is None:
            raise RuntimeError("httpx is required when Tianditu Web API is enabled.")
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        payload = dict(params)
        payload["tk"] = self.key
        resp = httpx.get(url, params=payload, headers=self._headers(), timeout=self.timeout_seconds)
        if resp.status_code == 403 and url.startswith("https://api.tianditu.gov.cn/"):
            alt_url = url.replace("https://", "http://", 1)
            resp = httpx.get(alt_url, params=payload, headers=self._headers(), timeout=self.timeout_seconds)
        if resp.status_code >= 400:
            body = resp.text.strip().replace("\n", " ")
            if len(body) > 500:
                body = f"{body[:500]}..."
            raise httpx.HTTPStatusError(
                f"{resp.status_code} {resp.reason_phrase} for url '{resp.url}' body='{body}'",
                request=resp.request,
                response=resp,
            )
        return resp

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {}
        resp = self._request(path, params)
        data = resp.json()
        return data if isinstance(data, dict) else {}

    def _get_text(self, path: str, params: dict[str, Any]) -> str:
        if not self.enabled:
            return ""
        resp = self._request(path, params)
        return resp.text

    def geocode(self, address: str, city: str | None = None) -> dict[str, Any]:
        keyword = f"{city}{address}" if city and city not in address else address
        return self._get("/geocoder", {"ds": json.dumps({"keyWord": keyword}, ensure_ascii=False)})

    def reverse_geocode(self, longitude: float, latitude: float) -> dict[str, Any]:
        post_str = {
            "lon": longitude,
            "lat": latitude,
            "ver": 1,
        }
        return self._get(
            "/geocoder",
            {
                "postStr": json.dumps(post_str, ensure_ascii=False),
                "type": "geocode",
            },
        )

    def search_poi(
        self,
        keyword: str,
        city: str | None = None,
        *,
        page: int = 1,
        offset: int = 10,
        location: str | None = None,
        radius: int | None = None,
    ) -> dict[str, Any]:
        start = max(page - 1, 0) * max(offset, 1)
        post_str: dict[str, Any] = {
            "keyWord": keyword if not city else f"{city} {keyword}",
            "queryType": 1,
            "start": start,
            "count": max(1, min(offset, 25)),
            "level": 12,
        }
        if location and "," in location:
            try:
                lng, lat = [float(part) for part in location.split(",", 1)]
                delta = max((radius or 1000) / 111_000.0, 0.005)
                post_str["mapBound"] = f"{lng - delta},{lat - delta},{lng + delta},{lat + delta}"
            except ValueError:
                pass
        return self._get(
            "/v2/search",
            {
                "postStr": json.dumps(post_str, ensure_ascii=False),
                "type": "query",
            },
        )

    def driving_route(
        self,
        origin_longitude: float,
        origin_latitude: float,
        destination_longitude: float,
        destination_latitude: float,
        *,
        style: str = "0",
    ) -> str:
        post_str = {
            "orig": f"{origin_longitude},{origin_latitude}",
            "dest": f"{destination_longitude},{destination_latitude}",
            "style": style,
        }
        return self._get_text(
            "/drive",
            {
                "postStr": json.dumps(post_str, ensure_ascii=False),
                "type": "search",
            },
        )
