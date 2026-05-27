"""Scheduler integration for periodic discovery + sync."""

from __future__ import annotations

from typing import Optional

from .calendar_sync import CalendarSyncer, get_calendar_backend
from .pipeline import run_sync_cycle


def run_monthly_sync(
    *,
    database_url: Optional[str] = None,
    max_ticks: Optional[int] = None,
) -> int:
    """Run discovery + sync.

    If max_ticks is provided, run that many immediate iterations for testability.
    Otherwise, run a true recurring APScheduler monthly job.
    """

    if max_ticks is not None:
        syncer = CalendarSyncer(backend=get_calendar_backend())
        ticks = 0
        for _ in range(max_ticks):
            run_sync_cycle(database_url=database_url)
            syncer.sync_pending(database_url=database_url)
            ticks += 1
        return ticks

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except Exception as exc:
        raise RuntimeError("APScheduler is required for scheduler command.") from exc

    ticks = 0
    syncer = CalendarSyncer(backend=get_calendar_backend())

    scheduler = BlockingScheduler()

    @scheduler.scheduled_job(
        CronTrigger(day=1, hour=3, minute=0, timezone="America/New_York"),
        id="monthly_discovery_and_sync",
        replace_existing=True,
    )
    def _run_job():
        nonlocal ticks
        result = run_sync_cycle(database_url=database_url)
        syncer.sync_pending(database_url=database_url)
        ticks += 1
        result.synced_records = ticks

    scheduler.start()
    return ticks
