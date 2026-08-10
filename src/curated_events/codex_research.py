"""Helpers for running Codex-backed event research sessions."""

from __future__ import annotations

import calendar
import json
import re
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional


DEFAULT_REPORT_PATH = Path("agent_reports/event_research_latest.md")
DEFAULT_SESSION_PATH = Path(".codex_event_session.json")
DEFAULT_PREFERENCES_PATH = Path("docs/preferences.md")
DEFAULT_RESEARCH_INSTRUCTIONS_PATH = Path("docs/research_instructions.md")
DEFAULT_OUTPUT_FORMAT_PATH = Path("docs/output_format.md")
DEFAULT_HANDOFF_INSTRUCTIONS_PATH = Path("docs/handoff_instructions.md")
DEFAULT_LAST_MESSAGE_PATH = Path("agent_reports/event_research_last_message.md")


@dataclass(frozen=True)
class ResearchPaths:
    repo_root: Path
    preferences_path: Path
    research_instructions_path: Path
    output_format_path: Path
    handoff_instructions_path: Path
    report_path: Path
    last_message_path: Path
    session_path: Path


@dataclass(frozen=True)
class ResearchScope:
    month_label: str
    month_start: date
    month_end: date
    limit: int | None


def build_paths(
    *,
    repo_root: Path,
    preferences_path: Path = DEFAULT_PREFERENCES_PATH,
    research_instructions_path: Path = DEFAULT_RESEARCH_INSTRUCTIONS_PATH,
    output_format_path: Path = DEFAULT_OUTPUT_FORMAT_PATH,
    handoff_instructions_path: Path = DEFAULT_HANDOFF_INSTRUCTIONS_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    last_message_path: Path = DEFAULT_LAST_MESSAGE_PATH,
    session_path: Path = DEFAULT_SESSION_PATH,
) -> ResearchPaths:
    return ResearchPaths(
        repo_root=repo_root,
        preferences_path=repo_root / preferences_path,
        research_instructions_path=repo_root / research_instructions_path,
        output_format_path=repo_root / output_format_path,
        handoff_instructions_path=repo_root / handoff_instructions_path,
        report_path=repo_root / report_path,
        last_message_path=repo_root / last_message_path,
        session_path=repo_root / session_path,
    )


def load_preferences(preferences_path: Path) -> str:
    return load_markdown_file(preferences_path, "Preferences")


