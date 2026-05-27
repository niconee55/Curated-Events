"""CLI entrypoint for curated-events."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .calendar_sync import CalendarSyncer, get_calendar_backend
from .config import get_settings
from .db import init_db
from .google_auth import ensure_google_credentials
from .pipeline import PipelineResult, run_sync_cycle
from .report_sync import apply_report_to_calendar, rollback_snapshot
from .scheduler import run_monthly_sync


def _info_command() -> None:
    settings = get_settings()
    print("curated-events")
    print(f"version: {__version__}")
    print(f"calendar: {settings.google_calendar_name}")


def _db_init_command(database_url: str | None) -> None:
    init_db(database_url=database_url)
    print("database initialized")


def _sync_command(database_url: str | None) -> None:
    result: PipelineResult = run_sync_cycle(database_url=database_url)
    syncer = CalendarSyncer(backend=get_calendar_backend())
    sync_result = syncer.sync_pending(database_url=database_url)
    print("discovery:", result.as_dict())
    print(
        "calendar:",
        {
            "created": sync_result.created,
            "updated": sync_result.updated,
            "skipped": sync_result.skipped,
        },
    )


def _scheduler_command(database_url: str | None, max_ticks: int | None) -> None:
    # Run a short test cycle by default? In CLI mode we keep this blocking.
    run_monthly_sync(database_url=database_url, max_ticks=max_ticks)
    print("scheduler stopped")


def _google_auth_command() -> None:
    settings = get_settings()
    if not settings.google_credentials_file:
        raise RuntimeError("GOOGLE_CREDENTIALS_FILE is not configured.")
    credentials_path = Path(settings.google_credentials_file)
    if not credentials_path.exists():
        raise RuntimeError(f"Google credentials file not found: {credentials_path}")

    token_path = Path(settings.google_token_file)
    ensure_google_credentials(credentials_path=credentials_path, token_path=token_path)
    print(f"google auth: token saved to {token_path}")


def _report_apply_command(
    report_path: str,
    snapshot_path: str,
    database_url: str | None,
    include_lower_priority: bool,
) -> None:
    settings = get_settings()
    backend = get_calendar_backend(settings=settings)
    if settings.google_calendar_id == "":
        raise RuntimeError("GOOGLE_CALENDAR_ID is not configured.")
    if backend.__class__.__name__ == "InMemoryCalendarBackend":
        raise RuntimeError("Google Calendar backend is not active. Run `curated-events google-auth` first.")

    scope = "all" if include_lower_priority else "high-confidence"
    result = apply_report_to_calendar(
        Path(report_path),
        database_url=database_url,
        timezone_name=settings.timezone,
        scope=scope,
        calendar_backend=backend,
        calendar_id=settings.google_calendar_id,
        snapshot_path=Path(snapshot_path),
    )
    print(
        "report-apply:",
        {
            "calendar_id": result.calendar_id,
            "scope": result.scope,
            "imported": result.imported,
            "created": result.created,
            "updated": result.updated,
            "snapshot": str(result.snapshot_path),
        },
    )


def _report_rollback_command(snapshot_path: str, database_url: str | None) -> None:
    settings = get_settings()
    backend = get_calendar_backend(settings=settings)
    if backend.__class__.__name__ == "InMemoryCalendarBackend":
        raise RuntimeError("Google Calendar backend is not active. Run `curated-events google-auth` first.")

    removed = rollback_snapshot(Path(snapshot_path), database_url=database_url, calendar_backend=backend)
    print(
        "report-rollback:",
        {
            "removed": removed,
            "snapshot": snapshot_path,
        },
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="curated-events")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    subparsers.add_parser("info", help="Print configured runtime settings summary.")

    db_parser = subparsers.add_parser("db", help="Database operations.")
    db_sub = db_parser.add_subparsers(dest="db_command")
    db_sub.required = True
    db_init_parser = db_sub.add_parser("init", help="Create tables and schemas.")
    db_init_parser.add_argument("--database-url", default=None)

    sync_parser = subparsers.add_parser("sync", help="Run discovery and sync once.")
    sync_parser.add_argument("--database-url", default=None)

    scheduler_parser = subparsers.add_parser("scheduler", help="Run monthly discovery + sync scheduler.")
    scheduler_parser.add_argument("--database-url", default=None)
    scheduler_parser.add_argument("--max-ticks", type=int, default=None)

    subparsers.add_parser("google-auth", help="Run local Google OAuth flow and save token.")

    report_parser = subparsers.add_parser("report", help="Apply or rollback a reviewed report.")
    report_sub = report_parser.add_subparsers(dest="report_command")
    report_sub.required = True

    report_apply_parser = report_sub.add_parser("apply", help="Import a reviewed report and sync it to Google Calendar.")
    report_apply_parser.add_argument("--report", default="preview_suggestions.txt")
    report_apply_parser.add_argument("--snapshot", default="agent_reports/report_apply_snapshot.json")
    report_apply_parser.add_argument("--database-url", default=None)
    report_apply_parser.add_argument("--include-lower-priority", action="store_true")

    report_rollback_parser = report_sub.add_parser("rollback", help="Delete events created by a previous report apply.")
    report_rollback_parser.add_argument("--snapshot", default="agent_reports/report_apply_snapshot.json")
    report_rollback_parser.add_argument("--database-url", default=None)

    args = parser.parse_args(argv)
    if args.command == "info":
        _info_command()
    elif args.command == "db":
        if args.db_command == "init":
            _db_init_command(args.database_url)
        else:
            parser.error("Unknown db command")
    elif args.command == "sync":
        _sync_command(args.database_url)
    elif args.command == "scheduler":
        _scheduler_command(args.database_url, args.max_ticks)
    elif args.command == "google-auth":
        _google_auth_command()
    elif args.command == "report":
        if args.report_command == "apply":
            _report_apply_command(
                args.report,
                args.snapshot,
                args.database_url,
                args.include_lower_priority,
            )
        elif args.report_command == "rollback":
            _report_rollback_command(args.snapshot, args.database_url)
        else:
            parser.error("Unknown report command")
    else:
        parser.error("Unknown command")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
