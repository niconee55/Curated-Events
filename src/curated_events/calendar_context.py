"""Export current Google Calendar events as prompt context for update runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Settings, get_settings
from .google_auth import load_google_credentials


@dataclass(frozen=True)
class CalendarContextEvent:
    title: str
    start: date | datetime
    end: date | datetime
    all_day: bool
    location: str
    description: str
    google_event_id: str


def export_calendar_month_context(*, month_start: date, month_end: date, output_path: Path, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if not settings.google_calendar_id:
        raise RuntimeError("GOOGLE_CALENDAR_ID is not configured.")
    credentials_path = Path(settings.google_credentials_file)
    token_path = Path(settings.google_token_file)
    if not credentials_path.exists():
        raise RuntimeError(f"Google credentials file not found: {credentials_path}")
    if not token_path.exists():
        raise RuntimeError(f"Google token file not found: {token_path}. Run `curated-events google-auth` first.")

    events = list_calendar_events_for_month(
        calendar_id=settings.google_calendar_id,
        token_path=token_path,
        timezone_name=settings.timezone,
        month_start=month_start,
        month_end=month_end,
    )
    markdown = render_calendar_context(
        events=events,
        calendar_name=settings.google_calendar_name,
        month_start=month_start,
        month_end=month_end,
        timezone_name=settings.timezone,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return markdown


def list_calendar_events_for_month(
    *,
    calendar_id: str,
    token_path: Path,
    timezone_name: str,
    month_start: date,
    month_end: date,
) -> list[CalendarContextEvent]:
    from googleapiclient.discovery import build

    tz = ZoneInfo(timezone_name)
    time_min = datetime.combine(month_start, time.min, tzinfo=tz)
    time_max = datetime.combine(month_end + timedelta(days=1), time.min, tzinfo=tz)
    credentials = load_google_credentials(token_path=token_path)
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

    response = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=2500,
        )
        .execute()
    )
    items = response.get("items") or []
    events: list[CalendarContextEvent] = []
    for item in items:
        start_value, start_all_day = _parse_google_datetime(item.get("start") or {}, timezone_name)
        end_value, _ = _parse_google_datetime(item.get("end") or {}, timezone_name)
        events.append(
            CalendarContextEvent(
                title=item.get("summary") or "(untitled event)",
                start=start_value,
                end=end_value,
                all_day=start_all_day,
                location=item.get("location") or "",
                description=(item.get("description") or "").strip(),
                google_event_id=item.get("id") or "",
            )
        )
    return events


def render_calendar_context(
    *,
    events: list[CalendarContextEvent],
    calendar_name: str,
    month_start: date,
    month_end: date,
    timezone_name: str,
) -> str:
    lines = [
        "# Current Calendar Context",
        "",
        f"- Calendar: {calendar_name}",
        f"- Month window: {month_start.isoformat()} to {month_end.isoformat()}",
        f"- Timezone: {timezone_name}",
        f"- Existing events in window: {len(events)}",
        "",
        "Use this as the current baseline for the user's calendar. Replace placeholders when the real matchup or stronger context is now available, refresh stale descriptions, and add genuinely missing events.",
        "",
        "## Existing Events",
    ]
    if not events:
        lines.extend(
            [
                "",
                "No events are currently on the calendar in this month window.",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    for event in events:
        lines.extend(
            [
                "",
                f"### {event.title}",
                f"- When: {_format_event_when(event, timezone_name)}",
            ]
        )
        if event.location:
            lines.append(f"- Location: {event.location}")
        if event.description:
            lines.append(f"- Current description: {_compact_description(event.description)}")
        if event.google_event_id:
            lines.append(f"- Calendar event id: {event.google_event_id}")

    return "\n".join(lines).rstrip() + "\n"


def _parse_google_datetime(value: dict, timezone_name: str) -> tuple[date | datetime, bool]:
    if "date" in value:
        parsed_date = date.fromisoformat(value["date"])
        return parsed_date, True
    raw = value.get("dateTime")
    if not raw:
        raise RuntimeError(f"Unsupported Google Calendar datetime payload: {value}")
    normalized = raw.replace("Z", "+00:00")
    parsed_dt = datetime.fromisoformat(normalized)
    return parsed_dt.astimezone(ZoneInfo(timezone_name)), False


def _format_event_when(event: CalendarContextEvent, timezone_name: str) -> str:
    if event.all_day:
        start_date = event.start if isinstance(event.start, date) else event.start.date()
        end_date = event.end if isinstance(event.end, date) else event.end.date()
        last_inclusive = end_date - timedelta(days=1)
        if last_inclusive <= start_date:
            return start_date.strftime("%a, %b %-d, %Y (all day)")
        return f"{start_date.strftime('%a, %b %-d, %Y')} to {last_inclusive.strftime('%a, %b %-d, %Y')} (all day)"

    start_dt = event.start if isinstance(event.start, datetime) else datetime.combine(event.start, time.min, tzinfo=ZoneInfo(timezone_name))
    end_dt = event.end if isinstance(event.end, datetime) else datetime.combine(event.end, time.min, tzinfo=ZoneInfo(timezone_name))
    return (
        f"{start_dt.strftime('%a, %b %-d, %Y, %-I:%M %p')} to "
        f"{end_dt.strftime('%-I:%M %p')} {timezone_name}"
    )


def _compact_description(text: str, limit: int = 280) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
