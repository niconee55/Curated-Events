from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import sentinel

from sqlalchemy import select

from curated_events.calendar_sync import CalendarSyncer, InMemoryCalendarBackend, RealGoogleCalendarBackend, get_calendar_backend
from curated_events.config import Settings
from curated_events.db import init_db, session_scope
from curated_events.models import CalendarMapping, Event
from curated_events.pipeline import PipelineResult, discover_and_persist, run_sync_cycle
from curated_events.scheduler import run_monthly_sync
from curated_events.schemas import EventCandidate
from curated_events.sources.ticketmaster import _format_tm_datetime


def _db_url() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    return f"sqlite:///{tmp.name}"


def _init_db_with_overrides(url: str) -> None:
    os.environ["DATABASE_URL"] = url
    os.environ["TICKETMASTER_API_KEY"] = ""
    os.environ["GOOGLE_CALENDAR_ID"] = ""
    os.environ["GOOGLE_CREDENTIALS_FILE"] = ""
    os.environ["GOOGLE_TOKEN_FILE"] = ""
    init_db(database_url=url)


def _candidate(title: str, *, start_dt: datetime) -> EventCandidate:
    return EventCandidate(
        title=title,
        category="soccer",
        entity="Real Madrid",
        start_dt=start_dt,
        source_name="stub",
        source_event_id=title,
        raw_confidence=0.95,
    )


def _run_discovery_with_duplicates(url: str) -> PipelineResult:
    now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)

    candidates = [
        _candidate("Match A", start_dt=now + timedelta(days=2)),
        _candidate("Match A", start_dt=now + timedelta(days=2)),
    ]

    sources = [("stub", lambda: candidates)]

    with session_scope(database_url=url) as session:
        return discover_and_persist(session=session, now=now, source_factories=sources)


def test_pipeline_dedupes_by_hash_key():
    url = _db_url()
    _init_db_with_overrides(url)

    first_run = _run_discovery_with_duplicates(url)
    assert first_run.inserted == 1
    assert first_run.skipped_duplicate == 1

    second_run = _run_discovery_with_duplicates(url)
    assert second_run.inserted == 0
    assert second_run.skipped_duplicate == 1

    with session_scope(database_url=url) as session:
        events = session.execute(select(Event)).scalars().all()
        mappings = session.execute(select(CalendarMapping)).scalars().all()
        assert len(events) == 1
        assert len(mappings) == 0


class CountingBackend:
    def __init__(self):
        self.calls = []
        self.calls_by_id = []

    def upsert(self, *, event_id: str | None, payload: dict) -> str:
        self.calls.append((event_id is not None, payload.get("summary")))
        return event_id or f"google-{len(self.calls)}"

    def build_payload(self, event) -> dict:
        self.calls_by_id.append(event.internal_event_id)
        reminders = []
        if event.reminder:
            reminders.append({"method": "popup", "minutes": 20})
        return {
            "summary": event.title,
            "description": event.description or "",
            "start": {"dateTime": event.start_dt.isoformat(), "timeZone": "America/New_York"},
            "end": {
                "dateTime": (event.end_dt or event.start_dt).isoformat(),
                "timeZone": "America/New_York",
            },
            "location": event.venue_name,
            "reminders": {"useDefault": False, "overrides": reminders},
        }


def test_syncer_is_idempotent_by_internal_event_id():
    url = _db_url()
    _init_db_with_overrides(url)
    _run_discovery_with_duplicates(url)

    backend = CountingBackend()
    syncer = CalendarSyncer(backend=backend)

    first = syncer.sync_pending(database_url=url)
    second = syncer.sync_pending(database_url=url)

    assert first.created == 1
    assert second.created == 0
    assert second.updated == 1
    assert all(isinstance(item, tuple) for item in backend.calls)

    with session_scope(database_url=url) as session:
        rows = session.execute(select(CalendarMapping)).scalars().all()
        assert len(rows) == 1


def test_scheduler_runs_bound_cycle_for_tests():
    url = _db_url()
    _init_db_with_overrides(url)
    assert run_monthly_sync(database_url=url, max_ticks=2) == 2


def test_ticketmaster_datetime_format_omits_microseconds():
    value = datetime(2026, 4, 1, 12, 30, 45, 123456, tzinfo=timezone.utc)
    assert _format_tm_datetime(value) == "2026-04-01T12:30:45Z"


def test_calendar_backend_defaults_to_in_memory_without_token(tmp_path: Path):
    settings = Settings(
        google_credentials_file=str(tmp_path / "google-credentials.json"),
        google_token_file=str(tmp_path / "token.json"),
        google_calendar_id="calendar-id",
    )
    (tmp_path / "google-credentials.json").write_text("{}", encoding="utf-8")

    backend = get_calendar_backend(settings=settings)

    assert isinstance(backend, InMemoryCalendarBackend)


def test_calendar_backend_uses_google_backend_when_token_present(monkeypatch, tmp_path: Path):
    credentials_path = tmp_path / "google-credentials.json"
    token_path = tmp_path / "token.json"
    credentials_path.write_text("{}", encoding="utf-8")
    token_path.write_text("{}", encoding="utf-8")
    settings = Settings(
        google_credentials_file=str(credentials_path),
        google_token_file=str(token_path),
        google_calendar_id="calendar-id",
    )

    monkeypatch.setattr("curated_events.google_auth.load_google_credentials", lambda token_path: sentinel.creds)

    backend = get_calendar_backend(settings=settings)

    assert isinstance(backend, RealGoogleCalendarBackend)
    assert backend.calendar_id == "calendar-id"
    assert backend.credentials is sentinel.creds


def test_in_memory_backend_builds_all_day_payload_for_midnight_bounded_event():
    event = Event(
        internal_event_id="report:event",
        dedupe_key="dedupe",
        title="Album Drop",
        description="desc",
        category="report_high_confidence",
        entity=None,
        start_dt=datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc),
        end_dt=datetime(2026, 4, 25, 0, 0, tzinfo=timezone.utc),
        venue_name="Official digital release",
        venue_city="",
        venue_country="",
        price_min=None,
        price_max=None,
        ticket_url=None,
        source_name="codex_research_report",
        source_event_id="report:event",
        confidence=1.0,
        priority=1.0,
        reminder=True,
        status="ready",
    )

    payload = InMemoryCalendarBackend().build_payload(event)

    assert payload["start"] == {"date": "2026-04-24"}
    assert payload["end"] == {"date": "2026-04-25"}
