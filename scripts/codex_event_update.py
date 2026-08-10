#!/usr/bin/env python3
"""Create and resume a Codex-backed calendar update session."""

from __future__ import annotations

import argparse
from pathlib import Path

from curated_events.calendar_context import export_calendar_month_context
from curated_events.codex_research import (
    DEFAULT_HANDOFF_INSTRUCTIONS_PATH,
    DEFAULT_OUTPUT_FORMAT_PATH,
    DEFAULT_PREFERENCES_PATH,
    build_paths,
    build_scope,
    run_create_session,
    run_resume_session,
)
from curated_events.config import get_settings


DEFAULT_UPDATE_INSTRUCTIONS_PATH = Path("docs/update_instructions.md")
DEFAULT_UPDATE_REPORT_PATH = Path("preview_suggestions.txt")
DEFAULT_UPDATE_SESSION_PATH = Path(".codex_event_update_session.json")
DEFAULT_CALENDAR_CONTEXT_PATH = Path("agent_reports/calendar_context_latest.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Codex-backed calendar update sessions.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Start a new Codex calendar update session.")
    create_parser.add_argument("--preferences", default=str(DEFAULT_PREFERENCES_PATH))
    create_parser.add_argument("--instructions", default=str(DEFAULT_UPDATE_INSTRUCTIONS_PATH))
    create_parser.add_argument("--output-format", default=str(DEFAULT_OUTPUT_FORMAT_PATH))
    create_parser.add_argument("--handoff", default=str(DEFAULT_HANDOFF_INSTRUCTIONS_PATH))
    create_parser.add_argument("--report", default=str(DEFAULT_UPDATE_REPORT_PATH))
    create_parser.add_argument("--session-file", default=str(DEFAULT_UPDATE_SESSION_PATH))
    create_parser.add_argument("--calendar-context", default=str(DEFAULT_CALENDAR_CONTEXT_PATH))
    create_parser.add_argument("--month", default=None, help="Target month in YYYY-MM format. Defaults to the current month.")
    create_parser.add_argument("--start-date", default=None, help="Custom range start in YYYY-MM-DD format.")
    create_parser.add_argument("--end-date", default=None, help="Custom range end in YYYY-MM-DD format.")
    create_parser.add_argument("--limit", type=int, default=None, help="Maximum number of high-confidence events to return. Omit for no cap.")

    resume_parser = subparsers.add_parser("resume", help="Resume the saved Codex calendar update session.")
    resume_parser.add_argument("--preferences", default=str(DEFAULT_PREFERENCES_PATH))
    resume_parser.add_argument("--instructions", default=str(DEFAULT_UPDATE_INSTRUCTIONS_PATH))
    resume_parser.add_argument("--output-format", default=str(DEFAULT_OUTPUT_FORMAT_PATH))
    resume_parser.add_argument("--handoff", default=str(DEFAULT_HANDOFF_INSTRUCTIONS_PATH))
    resume_parser.add_argument("--report", default=str(DEFAULT_UPDATE_REPORT_PATH))
    resume_parser.add_argument("--session-file", default=str(DEFAULT_UPDATE_SESSION_PATH))
    resume_parser.add_argument("--calendar-context", default=str(DEFAULT_CALENDAR_CONTEXT_PATH))
    resume_parser.add_argument("--month", default=None, help="Target month in YYYY-MM format. Defaults to the current month.")
    resume_parser.add_argument("--start-date", default=None, help="Custom range start in YYYY-MM-DD format.")
    resume_parser.add_argument("--end-date", default=None, help="Custom range end in YYYY-MM-DD format.")
    resume_parser.add_argument("--limit", type=int, default=None, help="Maximum number of high-confidence events to keep. Omit for no cap.")
    resume_parser.add_argument("--prompt", default=None, help="Optional follow-up prompt override.")

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    paths = build_paths(
        repo_root=repo_root,
        preferences_path=Path(args.preferences),
        research_instructions_path=Path(args.instructions),
        output_format_path=Path(args.output_format),
        handoff_instructions_path=Path(args.handoff),
        report_path=Path(args.report),
        session_path=Path(args.session_file),
    )
    scope = build_scope(
        month=args.month,
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
    )
    settings = get_settings()
    calendar_context_path = repo_root / Path(args.calendar_context)
    calendar_context_text = export_calendar_month_context(
        month_start=scope.month_start,
        month_end=scope.month_end,
        output_path=calendar_context_path,
        settings=settings,
    )

    if args.command == "create":
        run_create_session(
            paths,
            scope,
            calendar_context_text=calendar_context_text,
            workflow_name="calendar update",
        )
    elif args.command == "resume":
        run_resume_session(
            paths,
            scope,
            prompt_override=args.prompt,
            calendar_context_text=calendar_context_text,
            workflow_name="calendar update",
        )
    else:
        parser.error("Unknown command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
