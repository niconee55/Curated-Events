"""Ranking heuristics and candidate classification."""

from __future__ import annotations

from typing import Tuple

from .schemas import EventCandidate


BASE_WEIGHTS = {
    "ucl_knockout": 1.0,
    "ucl": 0.8,
    "real_madrid_big": 0.9,
    "france_nt_tournament": 0.9,
    "psg_ucl": 0.75,
    "premier_big": 0.75,
    "world_cup_euros": 1.0,
    "playoffs_marquee": 0.7,
    "nintendo_flagship": 0.7,
    "anime_favorite": 0.65,
    "anime_similar": 0.5,
    "noah_kahan": 0.7,
    "manhattan_culture": 0.45,
}

BOOST_KEYWORDS = {
    "knockout": 0.1,
    "semifinal": 0.1,
    "final": 0.1,
    "rivalry": 0.05,
    "clasico": 0.05,
    "ny": 0.05,
    "new york": 0.05,
    "mario": 0.05,
    "zelda": 0.05,
}

HIGHEST_PRIORITY_THRESHOLD = 0.85
REMINDER_THRESHOLD = 0.75


def classify_candidate(candidate: EventCandidate) -> str:
    title_lower = candidate.title.lower()
    cat = candidate.category.lower()
    entity = (candidate.entity or "").lower()

    if "champions league" in cat:
        if any(k in title_lower for k in ["quarter", "semi", "final"]):
            return "ucl_knockout"
        return "ucl"
    if "real madrid" in entity:
        return "real_madrid_big"
    if "france" in entity and "national" in cat:
        return "france_nt_tournament"
    if "psg" in entity and "champions league" in cat:
        return "psg_ucl"
    if "premier league" in cat:
        return "premier_big"
    if any(k in title_lower for k in ["world cup", "euro"]):
        return "world_cup_euros"
    if any(k in title_lower for k in ["playoff", "super bowl", "nba finals", "world series"]):
        return "playoffs_marquee"
    if any(k in title_lower for k in ["nintendo direct", "game awards", "zelda", "mario"]):
        return "nintendo_flagship"
    if any(k in title_lower for k in ["jujutsu kaisen", "demon slayer", "naruto", "frieren", "vinland", "fullmetal", "hunter"]):
        return "anime_favorite"
    if "anime" in cat:
        return "anime_similar"
    if "noah kahan" in title_lower:
        return "noah_kahan"
    if any(k in title_lower for k in ["museum", "comedy", "jazz", "moma", "blue note"]):
        return "manhattan_culture"
    return "unknown"


def rank_candidate(candidate: EventCandidate) -> Tuple[float, bool]:
    classification = classify_candidate(candidate)
    base = BASE_WEIGHTS.get(classification, 0.0)

    score = base + candidate.raw_confidence * 0.2
    text = f"{candidate.title} {candidate.entity or ''}".lower()
    for keyword, boost in BOOST_KEYWORDS.items():
        if keyword in text:
            score += boost

    score = min(score, 1.2)
    reminder = score >= HIGHEST_PRIORITY_THRESHOLD or (
        score >= REMINDER_THRESHOLD and classification in {"ucl_knockout", "real_madrid_big", "france_nt_tournament"}
    )
    return score, reminder
