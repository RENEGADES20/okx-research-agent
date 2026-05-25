from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .models import MacroRelease


TRADING_ECONOMICS_BASE_URL = "https://api.tradingeconomics.com"


class MacroDataError(RuntimeError):
    pass


class TradingEconomicsCalendarClient:
    """Optional economic calendar client.

    Requires `TRADING_ECONOMICS_CLIENT` and `TRADING_ECONOMICS_SECRET`.
    The manual release API works without these credentials.
    """

    def __init__(self, client: str | None = None, secret: str | None = None, timeout: float = 10.0) -> None:
        self.client = client or os.environ.get("TRADING_ECONOMICS_CLIENT")
        self.secret = secret or os.environ.get("TRADING_ECONOMICS_SECRET")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.client and self.secret)

    def latest_calendar(self, *, country: str = "United States", limit: int = 50) -> list[MacroRelease]:
        if not self.configured:
            raise MacroDataError("Trading Economics credentials are not configured.")
        params = {
            "c": f"{self.client}:{self.secret}",
            "country": country,
            "format": "json",
        }
        country_path = quote(country)
        data = self._get_json(f"{TRADING_ECONOMICS_BASE_URL}/calendar/country/{country_path}", params)
        if not isinstance(data, list):
            return []
        releases = [_release_from_te(item) for item in data[:limit] if isinstance(item, dict)]
        return [release for release in releases if release is not None]

    def _get_json(self, url: str, params: dict[str, Any]) -> Any:
        request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "epi-agent-mvp/0.1"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise MacroDataError(str(exc)) from exc


def macro_release_from_payload(payload: dict[str, Any]) -> MacroRelease:
    return MacroRelease.build(
        event_name=str(payload["event_name"]),
        country=str(payload.get("country", "United States")),
        category=str(payload.get("category", "macro")),
        release_time=payload.get("release_time"),
        actual=_as_float(payload.get("actual")),
        forecast=_as_float(payload.get("forecast")),
        previous=_as_float(payload.get("previous")),
        unit=payload.get("unit"),
        source=str(payload.get("source", "manual")),
        source_url=payload.get("source_url"),
        surprise_std=_as_float(payload.get("surprise_std")),
        importance=int(payload.get("importance", 1)),
    )


def _release_from_te(item: dict[str, Any]) -> MacroRelease | None:
    event_name = item.get("Event") or item.get("event")
    if not event_name:
        return None
    return MacroRelease.build(
        event_name=str(event_name),
        country=str(item.get("Country") or item.get("country") or "United States"),
        category=str(item.get("Category") or item.get("category") or "macro"),
        release_time=item.get("Date") or item.get("date"),
        actual=_as_float(item.get("Actual") or item.get("actual")),
        forecast=_as_float(item.get("Forecast") or item.get("forecast")),
        previous=_as_float(item.get("Previous") or item.get("previous")),
        unit=item.get("Unit") or item.get("unit"),
        source="trading_economics",
        source_url=item.get("URL") or item.get("url"),
        importance=int(_as_float(item.get("Importance") or item.get("importance")) or 1),
    )


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.replace("%", "").replace(",", "").strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
