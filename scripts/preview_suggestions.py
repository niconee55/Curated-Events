#!/usr/bin/env python3
"""Run discovery only and write ranked event suggestions to a text file."""

from __future__ import annotations

import argparse
from datetime import timezone
from pathlib import Path
from dataclasses import dataclass

from sqlalchemy import select

from curated_events.db import init_db, session_scope
from curated_events.models import Event
from curated_events.pipeline import run_sync_cycle


@dataclass(frozen=True)
class PreviewEvent:
    title: str
    priority: float
    reminder: bool
    start_dt: object
    category: str
    source_name: str
    entity: str | None
    venue_name: str | None
    venue_city: str | None
    venue_country: str | None
    ticket_url: str | None
    description: str | None


def _build_event_block(index: int, event: PreviewEvent) -> str:
    lines = [
        f"{index}. {event.title}",
        f"   Score: {event.priority:.2f} | Reminder: {'yes' if event.reminder else 'no'}",
        f"   When: {event.start_dt.astimezone(timezone.utc).isoformat()}",
        f"   Category: {event.category}",
        f"   Source: {event.source_name}",
    ]

    if event.entity:
        lines.append(f"   Entity: {event.entity}")
    if event.venue_name or event.venue_city or event.venue_country:
        venue_parts = [part for part in [event.venue_name, event.venue_city, event.venue_country] if part]
        lines.append(f"   Venue: {', '.join(venue_parts)}")
    if event.ticket_url:
        lines.append(f"   Tickets: {event.ticket_url}")
    if event.description:
        description = " ".join(line.strip() for line in event.description.splitlines() if line.strip())
        lines.append(f"   Notes: {description}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview curated event suggestions without calendar sync.")
    parser.add_argument(
        "--output",
        default="preview_suggestions.txt",
        help="Path to the text file that will receive the ranked suggestions.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Optional database URL override. Defaults to the configured DATABASE_URL.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of events to include in the output file.",
    )
    args = parser.parse_args()

    init_db(database_url=args.database_url)
    result = run_sync_cycle(database_url=args.database_url)

    with session_scope(database_url=args.database_url) as session:
        rows = session.execute(
            select(Event).order_by(Event.priority.desc(), Event.start_dt.asc(), Event.title.asc())
        ).scalars().all()
        events = [
            PreviewEvent(
                title=row.title,
                priority=row.priority,
                reminder=row.reminder,
                start_dt=row.start_dt,
                category=row.category,
                source_name=row.source_name,
                entity=row.entity,
                venue_name=row.venue_name,
                venue_city=row.venue_city,
                venue_country=row.venue_country,
                ticket_url=row.ticket_url,
                description=row.description,
            )
            for row in rows
        ]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    selected = events[: max(args.limit, 0)]
    lines = [
        "Curated Events Preview",
        "",
        f"Candidates seen: {result.candidates}",
        f"Inserted this run: {result.inserted}",
        f"Skipped duplicate: {result.skipped_duplicate}",
        f"Skipped low confidence: {result.skipped_low_confidence}",
        f"Source logs: {', '.join(result.logs) if result.logs else 'none'}",
        "",
        f"Events included: {len(selected)}",
        "",
    ]

    if not selected:
        lines.append("No events were persisted by the discovery run.")
    else:
        for index, event in enumerate(selected, start=1):
            lines.append(_build_event_block(index, event))
            lines.append("")

    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"wrote preview to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
