from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import select

from curated_events.calendar_sync import InMemoryCalendarBackend
from curated_events.db import init_db, session_scope
from curated_events.models import CalendarMapping, Event
from curated_events.report_sync import (
    apply_report_to_calendar,
    parse_report_events,
    rollback_snapshot,
)


def _db_url() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    return f"sqlite:///{tmp.name}"


def _sample_report(tmp_path: Path) -> Path:
    report = tmp_path / "preview_suggestions.txt"
    report.write_text(
        """# High-confidence events

### Match One
- One-sentence description: A strong soccer event.
- Exact date: Tuesday, April 7, 2026
- Exact time: 3:00 PM ET
- Location: Madrid, Spain
- Price: Not applicable for a watch event
- Why it matches the preferences: Big tournament match.
- Direct source link: https://example.com/match-one

### Album Drop
- One-sentence description: A new album release.
- Exact date: Friday, April 24, 2026
- Location: Official digital release
- Price: $9.99 digital album
- Why it matches the preferences: Strong music fit.
- Direct source link: https://example.com/album

# Lower-priority but useful events

### Museum Night
- One-sentence description: A museum night.
- Exact date: Saturday, April 18, 2026
- Location: New York, NY
- Price: Free with museum admission
- Why it is lower priority: Useful but secondary.
- Direct source link: https://example.com/museum

# Search gaps or intentionally empty categories
""",
        encoding="utf-8",
    )
    return report


def test_parse_report_events_reads_both_sections(tmp_path: Path):
    report_path = _sample_report(tmp_path)

    events = parse_report_events(report_path)

    assert len(events) == 3
    assert events[0].section == "high-confidence"
    assert events[2].section == "lower-priority"


def test_parse_report_events_reads_dash_title_format(tmp_path: Path):
    report = tmp_path / "preview_suggestions.txt"
    report.write_text(
        """# High-confidence events

- Title: Arsenal vs Fulham
  Description: A title-race London derby.
  Exact date: 2026-05-02
  Exact time: 12:30 PM ET
  Location: Emirates Stadium, London, England
  Why it matches the preferences: Strong EPL run-in match.
  Direct source link: https://example.com/arsenal-fulham

# Lower-priority but useful events

- Title: Frieze New York 2026 Public Opening (May 14)
  Description: A Manhattan culture pick.
  Exact date: 2026-05-14
  Exact time: 1:00 PM ET
  Location: The Shed, New York, NY
  Why it is lower priority: Secondary to soccer.
  Direct source link: https://example.com/frieze
""",
        encoding="utf-8",
    )

    events = parse_report_events(report)

    assert len(events) == 2
    assert events[0].title == "Arsenal vs Fulham"
    assert events[0].description == "A title-race London derby."
    assert events[1].section == "lower-priority"


def test_parse_report_events_reads_markdown_table_format(tmp_path: Path):
    report = tmp_path / "preview_suggestions.txt"
    report.write_text(
        """# High-confidence events

## FIFA World Cup 2026 June slate

| Title | Exact date | Exact time | Location | Why it matches the preferences | Direct source link |
|---|---:|---:|---|---|---|
| Mexico vs South Africa | 2026-06-11 | 4:00 PM ET | Estadio Banorte, Mexico City | Opening match of the expanded World Cup. | https://example.com/mexico-south-africa |
| France vs Senegal | 2026-06-16 | 4:00 PM ET | MetLife Stadium, East Rutherford | France priority match in the New York market. | https://example.com/france-senegal |

# Lower-priority but useful events
""",
        encoding="utf-8",
    )

    events = parse_report_events(report)

    assert len(events) == 2
    assert events[0].title == "Mexico vs South Africa"
    assert events[0].section == "high-confidence"
    assert events[0].description == "Opening match of the expanded World Cup."
    assert events[1].exact_time == "4:00 PM ET"


