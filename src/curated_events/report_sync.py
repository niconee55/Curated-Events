"""Import reviewed markdown reports into the event store and sync them safely."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .calendar_sync import CalendarBackend, CalendarSyncer, SyncStats
from .db import session_scope
from .models import CalendarMapping, Event, Source


REPORT_SOURCE_NAME = "codex_research_report"
REPORT_SOURCE_TYPE = "report"
REPORT_SOURCE_BASE_URL = "preview_suggestions"


@dataclass(frozen=True)
class ReportEvent:
    section: str
    title: str
    description: str
    exact_date: str
    exact_time: str
    location: str
    price: str
    why: str
    source_link: str


@dataclass(frozen=True)
class ImportedReportEvent:
    internal_event_id: str
    title: str
    section: str
    start_dt: datetime
    end_dt: datetime
    all_day: bool
    location: str


@dataclass(frozen=True)
class ApplyReportResult:
    imported: int
    created: int
    updated: int
    snapshot_path: Path
    calendar_id: str
    scope: str


def parse_report_events(report_path: Path) -> list[ReportEvent]:
    lines = report_path.read_text(encoding="utf-8").splitlines()
    events: list[ReportEvent] = []
    section = ""
    current_title: str | None = None
    current_fields: dict[str, str] = {}
    current_description_line: str = ""

    def flush() -> None:
        nonlocal current_title, current_fields, current_description_line
        if current_title is None or section not in {"high-confidence", "lower-priority"}:
            current_title = None
            current_fields = {}
            current_description_line = ""
            return
        exact_date = current_fields.get("Exact date") or _normalize_date_window(
            current_fields.get("Date window", "")
        )
        if not exact_date:
            current_title = None
            current_fields = {}
            current_description_line = ""
            return
        events.append(
            ReportEvent(
                section=section,
                title=current_title,
                description=current_fields.get("One-sentence description", "")
                or current_fields.get("Description", "")
                or current_description_line,
                exact_date=exact_date,
                exact_time=current_fields.get("Exact time", ""),
                location=current_fields.get("Location", ""),
                price=current_fields.get("Price", ""),
                why=current_fields.get("Why it matches the preferences")
                or current_fields.get("Why it matches")
                or current_fields.get("Why it is lower priority")
                or current_fields.get("Why lower priority", ""),
                source_link=current_fields.get("Direct source link")
                or current_fields.get("Source", ""),
            )
        )
        current_title = None
        current_fields = {}
        current_description_line = ""

    for line in lines:
        heading = _markdown_heading_text(line)
        if heading == "high-confidence events":
            flush()
            section = "high-confidence"
            continue
        if heading == "lower-priority but useful events":
            flush()
            section = "lower-priority"
            continue
        if heading and (heading.startswith("search gaps") or heading == "sources"):
            flush()
            section = ""
            continue
        table_event = _parse_markdown_table_event(line, section)
        if table_event:
            flush()
            events.append(table_event)
            continue
        if line.startswith("### ") or line.startswith("## "):
            flush()
            current_title = line.split(" ", 1)[1].strip()
            continue
        bullet_title = _parse_bold_bullet_title(line)
        if bullet_title:
            flush()
            current_title = bullet_title
            continue
        normalized_line = _normalize_report_line(line)
        if normalized_line.startswith("Title: "):
            flush()
            current_title = normalized_line.split(": ", 1)[1].strip()
            continue
        if current_title and normalized_line.strip() and ": " not in normalized_line and not current_description_line:
            current_description_line = normalized_line.strip()
            continue
        if current_title and ": " in normalized_line:
            key, value = normalized_line.split(": ", 1)
            current_fields[key] = value.strip()

    flush()
    return events


def _markdown_heading_text(line: str) -> str | None:
    match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
    if match is None:
        return None
    return match.group(1).strip().lower()


def _normalize_date_window(value: str) -> str:
    return re.sub(r"\s+\([^)]*\)\s*$", "", value.strip())


def _normalize_report_line(line: str) -> str:
    normalized = line.lstrip()
    while normalized.startswith("- "):
        normalized = normalized[2:]
        normalized = normalized.lstrip()
    return normalized


def _parse_bold_bullet_title(line: str) -> str | None:
    stripped = line.lstrip()
    if not stripped.startswith("- **") or not stripped.endswith("**"):
        return None
    return stripped[4:-2].strip()


def _parse_markdown_table_event(line: str, section: str) -> ReportEvent | None:
    if section not in {"high-confidence", "lower-priority"}:
        return None
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None

    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if len(cells) < 6:
        return None
    if cells[0].lower() == "title" or all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
        return None

    title, exact_date, exact_time, location, why, source_link = cells[:6]
    if not title or not exact_date:
        return None
    return ReportEvent(
        section=section,
        title=title,
        description=why,
        exact_date=exact_date,
        exact_time=exact_time,
        location=location,
        price="",
        why=why,
        source_link=source_link,
    )


def filter_report_events(events: Iterable[ReportEvent], scope: str) -> list[ReportEvent]:
    if scope == "all":
        return list(events)
    return [event for event in events if event.section == "high-confidence"]


def import_report_events(
    report_path: Path,
    *,
    database_url: str | None,
    timezone_name: str,
    scope: str,
) -> list[ImportedReportEvent]:
    timezone = ZoneInfo(timezone_name)
    parsed = filter_report_events(parse_report_events(report_path), scope=scope)
    imported: list[ImportedReportEvent] = []

    with session_scope(database_url=database_url) as session:
        source = session.execute(select(Source).where(Source.name == REPORT_SOURCE_NAME)).scalar_one_or_none()
        if source is None:
            source = Source(name=REPORT_SOURCE_NAME, type=REPORT_SOURCE_TYPE, base_url=REPORT_SOURCE_BASE_URL)
            session.add(source)
            session.flush()

        for report_event in parsed:
            for expanded_event in _expand_report_event(report_event):
                normalized_exact_time = _normalize_exact_time(expanded_event)
                source_timezone = _resolve_event_timezone(
                    expanded_event.location,
                    normalized_exact_time,
                    default_timezone=timezone,
                )
                start_dt, end_dt, all_day = _parse_event_dates(
                    expanded_event.exact_date,
                    normalized_exact_time,
                    timezone=source_timezone,
                )
                if not all_day:
                    start_dt = start_dt.astimezone(timezone)
                    end_dt = end_dt.astimezone(timezone)
                internal_event_id = _build_internal_event_id(expanded_event)
                dedupe_key = _build_dedupe_key(expanded_event)
                event = session.execute(
                    select(Event).where(Event.internal_event_id == internal_event_id)
                ).scalar_one_or_none()
                description = _build_event_description(expanded_event)

                if event is None:
                    event = Event(
                        internal_event_id=internal_event_id,
                        dedupe_key=dedupe_key,
                        title=expanded_event.title,
                        description=description,
                        category=_category_for_section(expanded_event.section),
                        entity=None,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        venue_name=expanded_event.location,
                        venue_city="",
                        venue_country="",
                        price_min=None,
                        price_max=None,
                        ticket_url=expanded_event.source_link or None,
                        source_name=REPORT_SOURCE_NAME,
                        source_event_id=internal_event_id,
                        confidence=1.0 if expanded_event.section == "high-confidence" else 0.7,
                        priority=1.0 if expanded_event.section == "high-confidence" else 0.7,
                        reminder=True,
                        status="ready",
                        source_id=source.id,
                    )
                    session.add(event)
                else:
                    event.title = expanded_event.title
                    event.description = description
                    event.start_dt = start_dt
                    event.end_dt = end_dt
                    event.venue_name = expanded_event.location
                    event.ticket_url = expanded_event.source_link or None
                    event.status = "ready"

                imported.append(
                    ImportedReportEvent(
                        internal_event_id=internal_event_id,
                        title=expanded_event.title,
                        section=expanded_event.section,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        all_day=all_day,
                        location=expanded_event.location,
                    )
                )

    return imported


def apply_report_to_calendar(
    report_path: Path,
    *,
    database_url: str | None,
    timezone_name: str,
    scope: str,
    calendar_backend: CalendarBackend,
    calendar_id: str,
    snapshot_path: Path,
) -> ApplyReportResult:
    imported = import_report_events(
        report_path,
        database_url=database_url,
        timezone_name=timezone_name,
        scope=scope,
    )
    sync_result = _sync_imported_events(
        imported=imported,
        database_url=database_url,
        calendar_backend=calendar_backend,
    )
    snapshot = _build_snapshot(
        database_url=database_url,
        calendar_id=calendar_id,
        report_path=report_path,
        scope=scope,
        imported=imported,
    )
    snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return ApplyReportResult(
        imported=len(imported),
        created=sync_result.created,
        updated=sync_result.updated,
        snapshot_path=snapshot_path,
        calendar_id=calendar_id,
        scope=scope,
    )


def rollback_snapshot(
    snapshot_path: Path,
    *,
    database_url: str | None,
    calendar_backend: CalendarBackend,
) -> int:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    removed = 0
    with session_scope(database_url=database_url) as session:
        for item in snapshot.get("events", []):
            google_event_id = item.get("google_event_id")
            internal_event_id = item.get("internal_event_id")
            if google_event_id:
                calendar_backend.delete(event_id=google_event_id)
                removed += 1
            mapping = session.execute(
                select(CalendarMapping).where(CalendarMapping.internal_event_id == internal_event_id)
            ).scalar_one_or_none()
            if mapping is not None:
                session.delete(mapping)
            event = session.execute(
                select(Event).where(Event.internal_event_id == internal_event_id)
            ).scalar_one_or_none()
            if event is not None and event.source_name == REPORT_SOURCE_NAME:
                session.delete(event)
    return removed


def remove_event_by_internal_id(
    internal_event_id: str,
    *,
    database_url: str | None,
    calendar_backend: CalendarBackend,
) -> bool:
    with session_scope(database_url=database_url) as session:
        mapping = session.execute(
            select(CalendarMapping).where(CalendarMapping.internal_event_id == internal_event_id)
        ).scalar_one_or_none()
        if mapping is not None:
            calendar_backend.delete(event_id=mapping.google_event_id)
            session.delete(mapping)
        event = session.execute(
            select(Event).where(Event.internal_event_id == internal_event_id)
        ).scalar_one_or_none()
        if event is None:
            return False
        session.delete(event)
        return True


def _build_snapshot(
    *,
    database_url: str | None,
    calendar_id: str,
    report_path: Path,
    scope: str,
    imported: list[ImportedReportEvent],
) -> dict:
    by_id = {item.internal_event_id: item for item in imported}
    with session_scope(database_url=database_url) as session:
        mappings = session.execute(
            select(CalendarMapping).where(CalendarMapping.internal_event_id.in_(list(by_id)))
        ).scalars().all()
        mapping_rows = [
            {
                "internal_event_id": mapping.internal_event_id,
                "google_event_id": mapping.google_event_id,
            }
            for mapping in mappings
        ]
    items = []
    for mapping in mapping_rows:
        imported_event = by_id[mapping["internal_event_id"]]
        items.append(
            {
                "internal_event_id": mapping["internal_event_id"],
                "google_event_id": mapping["google_event_id"],
                "title": imported_event.title,
                "section": imported_event.section,
                "start_dt": imported_event.start_dt.isoformat(),
                "end_dt": imported_event.end_dt.isoformat(),
                "all_day": imported_event.all_day,
                "location": imported_event.location,
            }
        )
    return {
        "calendar_id": calendar_id,
        "report_path": str(report_path.resolve()),
        "scope": scope,
        "events": items,
    }


def _sync_imported_events(
    *,
    imported: list[ImportedReportEvent],
    database_url: str | None,
    calendar_backend: CalendarBackend,
) -> SyncStats:
    syncer = CalendarSyncer(backend=calendar_backend)
    imported_ids = {item.internal_event_id for item in imported}
    stats = SyncStats()
    if not imported_ids:
        return stats

    from datetime import datetime, timezone

    with session_scope(database_url=database_url) as session:
        for internal_event_id in imported_ids:
            event = session.execute(
                select(Event).where(Event.internal_event_id == internal_event_id)
            ).scalar_one()
            existing = session.execute(
                select(CalendarMapping).where(CalendarMapping.internal_event_id == internal_event_id)
            ).scalar_one_or_none()
            if existing is None:
                google_event_id = calendar_backend.upsert(
                    event_id=None,
                    payload=syncer._build_payload(event),
                )
                session.add(
                    CalendarMapping(
                        event_id=event.id,
                        internal_event_id=event.internal_event_id,
                        google_event_id=google_event_id,
                        status="synced",
                        last_synced_at=datetime.now(timezone.utc),
                    )
                )
                stats.created += 1
            else:
                calendar_backend.upsert(
                    event_id=existing.google_event_id,
                    payload=syncer._build_payload(event),
                )
                existing.last_synced_at = datetime.now(timezone.utc)
                existing.status = "synced"
                stats.updated += 1
            event.status = "synced"
    return stats


def _build_internal_event_id(report_event: ReportEvent) -> str:
    stable = (
        f"{report_event.section}|{report_event.title}|{report_event.exact_date}|"
        f"{report_event.exact_time}|{report_event.location}"
    )
    digest = sha256(stable.encode("utf-8")).hexdigest()[:16]
    slug = re.sub(r"[^a-z0-9]+", "-", report_event.title.lower()).strip("-")[:40]
    return f"report:{slug}:{digest}"


def _build_dedupe_key(report_event: ReportEvent) -> str:
    stable = f"{report_event.title}|{report_event.exact_date}|{report_event.exact_time}|{report_event.location}"
    return sha256(stable.encode("utf-8")).hexdigest()


def _category_for_section(section: str) -> str:
    return "report_high_confidence" if section == "high-confidence" else "report_lower_priority"


def _build_event_description(report_event: ReportEvent) -> str:
    parts = [
        report_event.description,
        f"Price: {report_event.price}" if report_event.price else "",
        f"Source: {report_event.source_link}" if report_event.source_link else "",
    ]
    return "\n\n".join(part for part in parts if part)


def _expand_report_event(report_event: ReportEvent) -> list[ReportEvent]:
    expanded: list[ReportEvent] = []
    for recurring_event in _expand_recurring_report_event(report_event):
        expanded.extend(_expand_long_date_range(recurring_event))
    return expanded


def _expand_long_date_range(report_event: ReportEvent) -> list[ReportEvent]:
    date_range = _parse_date_range(report_event.exact_date)
    if date_range is None:
        return [report_event]

    start_date, end_date = date_range
    if (end_date - start_date).days < 3:
        return [report_event]

    return [
        _build_range_boundary_event(report_event, start_date, "Start"),
        _build_range_boundary_event(report_event, end_date, "End"),
    ]


def _build_range_boundary_event(report_event: ReportEvent, boundary_date: date, label: str) -> ReportEvent:
    return ReportEvent(
        section=report_event.section,
        title=f"{report_event.title} ({label})",
        description=report_event.description,
        exact_date=boundary_date.strftime("%B %d, %Y"),
        exact_time="",
        location=report_event.location,
        price=report_event.price,
        why=report_event.why,
        source_link=report_event.source_link,
    )


def _expand_recurring_report_event(report_event: ReportEvent) -> list[ReportEvent]:
    match = re.match(
        r"^(Mondays|Tuesdays|Wednesdays|Thursdays|Fridays|Saturdays|Sundays)"
        r"(?: and (Mondays|Tuesdays|Wednesdays|Thursdays|Fridays|Saturdays|Sundays))?"
        r" throughout ([A-Za-z]+) (\d{4})$",
        report_event.exact_date.strip(),
    )
    if not match:
        return [report_event]

    weekday_tokens = [token for token in match.groups()[:2] if token]
    month_name = match.group(3)
    year = int(match.group(4))
    month_num = datetime.strptime(month_name, "%B").month
    last_day = calendar.monthrange(year, month_num)[1]
    weekdays = {_weekday_name_to_index(token) for token in weekday_tokens}
    expanded: list[ReportEvent] = []
    for day in range(1, last_day + 1):
        current = date(year, month_num, day)
        if current.weekday() not in weekdays:
            continue
        expanded.append(
            ReportEvent(
                section=report_event.section,
                title=f"{report_event.title} ({_short_date_label(current)})",
                description=report_event.description,
                exact_date=current.strftime("%B %d, %Y"),
                exact_time=report_event.exact_time,
                location=report_event.location,
                price=report_event.price,
                why=report_event.why,
                source_link=report_event.source_link,
            )
        )
    return expanded or [report_event]


def _weekday_name_to_index(value: str) -> int:
    mapping = {
        "Mondays": 0,
        "Tuesdays": 1,
        "Wednesdays": 2,
        "Thursdays": 3,
        "Fridays": 4,
        "Saturdays": 5,
        "Sundays": 6,
    }
    return mapping[value]


def _short_date_label(value: date) -> str:
    return f"{value.strftime('%a %b')} {value.day}"


def _parse_event_dates(value: str, exact_time: str, *, timezone: ZoneInfo) -> tuple[datetime, datetime, bool]:
    date_range = _parse_date_range(value)
    if date_range is not None:
        start_date, end_date = date_range
        start_dt = datetime.combine(start_date, time(hour=0), tzinfo=timezone)
        end_dt = datetime.combine(end_date, time(hour=0), tzinfo=timezone)
        end_dt = end_dt + timedelta(days=1)
        return start_dt, end_dt, True

    start_date = _parse_human_date(value)
    if exact_time:
        try:
            parsed_time = _parse_human_time(exact_time)
        except ValueError:
            parsed_time = None
        if parsed_time is not None:
            start_dt = datetime.combine(start_date, parsed_time, tzinfo=timezone)
            end_time = _default_end_time(parsed_time)
            end_date = start_date + timedelta(days=1) if end_time <= parsed_time else start_date
            end_dt = datetime.combine(end_date, end_time, tzinfo=timezone)
            return start_dt, end_dt, False
    start_dt = datetime.combine(start_date, time(hour=0), tzinfo=timezone)
    end_dt = start_dt + timedelta(days=1)
    return start_dt, end_dt, True


def _parse_date_range(value: str) -> tuple[date, date] | None:
    cleaned = value.strip()
    iso_range = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\s*[-–—]\s*(\d{4}-\d{2}-\d{2})", cleaned)
    if iso_range is not None:
        try:
            return date.fromisoformat(iso_range.group(1)), date.fromisoformat(iso_range.group(2))
        except ValueError:
            return None

    if " to " in cleaned:
        start_value, end_value = cleaned.split(" to ", 1)
        try:
            return _parse_human_date(start_value), _parse_human_date(end_value)
        except ValueError:
            return None

    compact_range = re.fullmatch(
        r"([A-Za-z]+)\s+(\d{1,2})\s*[-–—]\s*(\d{1,2}),\s*(\d{4})",
        cleaned,
    )
    if compact_range is None:
        return None
    month, start_day, end_day, year = compact_range.groups()
    try:
        return (
            _parse_human_date(f"{month} {start_day}, {year}"),
            _parse_human_date(f"{month} {end_day}, {year}"),
        )
    except ValueError:
        return None


def _normalize_exact_time(event: ParsedReportEvent) -> str:
    exact_time = event.exact_time.strip()
    if not exact_time:
        return exact_time

    upper_time = exact_time.upper()
    source_link = event.source_link.lower()
    title = event.title.lower()

    # Champions League kickoff times are ultimately what matters on this calendar.
    # When the report falls back to venue-local wording, normalize to the canonical
    # New York kickoff time so the calendar does not inherit an incorrect local-time guess.
    if "local kickoff" in upper_time and "uefachampionsleague" in source_link:
        return "3:00 PM ET"

    # If the agent emits dual-time strings, keep the New York side only.
    if " / " in exact_time and "ET" in upper_time:
        return exact_time.split(" / ", 1)[0].strip()

    if "champions league" in title and "local kickoff" in upper_time:
        return "3:00 PM ET"

    return exact_time


def _parse_human_date(value: str) -> date:
    cleaned = re.sub(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+", "", value.strip())
    iso_date = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", cleaned)
    if iso_date:
        year, month, day = iso_date.groups()
        return date(int(year), int(month), int(day))
    compact_range = re.match(r"^([A-Za-z]+)\s+(\d{1,2})-(\d{1,2}),\s*(\d{4})$", cleaned)
    if compact_range:
        month, start_day, _end_day, year = compact_range.groups()
        cleaned = f"{month} {start_day}, {year}"
    return datetime.strptime(cleaned, "%B %d, %Y").date()


def _parse_human_time(value: str) -> time:
    cleaned = value.strip().upper().replace(".", "")
    cleaned = re.sub(r"\s*\([^)]*\)", "", cleaned).strip()
    if cleaned.startswith("NOT YET POSTED"):
        raise ValueError(f"Unsupported time format: {value}")
    if " / " in cleaned:
        cleaned = cleaned.split(" / ", 1)[0].strip()
    cleaned = re.sub(r"\s+LOCAL KICKOFF$", "", cleaned)
    cleaned = re.sub(r"\s+LOCAL$", "", cleaned)
    cleaned = re.sub(r"\s+(LOCAL|ET|EST|EDT|CT|CST|CDT|MT|MST|MDT|PT|PST|PDT|CET|CEST|BST)$", "", cleaned)
    if "-" in cleaned:
        left, right = [part.strip() for part in cleaned.split("-", 1)]
        if ("AM" not in left and "PM" not in left) and ("AM" in right or "PM" in right):
            suffix = "AM" if "AM" in right else "PM"
            cleaned = f"{left} {suffix}"
        else:
            cleaned = left
    for pattern in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            return datetime.strptime(cleaned, pattern).time()
        except ValueError:
            continue
    raise ValueError(f"Unsupported time format: {value}")


def _default_end_time(start: time) -> time:
    start_dt = datetime.combine(date(2000, 1, 1), start)
    return (start_dt + timedelta(hours=2)).time()


def _resolve_event_timezone(location: str, exact_time: str, default_timezone: ZoneInfo) -> ZoneInfo:
    upper_time = exact_time.upper()
    if any(token in upper_time for token in [" ET", " EST", " EDT"]):
        return ZoneInfo("America/New_York")
    if any(token in upper_time for token in [" BST"]):
        return ZoneInfo("Europe/London")
    if any(token in upper_time for token in [" CET", " CEST"]):
        return ZoneInfo("Europe/Paris")

    location_lower = location.lower()
    if "new york" in location_lower:
        return ZoneInfo("America/New_York")
    if "london" in location_lower or "liverpool" in location_lower or "england" in location_lower:
        return ZoneInfo("Europe/London")
    if "madrid" in location_lower or "barcelona" in location_lower or "spain" in location_lower:
        return ZoneInfo("Europe/Madrid")
    if "munich" in location_lower or "munchen" in location_lower or "germany" in location_lower:
        return ZoneInfo("Europe/Berlin")
    if "paris" in location_lower or "france" in location_lower:
        return ZoneInfo("Europe/Paris")
    if "lisbon" in location_lower or "portugal" in location_lower:
        return ZoneInfo("Europe/Lisbon")
    return default_timezone
