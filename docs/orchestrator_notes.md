# Orchestrator Notes

This file is for the orchestration layer that manages the research workflow. It is not the user preference file and it is not the output-format spec for the downstream Codex research agent.

## Current Workflow
- The preferred discovery path is the Codex-backed live web research flow, not the old Ticketmaster-heavy pipeline.
- The seed entrypoint is `python3 scripts/codex_event_research.py create --month YYYY-MM --report preview_suggestions.txt --session-file .codex_event_session_seed.json`.
- The update entrypoint is `python3 scripts/codex_event_update.py create --month YYYY-MM --report preview_suggestions.txt --session-file .codex_event_update_session.json`.
- Reports are typically written to `preview_suggestions.txt` for review runs.
- The usual live flow is:
  - generate `preview_suggestions.txt`
  - review it
  - apply it with `python3 -m curated_events.cli report apply ...`
  - rollback and reapply later after an update run
- The orchestrator should treat the markdown prompt files as the source of truth for agent behavior:
  - `docs/preferences.md`
  - `docs/research_instructions.md`
  - `docs/update_instructions.md`
  - `docs/output_format.md`
  - `docs/handoff_instructions.md`

## Current Steering Priorities
- Soccer is the top priority by a wide margin.
- The seed workflow should still be broader than the update workflow. It should surface the monthly slate of important things happening, even when some items are only adjacent interests or still need richer context.
- For late-stage Champions League, World Cup, Euros, and similar tournaments, include essentially all strong matches in the window, not just one representative reminder.
- Real Madrid, PSG in major Champions League spots, and top-tier international tournament games should dominate the high-confidence section.
- Routine domestic league matches should not dominate just because they involve Real Madrid or PSG.
- Domestic matches need stronger context: major opponent, title-race significance, or other unusually important stakes.
- The Premier League is the main domestic-league exception. Big EPL matches, title-race games, top-four battles, and relegation fights should be surfaced much more aggressively.
- The Premier League should be allowed to fill more of the calendar than before. Include more meaningful EPL fixtures when they have real stakes, derby value, or major-club significance.
- Adjacent sports the user could plausibly get into, such as March Madness or other major tournament games, are now in scope for the seed workflow when the stakes are broadly compelling.
- Women's club soccer should normally be excluded unless it is an exceptionally high-signal global marquee tournament context.
- Manhattan culture, jazz, and film are useful but secondary.
- Anime should usually mean major new season releases, major film releases, or major franchise announcements, not local screenings.
- Museum items should lean toward public-facing, easy-to-attend, date-night-friendly, after-hours, or free-night style events instead of overly niche talks or private programming.
- Major artist releases can count if they are a real fit.
- Music-release search should be broader than the exact named artists: use them as anchors for style and taste, not as a hard whitelist.
- Expensive NYC concerts should have a stricter fit bar than digital album releases or watch events.
- A high-quality one-off jazz or gala event can still belong on the calendar if it is genuinely compelling; the issue is bulk and weak fit, not the category itself.
- Current taste examples explicitly captured from user feedback:
  - Noah Kahan
  - Bruno Mars
  - Daniel Caesar
  - Billie Eilish
  - Gracie Abrams
  - Kacey Musgraves
  - Maggie Rogers
- Major Nintendo-related releases or media events at the level of a meaningful movie/game release are in scope.
- Release picks should stay broad and meaningful, not overly niche.
- Major official album releases from the stated artist taste set should beat weak museum filler.

## Output Expectations To Enforce
- Every surfaced item should have a one-sentence description.
- If an event requires attendance or tickets, include price information when available.
- Price formatting should be concise and use `Price: ...`
- Scheduled events should be reported in ET / New York time only.
- It is acceptable to return fewer than the cap if there are not enough strong matches.
- The configured limit is a ceiling. In dense months, the agent should fill toward it rather than self-censor to a tiny list.
- If the run still looks too sparse, bias toward including more plausible strong matches rather than raising the bar further.
- Search gaps are acceptable; do not pad weak categories just to hit the limit.

## Operational Lessons
- The first open-ended research prompt wandered and did not terminate quickly enough.
- The current bounded monthly prompt is better, but the downstream Codex session still tends to keep polishing sources after the report is already usable.
- The research wrapper now validates report time formatting and should reject venue-local or dual-time `Exact time` lines.
- If the seed run feels too constrained, the right move is usually to broaden the seed prompt rather than demanding update-level detail too early. The update workflow exists specifically to sharpen context later.
- The update workflow should export the current Google Calendar month state and feed it into the prompt before searching, so the agent can replace placeholders instead of guessing what is already on-calendar.
- In practice, once `preview_suggestions.txt` has been written and looks coherent, the orchestrator may need to stop the session manually rather than wait for perfect cleanup.
- If future runs still drift, tighten the research instructions before loosening quality standards.
