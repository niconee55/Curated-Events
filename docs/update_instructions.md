# Codex Calendar Update Instructions

Use live web search plus the provided current-calendar context to refresh the month.

## Goal
- Treat the existing calendar as the baseline state for the requested month.
- Improve it by updating placeholders, refreshing stale context, and adding clearly missing events.
- Produce a full replacement monthly report, not just a diff, so the orchestrator can rollback and reapply safely.
- Assume the seed workflow was intentionally broader and may have included plausible adjacent-sport or lighter-context items that now need to be sharpened rather than discarded reflexively.

## Update Priorities
- Replace bracket or placeholder soccer entries with the real matchup as soon as the official pairing and date are known.
- Refresh soccer descriptions with more immediate stakes when reliable sources support it, including standings, points gaps, qualification pressure, relegation pressure, or knockout consequences.
- Keep all major late-stage tournament games in scope even if some of them were only placeholders in the seed run.
- Add newly relevant EPL matches if the table picture has become clearer and the match now meaningfully affects the title race, European places, or relegation battle.
- For adjacent sports that were surfaced in the seed run, add the richer context that makes them more useful: tournament round, bracket implications, rivalry context, likely stakes, and whether they still clear the bar.
- Do not over-prune adjacent soccer semifinals, finals, or other trophy-deciding events if they still have clear watch value in the month.
- Add any major official releases or Manhattan culture items that became newly relevant since the seed run.
- Re-run a broader music-release check for the target month so newly announced or previously missed official album releases from strong-fit or adjacent artists can be added.

## Comparison Rules
- Compare the current calendar context against the best current web information.
- Keep good existing entries that are still correct.
- Upgrade titles when a formerly uncertain event now has a known matchup.
- Remove broad umbrella entries when more precise opening, closing, or recurring entries are the better calendar representation.
- Do not duplicate an existing event unless the old entry is being intentionally replaced with a better one.

## Context Rules
- For soccer, prefer sharper context than the seed run when possible.
- If a match is now close enough that standings are concrete, say why the result matters using real table context rather than generic hype.
- For placeholder tournament games that are still unresolved, keep them in the main list when the official date window is still important.
- For releases or flexible items, keep them all-day rather than inventing times.
- For music, do not limit the refresh to artists already present in the current calendar context; use the broader taste lane and official release sources to catch omitted albums.

## Completion Rule
- Once the refreshed month is coherent and clearly stronger than the current calendar baseline, stop.
- Do not keep searching indefinitely after the replacement report is good enough to apply.
