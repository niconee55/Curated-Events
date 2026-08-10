from __future__ import annotations

import json
from pathlib import Path

import pytest

from curated_events.codex_research import (
    DEFAULT_HANDOFF_INSTRUCTIONS_PATH,
    build_scope,
    build_initial_prompt,
    build_paths,
    build_resume_prompt,
    load_markdown_file,
    load_preferences,
    read_session_metadata,
    write_session_metadata,
)


def test_load_preferences_rejects_empty_file(tmp_path: Path):
    preferences = tmp_path / "preferences.md"
    preferences.write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError, match="empty"):
        load_preferences(preferences)


def test_load_markdown_file_rejects_missing_file(tmp_path: Path):
    with pytest.raises(RuntimeError, match="not found"):
        load_markdown_file(tmp_path / "missing.md", "Output format")


def test_prompt_includes_preferences_and_report_path(tmp_path: Path):
    report_path = tmp_path / "report.md"
    preferences_text = "- Soccer first\n- NYC"
    research_instructions_text = "Use official sources."
    output_format_text = "Include a one-sentence description."
    scope = build_scope(month="2026-04", limit=30)

    initial = build_initial_prompt(
        preferences_text,
        research_instructions_text,
        output_format_text,
        report_path,
        scope,
        handoff_instructions_text="Leave notes for the updater.",
        calendar_context_text="# Current Calendar Context",
        workflow_name="calendar update",
    )
    resumed = build_resume_prompt(
        preferences_text,
        research_instructions_text,
        output_format_text,
        report_path,
        scope,
        handoff_instructions_text="Leave notes for the updater.",
        calendar_context_text="# Current Calendar Context",
        workflow_name="calendar update",
    )

    assert preferences_text in initial
    assert research_instructions_text in initial
    assert output_format_text in initial
    assert str(report_path) in initial
    assert "2026-04-01" in initial
    assert "2026-04-30" in initial
    assert "at most 30 high-confidence events" in initial
    assert "calendar update workflow" in initial
    assert "<current_calendar_context>" in initial
    assert "Leave notes for the updater." in initial
    assert preferences_text in resumed
    assert research_instructions_text in resumed
    assert output_format_text in resumed
    assert str(report_path) in resumed
    assert "2026-04-01" in resumed
    assert "2026-04-30" in resumed
    assert "at most 30 high-confidence events" in resumed
    assert "calendar update workflow" in resumed
    assert "<current_calendar_context>" in resumed
    assert "Leave notes for the updater." in resumed


def test_prompt_supports_no_limit(tmp_path: Path):
    report_path = tmp_path / "report.md"
    scope = build_scope(month="2026-04", limit=None)

    initial = build_initial_prompt("prefs", "instr", "format", report_path, scope)
    resumed = build_resume_prompt("prefs", "instr", "format", report_path, scope)

    assert "Do not impose an arbitrary cap" in initial
    assert "Do not impose an arbitrary cap" in resumed
    assert "at most" not in initial
    assert "at most" not in resumed


def test_session_metadata_round_trip(tmp_path: Path):
    session_path = tmp_path / ".codex_event_session.json"
    data = {"thread_id": "abc123", "report_path": "agent_reports/event_research_latest.md"}

    write_session_metadata(session_path, data)

    assert json.loads(session_path.read_text(encoding="utf-8")) == data
    assert read_session_metadata(session_path) == data


def test_build_paths_resolves_from_repo_root(tmp_path: Path):
    paths = build_paths(repo_root=tmp_path)

    assert paths.preferences_path == tmp_path / "docs/preferences.md"
    assert paths.research_instructions_path == tmp_path / "docs/research_instructions.md"
    assert paths.output_format_path == tmp_path / "docs/output_format.md"
    assert paths.handoff_instructions_path == tmp_path / DEFAULT_HANDOFF_INSTRUCTIONS_PATH
    assert paths.report_path == tmp_path / "agent_reports/event_research_latest.md"
    assert paths.last_message_path == tmp_path / "agent_reports/event_research_last_message.md"
    assert paths.session_path == tmp_path / ".codex_event_session.json"


def test_build_scope_supports_explicit_month_and_limit():
    scope = build_scope(month="2026-02", limit=30)

    assert scope.month_label == "2026-02"
    assert scope.month_start.isoformat() == "2026-02-01"
    assert scope.month_end.isoformat() == "2026-02-28"
    assert scope.limit == 30


def test_build_scope_supports_no_limit():
    scope = build_scope(month="2026-02", limit=None)

    assert scope.month_label == "2026-02"
    assert scope.limit is None


def test_build_scope_supports_explicit_date_range():
    scope = build_scope(start_date="2026-08-01", end_date="2026-11-30", limit=None)

    assert scope.month_label == "2026-08-01_to_2026-11-30"
    assert scope.month_start.isoformat() == "2026-08-01"
    assert scope.month_end.isoformat() == "2026-11-30"
    assert scope.limit is None


def test_build_scope_rejects_bad_inputs():
    with pytest.raises(RuntimeError, match="YYYY-MM"):
        build_scope(month="2026/04", limit=30)

    with pytest.raises(RuntimeError, match="greater than 0"):
        build_scope(month="2026-04", limit=0)

    with pytest.raises(RuntimeError, match="provided together"):
        build_scope(start_date="2026-08-01")

    with pytest.raises(RuntimeError, match="cannot be combined"):
        build_scope(month="2026-08", start_date="2026-08-01", end_date="2026-11-30")

    with pytest.raises(RuntimeError, match="on or after"):
        build_scope(start_date="2026-11-30", end_date="2026-08-01")
