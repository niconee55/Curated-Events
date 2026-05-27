from __future__ import annotations

from datetime import date, datetime

from curated_events.calendar_context import CalendarContextEvent, render_calendar_context


def test_render_calendar_context_with_existing_events():
    events = [
        CalendarContextEvent(
            title="Real Madrid vs Bayern Munich",
            start=datetime.fromisoformat("2026-04-07T15:00:00-04:00"),
            end=datetime.fromisoformat("2026-04-07T17:00:00-04:00"),
            all_day=False,
            location="Santiago Bernabeu",
            description="Semifinal race context.",
            google_event_id="abc123",
        ),
        CalendarContextEvent(
            title="The Great Divide by Noah Kahan",
            start=date.fromisoformat("2026-04-03"),
            end=date.fromisoformat("2026-04-04"),
            all_day=True,
            location="",
            description="Album release.",
            google_event_id="def456",
        ),
    ]

    rendered = render_calendar_context(
        events=events,
        calendar_name="Curated Events",
        month_start=date.fromisoformat("2026-04-01"),
        month_end=date.fromisoformat("2026-04-30"),
        timezone_name="America/New_York",
    )

    assert "Current Calendar Context" in rendered
    assert "Existing events in window: 2" in rendered
    assert "Real Madrid vs Bayern Munich" in rendered
    assert "Tue, Apr 7, 2026, 3:00 PM to 5:00 PM America/New_York" in rendered
    assert "The Great Divide by Noah Kahan" in rendered
    assert "Fri, Apr 3, 2026 (all day)" in rendered


def test_render_calendar_context_with_no_events():
    rendered = render_calendar_context(
        events=[],
        calendar_name="Curated Events",
        month_start=date.fromisoformat("2026-04-01"),
        month_end=date.fromisoformat("2026-04-30"),
        timezone_name="America/New_York",
    )

    assert "No events are currently on the calendar" in rendered
