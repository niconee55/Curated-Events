# Model Guide: Creating `preferences.md`

Use this guide when helping a user create or substantially revise
`docs/preferences.md` and align `docs/research_instructions.md` with it. The goal
is to learn the user's actual taste through conversation, turn it into durable
preferences, and verify those preferences against events found by a real dry
run.

The model should drive the process. Do not ask the user to write the file or
translate their answers into prompt language themselves.

## Desired Outcome

A good `preferences.md` should let a research model answer four questions:

1. What kinds of events would this user genuinely want on their calendar?
2. Which interests should dominate when a month is crowded?
3. What adjacent events are worth discovering beyond the user's named examples?
4. What should be excluded even when it superficially matches a keyword?

The preference file should describe the user's taste, priorities, and inclusion
threshold. Once it is finalized, update `research_instructions.md` so the
research workflow knows how to search for and apply those preferences. Report
syntax belongs in `output_format.md`; credentials and private operational data
belong nowhere in either prompt file.

## Conversation Method

Conduct a short, adaptive interview. Ask one focused question at a time when
possible, respond to what the user actually says, and skip areas they have
already answered.

Start broad:

- What events do you already make an effort to watch, attend, or remember?
- Which teams, artists, leagues, franchises, venues, genres, or cultural areas
  matter most?
- Where can in-person events be located, and how far is the user willing to
  travel?

Then calibrate:

- Which interests are must-adds versus merely nice to know?
- Does the user want only marquee events, or a fuller slate in any category?
- What makes an unfamiliar event interesting: a final, rivalry, release day,
  critical acclaim, low price, date-night value, proximity, or something else?
- Which plausible matches should still be excluded?
- How much calendar density is acceptable in a busy month?
- Should lower-priority discoveries be included in the report for review?

Use concrete comparisons when an answer is vague. For example:

- "Would you want every match in this competition, only knockout rounds, or
  only the final?"
- "Should artists similar to these examples be discovered, or only the named
  artists?"
- "Would a free museum late night be useful even if you do not follow that
  museum?"
- "Is one extra borderline event better than missing something you would
  probably care about?"

Do not force the entire interview before producing value. Once the main
priorities and exclusions are clear, summarize the inferred preference model
briefly and ask the user to correct it. Resolve only the ambiguities that would
materially change results, then write the file.

## How to Interpret Answers

Treat examples as evidence about taste, not automatically as a closed list or a
permanent named rule.

When a user says, "I liked that the agent found the final of a competition I do
not normally follow," infer the broader rule: decisive, high-profile finals can
clear the bar outside core fandoms. Do not merely add that one competition to a
whitelist.

When a user names several artists, infer the shared taste lane and state both:

- the named artists as strong anchors
- the adjacent genres, audience, era, or style that make discovery useful

When a user rejects a result, determine why before encoding it. The cause might
be unfamiliarity, weak relevance, excessive cost, inconvenient location,
generational mismatch, low stakes, or the wrong event type. Do not convert one
rejected name into a broad category ban unless the user's explanation supports
that.

Distinguish these kinds of statements:

- Hard rule: always include or always exclude when the condition is met.
- Strong preference: normally include, but quality and context still matter.
- Discovery lane: search beyond named examples using a coherent similarity
  standard.
- Lower priority: useful for review, but should not displace core interests.
- Temporary instruction: applies to a particular month or tournament and
  should not become a permanent preference without confirmation.

Prefer rules that explain *why* an event belongs. This helps the research model
generalize to events neither the user nor the authoring model already knows.

## Required Coverage

Capture the following when they are relevant. Omit empty sections rather than
inventing preferences.

### Location and Logistics

- Primary city or region
- Preferred neighborhoods or travel radius
- In-person versus watch-at-home or release-day events
- Price sensitivity and any useful accessibility constraints

Do not include a home address, work address, calendar ID, tokens, credentials,
or other sensitive information.

### Priority Interests

- Core categories and explicit ordering
- Favorite teams, artists, competitions, franchises, venues, or genres
- The stages or circumstances that make routine events important
- Any category where the user wants exhaustive rather than selective coverage

### Discovery Preferences

- Adjacent categories the model may explore
- How similarity should be judged
- Whether unfamiliar but high-profile events are welcome
- What makes an event broadly compelling to this user

### Exclusions

- Categories, formats, locations, or price levels that are usually unwanted
- Common false positives such as tribute acts, fan events, routine fixtures, or
  minor announcements
- Exceptions to each broad exclusion when appropriate

### Quality and Density

- The user's threshold for putting something on the calendar
- Whether false positives or missed events are more costly by category
- How core and secondary events compete in a crowded month
- Whether a configured result limit is a strict target, a ceiling, or may be
  exceeded for an explicitly exhaustive category

### Calendar Presentation Preferences

- Whether scheduled events should use the user's local timezone
- Which flexible events should remain all-day
- Whether ticket price matters for attendance events
- Any distinction between high-confidence and lower-priority items

