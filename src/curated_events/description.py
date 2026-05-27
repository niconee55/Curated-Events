"""Description helpers for generated calendar entries."""

from __future__ import annotations

from .schemas import EventCandidate


def build_description(candidate: EventCandidate) -> str:
    parts = [candidate.description or ""]
    if candidate.ticket_url:
        parts.append(f"Tickets: {candidate.ticket_url}")
    if candidate.price_min is not None or candidate.price_max is not None:
        if candidate.price_min is not None and candidate.price_max is not None:
            parts.append(f"Price range: {candidate.price_min}-{candidate.price_max}")
        elif candidate.price_min is not None:
            parts.append(f"Price from: {candidate.price_min}")
        elif candidate.price_max is not None:
            parts.append(f"Price up to: {candidate.price_max}")
    parts.append(f"Category: {candidate.category}")
    if candidate.entity:
        parts.append(f"Entity: {candidate.entity}")
    return "\n".join([p for p in parts if p])


def enrich_with_llm(candidate: EventCandidate) -> str:
    """Placeholder hook for LLM-based enrichment."""
    return build_description(candidate)