def test_apply_report_accepts_iso_dates(tmp_path: Path):
    url = _db_url()
    init_db(database_url=url)
    report = tmp_path / "preview_suggestions.txt"
    report.write_text(
        """# High-confidence events

## ISO Match
- One-sentence description: A seeded event using ISO date format.
- Exact date: 2026-04-07
- Exact time: 3:00 PM ET
- Location: Lisbon, Portugal
- Why it matches the preferences: Valid autonomous report format.
- Direct source link: https://example.com/iso-match
""",
        encoding="utf-8",
    )
    snapshot_path = tmp_path / "snapshot.json"

    result = apply_report_to_calendar(
        report,
        database_url=url,
        timezone_name="America/New_York",
        scope="high-confidence",
        calendar_backend=InMemoryCalendarBackend(),
        calendar_id="calendar-id",
        snapshot_path=snapshot_path,
    )

    assert result.imported == 1
    with session_scope(database_url=url) as session:
        event = session.execute(select(Event).where(Event.title == "ISO Match")).scalar_one()
        assert event.start_dt.year == 2026
        assert event.start_dt.month == 4
        assert event.start_dt.day == 7


def test_apply_report_handles_late_night_event_crossing_midnight(tmp_path: Path):
    url = _db_url()
    init_db(database_url=url)
    report = tmp_path / "preview_suggestions.txt"
    report.write_text(
        """# High-confidence events

## Late Match
- One-sentence description: A late match.
- Exact date: 2026-06-11
- Exact time: 11:00 PM ET
- Location: New York, NY
- Why it matches the preferences: Valid late match.
- Direct source link: https://example.com/late-match
""",
        encoding="utf-8",
    )

    result = apply_report_to_calendar(
        report,
        database_url=url,
        timezone_name="America/New_York",
        scope="high-confidence",
        calendar_backend=InMemoryCalendarBackend(),
        calendar_id="calendar-id",
        snapshot_path=tmp_path / "snapshot.json",
    )

    assert result.imported == 1
    with session_scope(database_url=url) as session:
        event = session.execute(select(Event).where(Event.title == "Late Match")).scalar_one()
        assert event.start_dt.hour == 23
        assert event.end_dt.day == 12
        assert event.end_dt.hour == 1


def test_apply_report_imports_high_confidence_only_and_writes_snapshot(tmp_path: Path):
    url = _db_url()
    init_db(database_url=url)
    report_path = _sample_report(tmp_path)
    snapshot_path = tmp_path / "snapshot.json"

    result = apply_report_to_calendar(
        report_path,
        database_url=url,
        timezone_name="America/New_York",
        scope="high-confidence",
        calendar_backend=InMemoryCalendarBackend(),
        calendar_id="calendar-id",
        snapshot_path=snapshot_path,
    )

    assert result.imported == 2
    assert result.created == 2
    assert snapshot_path.exists()

    with session_scope(database_url=url) as session:
        events = session.execute(select(Event)).scalars().all()
        mappings = session.execute(select(CalendarMapping)).scalars().all()
        assert len(events) == 2
        assert len(mappings) == 2
        timed = next(event for event in events if event.title == "Match One")
        all_day = next(event for event in events if event.title == "Album Drop")
        assert timed.start_dt.hour == 15
        assert timed.end_dt.hour == 17
        assert all_day.start_dt.hour == 0
        assert all_day.end_dt.day == all_day.start_dt.day + 1


def test_rollback_snapshot_removes_synced_report_events(tmp_path: Path):
    url = _db_url()
    init_db(database_url=url)
    report_path = _sample_report(tmp_path)
    snapshot_path = tmp_path / "snapshot.json"
    backend = InMemoryCalendarBackend()

    apply_report_to_calendar(
        report_path,
        database_url=url,
        timezone_name="America/New_York",
        scope="high-confidence",
        calendar_backend=backend,
        calendar_id="calendar-id",
        snapshot_path=snapshot_path,
    )

    removed = rollback_snapshot(snapshot_path, database_url=url, calendar_backend=backend)

    assert removed == 2
    with session_scope(database_url=url) as session:
        events = session.execute(select(Event)).scalars().all()
        mappings = session.execute(select(CalendarMapping)).scalars().all()
        assert events == []
        assert mappings == []
