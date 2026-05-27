"""Google Calendar synchronization abstraction and idempotent mapping logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .config import Settings, get_settings
from .db import session_scope
from .models import CalendarMapping, Event


@dataclass
class SyncStats:
    created: int = 0
    updated: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return self.created + self.updated + self.skipped


class CalendarBackend:
    def upsert(self, *, event_id: str | None, payload: dict) -> str:
        raise NotImplementedError

    def delete(self, *, event_id: str) -> None:
        raise NotImplementedError

    def build_payload(self, event: Event) -> dict:
        raise NotImplementedError


class InMemoryCalendarBackend(CalendarBackend):
    """A deterministic in-memory backend used for development and tests."""

    def __init__(self) -> None:
        self.upserts: dict[str | None, str] = {}

    def upsert(self, *, event_id: str | None, payload: dict) -> str:
        key = event_id
        if key is not None:
            self.upserts[key] = key
            return key
        new_id = payload.get("id") or f"mock-{uuid.uuid4()}"
        self.upserts[new_id] = new_id
        return new_id

    def delete(self, *, event_id: str) -> None:
        self.upserts.pop(event_id, None)

    def build_payload(self, event: Event) -> dict:
        reminders = []
        if event.reminder:
            reminders.append({"method": "popup", "minutes": 20})
        time_zone = get_settings().timezone
        if _is_all_day_event(event):
            return {
                "summary": event.title,
                "description": event.description or "",
                "start": {"date": event.start_dt.date().isoformat()},
                "end": {"date": (event.end_dt or event.start_dt).date().isoformat()},
                "location": event.venue_name,
                "reminders": {"useDefault": False, "overrides": reminders},
                "id": f"internal-{event.internal_event_id}",
            }
        return {
            "summary": event.title,
            "description": event.description or "",
            "start": {
                "dateTime": event.start_dt.astimezone(ZoneInfo(time_zone)).isoformat(),
                "timeZone": time_zone,
            },
            "end": {
                "dateTime": (event.end_dt or event.start_dt).astimezone(ZoneInfo(time_zone)).isoformat(),
                "timeZone": time_zone,
            },
            "location": event.venue_name,
            "reminders": {"useDefault": False, "overrides": reminders},
            "id": f"internal-{event.internal_event_id}",
        }


class RealGoogleCalendarBackend(CalendarBackend):
    """Best-effort Google Calendar backend that can be enabled at runtime."""

    def __init__(self, calendar_id: str, credentials):
        self.calendar_id = calendar_id
        self.credentials = credentials
        from googleapiclient.discovery import build
        self._build = build

    def upsert(self, *, event_id: str | None, payload: dict) -> str:
        payload = dict(payload)
        payload.pop("id", None)
        service = self._get_service()
        if event_id:
            service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=payload,
            ).execute()
            return event_id
        created = (
            service.events()
            .insert(calendarId=self.calendar_id, body=payload)
            .execute()
        )
        return created.get("id")

    def delete(self, *, event_id: str) -> None:
        service = self._get_service()
        service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()

    def _get_service(self):
        return self._build("calendar", "v3", credentials=self.credentials, cache_discovery=False)

    def build_payload(self, event: Event) -> dict:
        reminders = []
        if event.reminder:
            reminders.append({"method": "popup", "minutes": 20})
        time_zone = get_settings().timezone
        if _is_all_day_event(event):
            return {
                "summary": event.title,
                "description": event.description or "",
                "start": {"date": event.start_dt.date().isoformat()},
                "end": {"date": (event.end_dt or event.start_dt).date().isoformat()},
                "location": event.venue_name,
                "reminders": {"useDefault": False, "overrides": reminders},
            }
        return {
            "summary": event.title,
            "description": event.description or "",
            "start": {
                "dateTime": event.start_dt.astimezone(ZoneInfo(time_zone)).isoformat(),
                "timeZone": time_zone,
            },
            "end": {
                "dateTime": (event.end_dt or event.start_dt).astimezone(ZoneInfo(time_zone)).isoformat(),
                "timeZone": time_zone,
            },
            "location": event.venue_name,
            "reminders": {"useDefault": False, "overrides": reminders},
        }


class CalendarSyncer:
    """Synchronize proposed events into calendar with internal id mapping."""

    def __init__(self, backend: Optional[CalendarBackend] = None):
        self.backend = backend or InMemoryCalendarBackend()

    def sync_pending(self, database_url: Optional[str] = None) -> SyncStats:
        stats = SyncStats()
        with session_scope(database_url=database_url) as session:
            pending = session.execute(
                select(Event).where(Event.status.in_(["proposed", "ready", "synced"]))
            ).scalars().all()
            if not pending:
                return stats

            for event in pending:
                existing = session.execute(
                    select(CalendarMapping).where(
                        CalendarMapping.internal_event_id == event.internal_event_id
                    )
                ).scalar_one_or_none()
                if existing is None:
                    google_event_id = self.backend.upsert(
                        event_id=None,
                        payload=self._build_payload(event),
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
                    self.backend.upsert(
                        event_id=existing.google_event_id,
                        payload=self._build_payload(event),
                    )
                    existing.last_synced_at = datetime.now(timezone.utc)
                    existing.status = "synced"
                    stats.updated += 1
                event.status = "synced"

        return stats

    def _build_payload(self, event: Event) -> dict:
        payload = self.backend.build_payload(event)
        payload.setdefault("id", event.internal_event_id)
        return payload


def get_calendar_backend(settings: Optional[Settings] = None) -> CalendarBackend:
    settings = settings or get_settings()
    if not settings.google_calendar_id:
        return InMemoryCalendarBackend()

    credentials_path = Path(settings.google_credentials_file)
    token_path = Path(settings.google_token_file)
    if not credentials_path.exists() or not token_path.exists():
        return InMemoryCalendarBackend()

    from .google_auth import load_google_credentials

    credentials = load_google_credentials(token_path=token_path)
    return RealGoogleCalendarBackend(calendar_id=settings.google_calendar_id, credentials=credentials)


def _is_all_day_event(event: Event) -> bool:
    if event.end_dt is None:
        return False
    return (
        event.start_dt.hour == 0
        and event.start_dt.minute == 0
        and event.start_dt.second == 0
        and event.end_dt.hour == 0
        and event.end_dt.minute == 0
        and event.end_dt.second == 0
    )
