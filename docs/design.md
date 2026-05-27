# Curated Events Design

## Product
Curated Events is a personal event-discovery and Google Calendar workflow built around a report-first process:
- a seed agent searches the web for a broad monthly slate of relevant events
- the user reviews the generated markdown report
- the reviewed report is applied to a dedicated Google Calendar
- a later update agent revisits the same month to replace placeholders and sharpen context

The current production path is the Codex-backed seed/update workflow, not the older built-in discovery pipeline.

## Architecture
There are three main layers:

### 1. Research
- Seed agent: [scripts/codex_event_research.py](../scripts/codex_event_research.py)
- Update agent: [scripts/codex_event_update.py](../scripts/codex_event_update.py)
- Prompt inputs:
  - [preferences.md](preferences.md)
  - [research_instructions.md](research_instructions.md)
  - [update_instructions.md](update_instructions.md)
  - [output_format.md](output_format.md)
  - [handoff_instructions.md](handoff_instructions.md)

The seed agent is intentionally broader. It should capture the important monthly slate, including placeholders for major tournament rounds and some adjacent interests. The update agent is narrower and should improve context, replace placeholders, and revise the month using the current calendar state as input.

### 2. Report Import and Persistence
- Report parser/importer: [src/curated_events/report_sync.py](../src/curated_events/report_sync.py)
- Database models: [src/curated_events/models.py](../src/curated_events/models.py)
- Default DB: local SQLite

The importer turns the markdown report into concrete event rows, expands recurring items when needed, and normalizes scheduled times into New York time for calendar use.

### 3. Google Calendar Sync
- Calendar sync backend: [src/curated_events/calendar_sync.py](../src/curated_events/calendar_sync.py)
- CLI entrypoints: [src/curated_events/cli.py](../src/curated_events/cli.py)

Calendar writes are applied only to the configured `Curated Events` calendar. Every apply writes a rollback snapshot so the current applied report can be removed safely later.

## Data Flow
Typical monthly flow:
1. Run the seed agent for a target month.
2. Review `preview_suggestions.txt`.
3. Apply the report to Google Calendar.
4. Later, run the update agent for the same month.
5. Roll back the previous snapshot and reapply the refreshed report.

Key artifacts:
- `preview_suggestions.txt`: current reviewed report
- `agent_reports/report_apply_snapshot.json`: rollback snapshot for the currently applied calendar version
- `.codex_event_session_*.json`: session metadata for seed runs
- `.codex_event_update_session.json`: session metadata for update runs
- `agent_reports/calendar_context_latest.md`: exported current calendar context for update runs

## Preference Model
The system is tuned around a strong ordering:
1. Soccer first
2. Major tournament and marquee adjacent sports
3. Major releases that fit the taste profile
4. Manhattan culture, film, museum, and jazz as secondary items

Important current rules:
- late-stage Champions League matches should be surfaced aggressively
- official semifinal placeholder dates belong in the main list when pairings are still unknown
- Premier League is the only domestic league with a deliberately looser inclusion bar
- women's club soccer is normally excluded unless it is truly global-marquee
- timed events should be represented in New York time
- release-style items should remain all-day

## Safety and Rollback
The workflow is designed to be reversible:
- apply command writes a snapshot
- rollback command removes the events created from that snapshot
- report application is scoped to the configured calendar only

Commands:
```bash
python3 -m curated_events.cli report apply --report preview_suggestions.txt --snapshot agent_reports/report_apply_snapshot.json --include-lower-priority
python3 -m curated_events.cli report rollback --snapshot agent_reports/report_apply_snapshot.json
```

## Legacy Pipeline
The repo still contains the earlier internal discovery/ranking pipeline:
- `curated-events sync`
- `curated-events scheduler`

That path is still testable, but it is no longer the preferred live workflow for this project.
