"""Discovery and persistence pipeline orchestration."""

from __future__ import annotations

from dataclasses import replace
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from collections import Counter
from typing import Callable, Optional

from sqlalchemy import select

from .config import get_settings
from .db import session_scope
from .description import build_description
from .dedupe import build_dedupe_key
from .models import Event, IngestionLog, Source
from .ranking import rank_candidate
from .schemas import EventCandidate
from .sources import TicketmasterSource, NintendoSource, AnimeSource


MIN_PRIORITY = 0.35


@dataclass
class PipelineResult:
    candidates: int = 0
    inserted: int = 0
    skipped_duplicate: int = 0
    skipped_low_confidence: int = 0
    synced_records: int = 0
    logs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, int | list[str]]:
        return {
            "candidates": self.candidates,
            "inserted": self.inserted,
            "skipped_duplicate": self.skipped_duplicate,
            "skipped_low_confidence": self.skipped_low_confidence,
            "synced_records": self.synced_records,
            "logs": self.logs,
        }


def _normalize_dt(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_candidate(candidate: EventCandidate) -> EventCandidate:
    start_dt = _normalize_dt(candidate.start_dt)
    if start_dt is None:
        return candidate
    end_dt = _normalize_dt(candidate.end_dt)
    if end_dt == candidate.end_dt and start_dt == candidate.start_dt:
        return candidate
    return replace(
        candidate,
        start_dt=start_dt,
        end_dt=end_dt,
    )


def _build_internal_event_id(candidate: EventCandidate, dedupe_key: str) -> str:
    source_name = candidate.source_name or "unknown"
    source_event = candidate.source_event_id or ""
    start_fragment = ""
    if candidate.start_dt is not None:
        start_fragment = candidate.start_dt.isoformat()
    if source_event:
        return f"{source_name}:{source_event}:{start_fragment}:{dedupe_key}"
    return f"{source_name}:{start_fragment}:{dedupe_key}"


def _get_or_create_source(session, name: str, source_type: str, base_url: str | None) -> Source:
    source = session.execute(select(Source).where(Source.name == name)).scalar_one_or_none()
    if source is None:
        source = Source(name=name, type=source_type, base_url=base_url)
        session.add(source)
        session.flush()
    return source


def _make_default_sources() -> list[tuple[str, Callable[[], list[EventCandidate]]]]:
    settings = get_settings()
    ticketmaster = TicketmasterSource(api_key=settings.ticketmaster_api_key, days_ahead=settings.discovery_days_ahead)
    nintendo = NintendoSource()
    anime = AnimeSource()

    return [
        ("ticketmaster_soccer", ticketmaster.fetch_soccer),
        ("ticketmaster_noah_kahan", lambda: ticketmaster.fetch_concerts("Noah Kahan")),
        ("nintendo", nintendo.fetch),
        ("anime", anime.fetch),
    ]


def discover_and_persist(
    session,
    now: Optional[datetime] = None,
    source_factories = None,
) -> PipelineResult:
    now = now or datetime.now(timezone.utc)
    settings = get_settings()

    window_end = now + timedelta(days=settings.discovery_days_ahead)
    result = PipelineResult()
    source_entries = source_factories or _make_default_sources()
    seen_internal_ids: set[str] = set()

    for source_name, fetch in source_entries:
        source_row = _get_or_create_source(
            session,
            name=source_name,
            source_type="api",
            base_url="discovery",
        )

        try:
            candidates = fetch()
        except Exception as err:
            session.add(
                IngestionLog(
                    source_name=source_name,
                    candidates=0,
                    kept=0,
                    skipped=0,
                    synced=0,
                    outcome="failed",
                    message=f"{type(err).__name__}: {err}",
                )
            )
            result.logs.append(f"{source_name}:failed")
            continue

        if not candidates:
            continue

        dedupe_counts = Counter[str]()
        dedupe_seen_keys: set[str] = set()
        normalized_candidates = []
        for candidate in candidates:
            result.candidates += 1
            candidate = _normalize_candidate(candidate)
            if candidate.start_dt < now or candidate.start_dt > window_end:
                result.skipped_low_confidence += 1
                continue

            dedupe_key = build_dedupe_key(candidate.title, candidate.start_dt, candidate.venue_name)
            dedupe_counts[dedupe_key] += 1

            # Keep the first observed candidate per dedupe key.
            if dedupe_key in dedupe_seen_keys:
                continue
            normalized_candidates.append((dedupe_key, candidate))
            dedupe_seen_keys.add(dedupe_key)

        kept = 0
        for dedupe_key, candidate in normalized_candidates:
            score, reminder = rank_candidate(candidate)
            if score < MIN_PRIORITY:
                result.skipped_low_confidence += 1
                continue

            try:
                description = build_description(candidate)
            except Exception:
                description = candidate.description or ""

            internal_event_id = _build_internal_event_id(candidate, dedupe_key)
            if internal_event_id in seen_internal_ids:
                result.skipped_duplicate += 1
                continue

            existing = session.execute(select(Event).where(Event.dedupe_key == dedupe_key)).scalar_one_or_none()
            if existing is not None:
                result.skipped_duplicate += 1
                continue

            if dedupe_counts[dedupe_key] > 1:
                # Multiple copies of same raw event in one source response. Keep one candidate,
                # mark one duplicate to avoid noisy insert metrics.
                result.skipped_duplicate += 1

            existing_internal = session.execute(
                select(Event).where(Event.internal_event_id == internal_event_id)
            ).scalar_one_or_none()
            if existing_internal is not None:
                result.skipped_duplicate += 1
                continue

            event = Event(
                internal_event_id=internal_event_id,
                dedupe_key=dedupe_key,
                title=candidate.title,
                description=description,
                category=candidate.category,
                entity=candidate.entity,
                start_dt=candidate.start_dt,
                end_dt=candidate.end_dt,
                venue_name=candidate.venue_name,
                venue_city=candidate.venue_city,
                venue_country=candidate.venue_country,
                price_min=candidate.price_min,
                price_max=candidate.price_max,
                ticket_url=str(candidate.ticket_url) if candidate.ticket_url else None,
                source_name=candidate.source_name,
                source_event_id=candidate.source_event_id,
                confidence=candidate.raw_confidence,
                priority=score,
                reminder=reminder,
                status="proposed",
                source_id=source_row.id,
            )

            session.add(event)
            seen_internal_ids.add(internal_event_id)
            result.inserted += 1
            kept += 1

        session.add(
            IngestionLog(
                source_name=source_name,
                candidates=len(candidates),
                kept=kept,
                skipped=max(len(candidates) - kept, 0),
                synced=0,
                outcome="success",
            )
        )

    return result


def run_sync_cycle(database_url: Optional[str] = None, now: Optional[datetime] = None) -> PipelineResult:
    with session_scope(database_url=database_url) as session:
        return discover_and_persist(session=session, now=now)
