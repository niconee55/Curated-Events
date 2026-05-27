"""Anime-focused sources."""

from __future__ import annotations

from datetime import datetime
from typing import List

from ..schemas import EventCandidate


class AnimeSource:
    """Placeholder source for anime premieres and releases."""

    def fetch(self) -> List[EventCandidate]:
        # Keep deterministic and lightweight when scraping isn't configured.
        return []

    def static_premiere(self, title: str, date: datetime, description: str | None = None) -> EventCandidate:
        return EventCandidate(
            title=title,
            category="Anime",
            entity=title,
            start_dt=date,
            description=description,
            source_name="anime_manual",
            raw_confidence=0.4,
        )
