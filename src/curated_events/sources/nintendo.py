"""Nintendo-focused source."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import httpx

from ..schemas import EventCandidate


class NintendoSource:
    NEWS_URL = "https://www.nintendo.com/us/whatsnew/"

    def fetch(self) -> List[EventCandidate]:
        # Conservative parser: best effort live scrape with graceful fallback.
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(self.NEWS_URL)
                resp.raise_for_status()
                text = resp.text
        except httpx.HTTPError:
            return []

        now = datetime.now(timezone.utc)
        candidates: List[EventCandidate] = []
        for title in _extract_titles(text):
            candidates.append(
                EventCandidate(
                    title=title,
                    category="Nintendo",
                    entity="Nintendo",
                    start_dt=now,
                    description="Nintendo announcement or release page item",
                    source_name="nintendo_news",
                    source_event_id=title,
                    raw_confidence=0.55,
                )
            )
        return candidates[:10]


def _extract_titles(html: str) -> List[str]:
    # Minimal extraction using a conservative heuristic instead of brittle selectors.
    titles: List[str] = []
    for line in html.splitlines():
        marker = ">"
        if marker not in line or "<a " not in line.lower():
            continue
        stripped = line.strip()
        if not stripped.startswith("<a"):
            continue
        if "</a>" in stripped:
            title = stripped.split(">", 1)[1].split("<", 1)[0].strip()
            if title:
                titles.append(title)
    return titles
