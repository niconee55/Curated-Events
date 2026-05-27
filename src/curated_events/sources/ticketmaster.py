"""Ticketmaster discovery adapter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx

from ..schemas import EventCandidate


def _format_tm_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TicketmasterSource:
    def __init__(self, api_key: str | None, days_ahead: int = 60):
        self.api_key = api_key
        self.days_ahead = days_ahead
        self.base_url = "https://app.ticketmaster.com/discovery/v2/events.json"

    def _window(self):
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=self.days_ahead)
        return start, end

    def _build_request(self, keyword: str, classification_name: str | None = None):
        if not self.api_key:
            return None
        start, end = self._window()
        params = {
            "apikey": self.api_key,
            "keyword": keyword,
            "startDateTime": _format_tm_datetime(start),
            "endDateTime": _format_tm_datetime(end),
            "size": 50,
        }
        if classification_name:
            params["classificationName"] = classification_name
        return params

    def fetch(self, keyword: str, classification_name: str | None = None) -> List[EventCandidate]:
        params = self._build_request(keyword, classification_name=classification_name)
        if params is None:
            return []

        with httpx.Client(timeout=10) as client:
            resp = client.get(self.base_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        events = data.get("_embedded", {}).get("events", []) if data else []
        category = classification_name or keyword
        candidates: List[EventCandidate] = []
        for ev in events:
            parsed = _parse_event(ev, category)
            if parsed is not None:
                candidates.append(parsed)
        return candidates

    def fetch_soccer(self) -> List[EventCandidate]:
        return self.fetch(keyword="soccer", classification_name="Soccer")

    def fetch_concerts(self, artist: str) -> List[EventCandidate]:
        return self.fetch(keyword=artist, classification_name="Music")


def _parse_event(ev: dict, category: str) -> Optional[EventCandidate]:
    start_dt = ev.get("dates", {}).get("start", {}).get("dateTime")
    if not start_dt:
        return None

    venue = city = country = None
    venues = ev.get("_embedded", {}).get("venues", [])
    if venues:
        venue_data = venues[0]
        venue = venue_data.get("name")
        city = venue_data.get("city", {}).get("name")
        country = venue_data.get("country", {}).get("name")

    price_ranges = ev.get("priceRanges", [])
    price_min = price_ranges[0].get("min") if price_ranges else None
    price_max = price_ranges[0].get("max") if price_ranges else None

    return EventCandidate(
        title=ev.get("name", ""),
        category=category,
        entity=None,
        start_dt=datetime.fromisoformat(start_dt.replace("Z", "+00:00")),
        end_dt=None,
        venue_name=venue,
        venue_city=city,
        venue_country=country,
        price_min=price_min,
        price_max=price_max,
        ticket_url=ev.get("url"),
        description=ev.get("info") or ev.get("pleaseNote"),
        source_name="ticketmaster",
        source_event_id=ev.get("id"),
        raw_confidence=0.6,
    )
