# Curated Events

Created by Nicolas Nee

Personalized event discovery and Google Calendar sync pipeline tailored to the provided interest profile (soccer-first, selected gaming/anime, Manhattan culture, and marquee sports moments). The current live workflow generates reviewed monthly reports, imports them into a local database, and syncs a dedicated Google Calendar named **Curated Events**.

## Quickstart
1. Create and activate a Python 3.11+ environment.
2. Install dependencies:
   ```bash
   pip install -e .[dev]
   ```
3. Copy `.env.example` to `.env` and fill values.
4. Authorize Google Calendar access:
   ```bash
   curated-events google-auth
   ```
5. Initialize the database:
   ```bash
   curated-events db init
   ```

## Recommended Calendar Workflow
The current production workflow is report-driven:
1. run the seed research agent
2. review the generated report
3. apply that report to the dedicated `Curated Events` Google Calendar
4. later run the update agent to refine placeholders, standings context, and late-breaking items

### 1. Generate the monthly seed report
```bash
python3 scripts/codex_event_research.py create --month 2026-04 --report preview_suggestions.txt --session-file .codex_event_session_seed.json
```

This uses live web search and writes the autonomous monthly report to:
- `preview_suggestions.txt`

Prompt inputs:
- [docs/preferences.md](docs/preferences.md)
- [docs/research_instructions.md](docs/research_instructions.md)
- [docs/output_format.md](docs/output_format.md)
- [docs/handoff_instructions.md](docs/handoff_instructions.md)

### 2. Review the report
Open:
- `preview_suggestions.txt`

This file is the review artifact that gets pushed to Google Calendar.

### 3. Apply the reviewed report to Google Calendar
To push both high-confidence and lower-priority items:
```bash
python3 -m curated_events.cli report apply --report preview_suggestions.txt --snapshot agent_reports/report_apply_snapshot.json --include-lower-priority
```

This writes only to the configured Google Calendar ID, not your other calendars.

Artifacts:
- report: `preview_suggestions.txt`
- rollback snapshot: `agent_reports/report_apply_snapshot.json`

### 4. Roll back the last applied calendar version
If you want to remove the currently applied report from Google Calendar:
```bash
python3 -m curated_events.cli report rollback --snapshot agent_reports/report_apply_snapshot.json
```

Typical replacement flow:
```bash
python3 -m curated_events.cli report rollback --snapshot agent_reports/report_apply_snapshot.json
python3 scripts/codex_event_research.py create --month 2026-04 --report preview_suggestions.txt --session-file .codex_event_session_seed.json
python3 -m curated_events.cli report apply --report preview_suggestions.txt --snapshot agent_reports/report_apply_snapshot.json --include-lower-priority
```

## Suggestion Preview
To review ranked suggestions without writing to Google Calendar, run:
```bash
python3 scripts/preview_suggestions.py --output preview_suggestions.txt
```

This runs discovery only, stores results in the configured database, and writes a plain text summary you can review before syncing.

## Codex Seed Workflow
To seed a month with live web search through Codex:
```bash
python3 scripts/codex_event_research.py create --month 2026-04 --report preview_suggestions.txt --session-file .codex_event_session_seed.json
```

To continue the same session later:
```bash
python3 scripts/codex_event_research.py resume --month 2026-04 --report preview_suggestions.txt --session-file .codex_event_session_seed.json
```

Session metadata is stored in the session file you pass, for example:
- `.codex_event_session_seed.json`

## Codex Update Workflow
To revisit a month later, using the current Google Calendar contents as context:
```bash
python3 scripts/codex_event_update.py create --month 2026-04 --report preview_suggestions.txt --session-file .codex_event_update_session.json
```

This update workflow:
- exports the current month from the configured Google Calendar into `agent_reports/calendar_context_latest.md`
- reads [docs/preferences.md](docs/preferences.md)
- reads [docs/update_instructions.md](docs/update_instructions.md)
- reads [docs/output_format.md](docs/output_format.md)
- reads [docs/handoff_instructions.md](docs/handoff_instructions.md)
- writes a refreshed full-month report back to `preview_suggestions.txt` by default

To continue the same update session later:
```bash
python3 scripts/codex_event_update.py resume --month 2026-04 --report preview_suggestions.txt --session-file .codex_event_update_session.json
```

Session metadata for the updater is stored in the session file you pass, for example:
- `.codex_event_update_session.json`

Typical monthly flow:
1. Start of month:
   ```bash
   python3 scripts/codex_event_research.py create --month 2026-04 --report preview_suggestions.txt --session-file .codex_event_session_seed.json
   python3 -m curated_events.cli report apply --report preview_suggestions.txt --snapshot agent_reports/report_apply_snapshot.json --include-lower-priority
   ```
2. Mid-month refresh:
   ```bash
   python3 -m curated_events.cli report rollback --snapshot agent_reports/report_apply_snapshot.json
   python3 scripts/codex_event_update.py create --month 2026-04 --report preview_suggestions.txt --session-file .codex_event_update_session.json
   python3 -m curated_events.cli report apply --report preview_suggestions.txt --snapshot agent_reports/report_apply_snapshot.json --include-lower-priority
   ```

## Legacy Built-in Pipeline
The older internal discovery pipeline still exists:
```bash
curated-events sync
curated-events scheduler
```

But the preferred workflow for live use is the Codex seed/update report flow above.

## Development
- Tests: `pytest`
- Linting is not configured; rely on type hints and tests.
- External calls (APIs/Google) are wrapped so they can be stubbed or no-op when credentials are absent.

See [docs/design.md](docs/design.md) for product summary, architecture, data model, sources, ranking, and defaults.
