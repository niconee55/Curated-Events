"""Deduplication helpers."""

from __future__ import annotations

from datetime import datetime
import hashlib


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def build_dedupe_key(title: str, start_dt: datetime, venue_name: str | None) -> str:
    base = f"{normalize(title)}|{start_dt.isoformat()}|{normalize(venue_name) if venue_name else ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]
