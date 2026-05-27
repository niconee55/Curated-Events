from __future__ import annotations

from datetime import datetime, timezone

from curated_events.dedupe import build_dedupe_key
from curated_events.ranking import rank_candidate
from curated_events.schemas import EventCandidate


def test_dedupe_key_is_stable_for_matching_input():
    start = datetime(2026, 4, 1, 18, 0, tzinfo=timezone.utc)
    key_1 = build_dedupe_key("PSG vs Real Madrid", start, "Staples Center")
    key_2 = build_dedupe_key("PSG vs Real Madrid", start, " staples center ")
    assert key_1 == key_2


def test_rank_candidate_marks_high_priority_soccer_match():
    candidate = EventCandidate(
        title="UEFA Champions League Final: Paris vs Real Madrid",
        category="soccer",
        entity="Real Madrid",
        start_dt=datetime(2026, 4, 1, tzinfo=timezone.utc),
        source_name="test",
        raw_confidence=0.95,
    )
    score, reminder = rank_candidate(candidate)
    assert score >= 1.0
    assert reminder is True
