#!/usr/bin/env python3
"""Create and resume a Codex-backed event research session."""

from __future__ import annotations

import argparse
from pathlib import Path

from curated_events.codex_research import (
    DEFAULT_HANDOFF_INSTRUCTIONS_PATH,
    DEFAULT_OUTPUT_FORMAT_PATH,
    DEFAULT_PREFERENCES_PATH,
    DEFAULT_REPORT_PATH,
    DEFAULT_RESEARCH_INSTRUCTIONS_PATH,
    DEFAULT_SESSION_PATH,
    build_scope,
    build_paths,
    run_create_session,
    run_resume_session,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Codex-backed event research sessions.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Start a new Codex event research session.")
    create_parser.add_argument("--preferences", default=str(DEFAULT_PREFERENCES_PATH))
    create_parser.add_argument("--instructions", default=str(DEFAULT_RESEARCH_INSTRUCTIONS_PATH))
    create_parser.add_argument("--output-format", default=str(DEFAULT_OUTPUT_FORMAT_PATH))
    create_parser.add_argument("--handoff", default=str(DEFAULT_HANDOFF_INSTRUCTIONS_PATH))
    create_parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    create_parser.add_argument("--session-file", default=str(DEFAULT_SESSION_PATH))
    create_parser.add_argument("--month", default=None, help="Target month in YYYY-MM format. Defaults to the current month.")
    create_parser.add_argument("--limit", type=int, default=None, help="Maximum number of high-confidence events to return. Omit for no cap.")

    resume_parser = subparsers.add_parser("resume", help="Resume the saved Codex event research session.")
    resume_parser.add_argument("--preferences", default=str(DEFAULT_PREFERENCES_PATH))
    resume_parser.add_argument("--instructions", default=str(DEFAULT_RESEARCH_INSTRUCTIONS_PATH))
    resume_parser.add_argument("--output-format", default=str(DEFAULT_OUTPUT_FORMAT_PATH))
    resume_parser.add_argument("--handoff", default=str(DEFAULT_HANDOFF_INSTRUCTIONS_PATH))
    resume_parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    resume_parser.add_argument("--session-file", default=str(DEFAULT_SESSION_PATH))
    resume_parser.add_argument("--month", default=None, help="Target month in YYYY-MM format. Defaults to the current month.")
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
    scope = build_scope(month=args.month, limit=args.limit)

    if args.command == "create":
        run_create_session(paths, scope, workflow_name="monthly seed")
    elif args.command == "resume":
        run_resume_session(paths, scope, prompt_override=args.prompt, workflow_name="monthly seed")
    else:
        parser.error("Unknown command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