def load_markdown_file(path: Path, label: str) -> str:
    if not path.exists():
        raise RuntimeError(f"{label} file not found: {path}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"{label} file is empty: {path}. Fill it in before starting research.")
    return text


def build_scope(
    month: str | None = None,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    today: date | None = None,
    limit: int | None = 30,
) -> ResearchScope:
    if limit is not None and limit <= 0:
        raise RuntimeError("limit must be greater than 0")

    if month and (start_date or end_date):
        raise RuntimeError("month cannot be combined with start-date or end-date")
    if bool(start_date) != bool(end_date):
        raise RuntimeError("start-date and end-date must be provided together")

    if start_date and end_date:
        try:
            range_start = date.fromisoformat(start_date)
            range_end = date.fromisoformat(end_date)
        except ValueError as exc:
            raise RuntimeError("start-date and end-date must be in YYYY-MM-DD format") from exc
        if range_end < range_start:
            raise RuntimeError("end-date must be on or after start-date")
        return ResearchScope(
            month_label=f"{range_start.isoformat()}_to_{range_end.isoformat()}",
            month_start=range_start,
            month_end=range_end,
            limit=limit,
        )

    today = today or datetime.now().date()
    if month is None:
        year = today.year
        month_num = today.month
    else:
        try:
            year_str, month_str = month.split("-", 1)
            year = int(year_str)
            month_num = int(month_str)
        except (ValueError, AttributeError) as exc:
            raise RuntimeError("month must be in YYYY-MM format") from exc
        if month_num < 1 or month_num > 12:
            raise RuntimeError("month must be in YYYY-MM format")

    month_start = date(year, month_num, 1)
    last_day = calendar.monthrange(year, month_num)[1]
    month_end = date(year, month_num, last_day)
    return ResearchScope(
        month_label=f"{year:04d}-{month_num:02d}",
        month_start=month_start,
        month_end=month_end,
        limit=limit,
    )


def build_initial_prompt(
    preferences_text: str,
    research_instructions_text: str,
    output_format_text: str,
    report_path: Path,
    scope: ResearchScope,
    *,
    handoff_instructions_text: str = "",
    calendar_context_text: str | None = None,
    workflow_name: str = "monthly seed",
) -> str:
    limit_line = "- Do not impose an arbitrary cap; include all events that clearly clear the confidence bar.\n"
    if scope.limit is not None:
        limit_line = f"- Return at most {scope.limit} high-confidence events.\n"
    calendar_context_block = ""
    if calendar_context_text:
        calendar_context_block = (
            "<current_calendar_context>\n"
            f"{calendar_context_text}\n"
            "</current_calendar_context>\n\n"
        )
    handoff_block = ""
    if handoff_instructions_text:
        handoff_block = (
            "<handoff_instructions>\n"
            f"{handoff_instructions_text}\n"
            "</handoff_instructions>\n\n"
        )
    return (
        f"Search the web for upcoming events that match the user preferences below.\n"
        f"This is the {workflow_name} workflow.\n\n"
        "Runtime constraints:\n"
        "- Use live web search.\n"
        f"- Only include events occurring between {scope.month_start.isoformat()} and {scope.month_end.isoformat()}.\n"
        f"{limit_line}"
        "- If official late-stage tournament date slots exist in the target month but exact pairings are still unresolved, include them in the main event list as placeholder events instead of moving them to Search gaps.\n"
        "- Treat that as a hard validity rule. If your draft leaves those placeholders in Search gaps or omits them entirely, revise the report before writing the final output.\n"
        "- Every scheduled event in the final report must use one canonical New York / ET time expression only.\n"
        "- Do not leave any `Exact time` lines in venue-local wording or dual-time format.\n"
        f"- Write the final report to {report_path} as markdown.\n"
        "- In the final response, summarize the best events and mention where the report was written.\n\n"
        f"{calendar_context_block}"
        "<research_instructions>\n"
        f"{research_instructions_text}\n"
        "</research_instructions>\n\n"
        "<output_format>\n"
        f"{output_format_text}\n"
        "</output_format>\n\n"
        f"{handoff_block}"
        "<user_preferences>\n"
        f"{preferences_text}\n"
        "</user_preferences>\n"
    )


def build_resume_prompt(
    preferences_text: str,
    research_instructions_text: str,
    output_format_text: str,
    report_path: Path,
    scope: ResearchScope,
    *,
    handoff_instructions_text: str = "",
    calendar_context_text: str | None = None,
    workflow_name: str = "monthly seed",
) -> str:
    limit_line = "- Do not impose an arbitrary cap; keep all events that clearly clear the confidence bar.\n"
    if scope.limit is not None:
        limit_line = f"- Keep at most {scope.limit} high-confidence events in the report.\n"
    calendar_context_block = ""
    if calendar_context_text:
        calendar_context_block = (
            "<current_calendar_context>\n"
            f"{calendar_context_text}\n"
            "</current_calendar_context>\n\n"
        )
    handoff_block = ""
    if handoff_instructions_text:
        handoff_block = (
            "<handoff_instructions>\n"
            f"{handoff_instructions_text}\n"
            "</handoff_instructions>\n\n"
        )
    return (
        "Resume the event research session.\n"
        f"This is the {workflow_name} workflow.\n"
        "Refresh and improve the existing event recommendations using live web search.\n"
        f"Keep the results limited to events between {scope.month_start.isoformat()} and {scope.month_end.isoformat()}.\n"
        f"{limit_line}"
        "- Keep official late-stage tournament placeholders in the main event list when their dates are known but pairings are unresolved; do not leave them in Search gaps.\n"
        "- Treat that as a hard validity rule. If the report still leaves them in Search gaps or omits them, revise it before finishing.\n"
        "- Every scheduled event in the final report must use one canonical New York / ET time expression only.\n"
        "- Do not leave any `Exact time` lines in venue-local wording or dual-time format.\n"
        f"Update the markdown report at {report_path}.\n"
        "Keep the report focused on the best upcoming opportunities and remove stale or weak matches.\n\n"
        f"{calendar_context_block}"
        "<research_instructions>\n"
        f"{research_instructions_text}\n"
        "</research_instructions>\n\n"
        "<output_format>\n"
        f"{output_format_text}\n"
        "</output_format>\n\n"
        f"{handoff_block}"
        "<user_preferences>\n"
        f"{preferences_text}\n"
        "</user_preferences>\n"
    )


def read_session_metadata(session_path: Path) -> dict:
    if not session_path.exists():
        raise RuntimeError(f"Session metadata not found: {session_path}")
    return json.loads(session_path.read_text(encoding="utf-8"))


def write_session_metadata(session_path: Path, data: dict) -> None:
    session_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _stream_and_capture_thread_id(process, session_path: Path, report_path: Path) -> int:
    thread_id: Optional[str] = None
    report_written = False
    report_written_at: float | None = None
    forced_stop = False

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if payload.get("type") == "thread.started":
            thread_id = payload.get("thread_id")
        item = payload.get("item")
        if isinstance(item, dict) and item.get("type") == "file_change" and item.get("status") == "completed":
            changes = item.get("changes") or []
            for change in changes:
                if change.get("path") == str(report_path) and change.get("kind") in {"add", "update"}:
                    report_written = True
                    report_written_at = time.monotonic()

        if report_written and report_written_at is not None:
            elapsed = time.monotonic() - report_written_at
            if elapsed >= 5 and process.poll() is None:
                process.send_signal(signal.SIGINT)
                forced_stop = True
                break

    if forced_stop and process.poll() is None:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    return_code = process.wait()
    if return_code != 0 and not (forced_stop and report_written):
        raise RuntimeError(f"Codex exited with status {return_code}")
    if not thread_id:
        raise RuntimeError("Codex did not return a thread id.")

    write_session_metadata(
        session_path,
        {
            "thread_id": thread_id,
            "report_path": str(report_path),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return return_code


def validate_report_output(report_path: Path) -> None:
    if not report_path.exists():
        raise RuntimeError(f"Expected report was not written: {report_path}")

    text = report_path.read_text(encoding="utf-8")
    invalid_patterns = [
        r"(?im)^- Exact time:\s*.*local kickoff.*$",
        r"(?im)^- Exact time:\s*.*local time.*$",
        r"(?im)^- Exact time:\s*.*\bET\b\s*/\s*.*$",
        r"(?im)^- Exact time:\s*.*\bBST\b\s*/\s*.*$",
        r"(?im)^- Exact time:\s*.*\bCEST\b\s*/\s*.*$",
        r"(?im)^- Exact time:\s*.*\bCET\b\s*/\s*.*$",
    ]
    for pattern in invalid_patterns:
        if re.search(pattern, text):
            raise RuntimeError(
                "Research report contains invalid time formatting; rerun required before calendar apply."
            )


def run_create_session(
    paths: ResearchPaths,
    scope: ResearchScope,
    *,
    calendar_context_text: str | None = None,
    workflow_name: str = "monthly seed",
) -> None:
    preferences_text = load_preferences(paths.preferences_path)
    research_instructions_text = load_markdown_file(paths.research_instructions_path, "Research instructions")
    output_format_text = load_markdown_file(paths.output_format_path, "Output format")
    handoff_instructions_text = load_markdown_file(paths.handoff_instructions_path, "Handoff instructions")
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)
    paths.last_message_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_initial_prompt(
        preferences_text,
        research_instructions_text,
        output_format_text,
        paths.report_path,
        scope,
        handoff_instructions_text=handoff_instructions_text,
        calendar_context_text=calendar_context_text,
        workflow_name=workflow_name,
    )
    command = [
        "codex",
        "--search",
        "exec",
        "--skip-git-repo-check",
        "--json",
        "--output-last-message",
        str(paths.last_message_path),
        "-C",
        str(paths.repo_root),
        prompt,
    ]
    process = subprocess.Popen(
        command,
        cwd=paths.repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _stream_and_capture_thread_id(process, paths.session_path, paths.report_path)
    validate_report_output(paths.report_path)
    metadata = read_session_metadata(paths.session_path)
    metadata["month"] = scope.month_label
    metadata["limit"] = scope.limit
    write_session_metadata(paths.session_path, metadata)


def run_resume_session(
    paths: ResearchPaths,
    scope: ResearchScope,
    prompt_override: str | None = None,
    *,
    calendar_context_text: str | None = None,
    workflow_name: str = "monthly seed",
) -> None:
    session = read_session_metadata(paths.session_path)
    thread_id = session.get("thread_id")
    if not thread_id:
        raise RuntimeError(f"No thread_id present in {paths.session_path}")

    preferences_text = load_preferences(paths.preferences_path)
    research_instructions_text = load_markdown_file(paths.research_instructions_path, "Research instructions")
    output_format_text = load_markdown_file(paths.output_format_path, "Output format")
    handoff_instructions_text = load_markdown_file(paths.handoff_instructions_path, "Handoff instructions")
    prompt = prompt_override or build_resume_prompt(
        preferences_text,
        research_instructions_text,
        output_format_text,
        paths.report_path,
        scope,
        handoff_instructions_text=handoff_instructions_text,
        calendar_context_text=calendar_context_text,
        workflow_name=workflow_name,
    )
    command = [
        "codex",
        "exec",
        "resume",
        str(thread_id),
        "--json",
        "--output-last-message",
        str(paths.last_message_path),
        prompt,
    ]
    process = subprocess.Popen(
        command,
        cwd=paths.repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _stream_and_capture_thread_id(process, paths.session_path, paths.report_path)
    validate_report_output(paths.report_path)
    session["month"] = scope.month_label
    session["limit"] = scope.limit
    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_session_metadata(paths.session_path, session)
