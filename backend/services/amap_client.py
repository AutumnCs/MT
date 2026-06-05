"""Shared GaoDe Web API client helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx


AMAP_KEY = os.getenv("AMAP_KEY") or os.getenv("AMAP_WEB_KEY", "")
AMAP_BASE_URL = os.getenv("AMAP_WEB_BASE_URL", "https://restapi.amap.com").rstrip("/")
AMAP_TIMEOUT_SECONDS = float(os.getenv("AMAP_WEB_TIMEOUT_SECONDS", "10"))


@dataclass
class AmapClient:
    key: str = AMAP_KEY
    base_url: str = AMAP_BASE_URL
    timeout_seconds: float = AMAP_TIMEOUT_SECONDS

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {}
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        resp = httpx.get(url, params=params, timeout=self.timeout_seconds)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {}

    def geocode(self, address: str, city: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "key": self.key,
            "address": address,
            "output": "JSON",
        }
        if city:
            params["city"] = city
        return self._get("/v3/geocode/geo", params)

    def search_poi(
        self,
        keyword: str,
        city: str | None = None,
        *,
        page: int = 1,
        offset: int = 5,
        types: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "key": self.key,
            "keywords": keyword,
            "output": "JSON",
            "page": page,
            "offset": offset,
        }
        if city:
            params["city"] = city
        if types:
            params["types"] = types
        return self._get("/v3/place/text", params)

    def poi_detail(self, poi_id: str) -> dict[str, Any]:
        params = {"key": self.key, "id": poi_id, "output": "JSON"}
        return self._get("/v3/place/detail", params)