Keep presentation preferences limited to user-facing choices. Parser-specific
formatting remains in `output_format.md`.

## Writing Rules

Write clear, imperative bullets that a separate research model can apply.

- Put the strongest priorities first.
- State category-specific thresholds instead of relying on one vague global
  threshold.
- Preserve meaningful nuance, such as a stricter bar for expensive concerts
  than for free album releases.
- Use named examples as anchors and explain how to generalize from them.
- Include negative preferences and common false positives.
- Avoid duplicate rules phrased several different ways.
- Avoid references such as "like the event we discussed earlier"; the file must
  stand alone in a fresh model session.
- Avoid facts that will quickly become stale, such as current standings,
  one-month schedules, or an upcoming release, unless explicitly marked as a
  temporary override.
- Do not embed research tactics that apply to every user. Keep universal
  sourcing and verification rules in `research_instructions.md`.

## Recommended File Structure

Use this structure as a starting point, adapting it to the user's answers:

```markdown
# Event Search Preferences

Use this file as the single source of truth for this user's event preferences.

## Location and Logistics
- ...

## Core Interests
- ...

## Secondary and Discovery Interests
- ...

## Lower-Priority Preferences
- ...

## Exclusions and False Positives
- ...

## Quality Bar and Calendar Density
- ...

## Calendar Presentation
- ...

## Notes
- Update this file as the user gives feedback on real monthly results.
```

## Update `research_instructions.md`

After the user confirms the preference model and `preferences.md` is finalized,
read the existing `docs/research_instructions.md` and update it to support the
new preferences.

Keep the roles of the files distinct:

- `preferences.md` says what the user likes, dislikes, and prioritizes.
- `research_instructions.md` says how the research agent should search,
  evaluate, verify, and select events using those preferences.

Translate the finalized preferences into operational coverage where necessary.
For example, the research instructions may need category-specific search
passes, primary-source requirements, rules for handling tournament
placeholders, broader discovery methods, or guidance for balancing recall
against precision.

Preserve useful universal research rules and unrelated confirmed behavior.
Remove or revise instructions that conflict with the new preference model.
Avoid copying the entire preference profile into the research file, embedding
one-off event names, or making temporary month-specific facts permanent.

## Dry-Run Fine-Tuning

Creating the files is not complete until they have been tested with actual
research results.

After writing `preferences.md` and updating `research_instructions.md`, choose a
representative future month with the user and run:

```bash
python3 scripts/codex_event_research.py create \
  --month YYYY-MM \
  --report preview_suggestions_dryrun.txt \
  --session-file .codex_event_session_dryrun.json
```

Let the research process finish. Do not sync the dry-run report to Google
Calendar.

Review the resulting events with the user. Ask for feedback on the set as a
whole:

- Which events are clear successes?
- Which events should not have appeared, and why?
- What expected events or event types are missing?
- Is each category too broad, too narrow, or about right?
- Is the total calendar density appropriate?

Use those answers to revise the underlying rules in `preferences.md` and, when
the issue concerns search or selection behavior, in
`research_instructions.md`. Do not merely edit the generated report or add a
list of event-specific exceptions.

Run another dry test when the feedback causes a meaningful rule change. Repeat
until the results reflect the user's intended taste and no important systematic
miss remains. A single run is enough only when the user is satisfied with its
coverage and exclusions.

## Final Review

Before declaring the authoring process complete, check that:

- A new model could rank two plausible events without needing the original
  conversation.
- Named examples can lead to sensible new discoveries rather than functioning
  only as a whitelist.
- Hard requirements are clearly distinguishable from preferences.
- Rejected results led to causal rules, not arbitrary name-based exclusions.
- Temporary campaign or tournament instructions are not accidentally permanent.
- The file contains no secrets or unnecessarily precise personal information.
- Preference rules do not conflict; if they do, the higher priority is explicit.
- Repeated feedback has been consolidated instead of appended as duplicate
  bullets.
- `research_instructions.md` operationalizes the preference model without
  duplicating it or contradicting it.
- At least one real monthly dry run completed using the new files.
- Dry-run feedback was incorporated into the source prompt files rather than
  patched only in the generated report.

Tell the user what preference model was captured, how the research instructions
were changed, which month was tested, and where the dry-run report was written.
Identify any important remaining assumption.

## Updating an Existing File

When revising an established `preferences.md`, preserve confirmed preferences
that the user did not challenge. Integrate new feedback into the smallest
general rule that explains it, remove superseded or contradictory wording, and
avoid continuously appending near-duplicate bullets.

If the user requests a temporary exception, label it clearly and remove it when
its time window ends. If the feedback reveals a lasting taste preference,
rewrite the relevant section so the file remains coherent. Reconcile
`research_instructions.md` after the preference revision and rerun the dry test
when the change could materially affect discovery results.
