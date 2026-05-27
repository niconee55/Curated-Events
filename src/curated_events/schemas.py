"""Public data model definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class EventCandidate:
    title: str
    category: str
    source_name: str
    start_dt: datetime
    entity: Optional[str] = None
    end_dt: Optional[datetime] = None
    venue_name: Optional[str] = None
    venue_city: Optional[str] = None
    venue_country: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    ticket_url: Optional[str] = None
    description: Optional[str] = None
    source_event_id: Optional[str] = None
    raw_confidence: float = 0.5

    def __post_init__(self):
        if not (0.0 <= self.raw_confidence <= 1.0):
            raise ValueError("raw_confidence must be between 0.0 and 1.0")
