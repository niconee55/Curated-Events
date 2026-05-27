# Codex Research Output Format

Write the final report as markdown.

## Required Sections
1. High-confidence events
2. Lower-priority but useful events
3. Search gaps or intentionally empty categories
4. Sources

## High-Confidence Events
Include only events that are strong matches.

The configured `limit` is a maximum, not a target to undershoot. If many items clearly clear the confidence bar, include them up to the limit.
For soccer-heavy months, interpret `strong matches` broadly enough to keep the meaningful slate rather than only the absolute top handful.

If semifinal or final slots are already important and calendared in the requested month, they may be included as real watch events even before the exact teams are fully known.
For the monthly seed run, official late-stage tournament date slots that are already known should usually appear in `High-confidence events` when they are clearly strong fits, even if exact pairings are not yet known.

For each event include:
- Title
- One-sentence description
- Exact date
- Exact time when it is known and meaningful
- Location
- Price if attendance or tickets are required and price information is available
- Why it matches the preferences
- Direct source link

## Title Rules
- For known specific sports matchups, use the plain match title, for example `Real Madrid vs Bayern Munich` or `Sporting CP vs Arsenal`.
- Do not prepend competition or stage to the title when the exact matchup is already known and the match title itself is clean and recognizable.
- Titles like `Champions League quarter-final first leg: Real Madrid vs Bayern Munich` are not acceptable when the exact teams are already known.
- If you are surfacing only the opening, closing, or other boundary marker from a longer festival or exhibition run, make that explicit in the title.
- Include short date markers in those boundary titles when useful, for example `Opening Night (Apr 8)` or `Closing Weekend (Apr 19)`.
- Do not include both a broad multi-week umbrella event and separate opening/closing entries for the same thing in the same report.
- For bracket-dependent sports slots, put the competition and stage in the title first, and keep the team-dependency details in the description.
- Good examples:
  - `Champions League semifinal first leg`
  - `New Directors/New Films 2026 Opening Night (Apr 8)`
  - `New Directors/New Films 2026 Closing Weekend (Apr 19)`

## Lower-Priority But Useful Events
Use this for nice-to-know items such as notable Manhattan culture, film, or jazz that fit the taste profile but are not at the same importance level as top soccer matches.

Do not use this section for obvious high-fit items that should have been in the high-confidence section.
Do not use this section for women's club soccer unless it is truly global-marquee and explicitly relevant.
Do not demote clearly meaningful Champions League, major-tournament, or EPL matches into this section just because the high-confidence list is getting long.

For each event include:
- Title
- One-sentence description
- Exact date
- Exact time when it is known and meaningful
- Location
- Price if attendance or tickets are required and price information is available
- Why it is lower priority
- Direct source link

## Time Formatting
- If an event has a real scheduled time, include `Exact time: ...`
- For soccer matches, concerts, jazz, museum after-hours, screenings, and other scheduled events, convert the scheduled start time into New York time before writing it.
- For releases or flexible experiences that do not have a meaningful appointment time, omit `Exact time` and let them be treated as all-day.
- Do not omit `Exact time` for scheduled soccer or attendance events when a source provides it.
- Use one canonical time expression only, in ET / New York time.
- Do not output venue-local-only time strings such as `9:00 PM local kickoff`.
- Do not output dual-time strings such as `11:30 AM ET / 4:30 PM BST`.
- If any `Exact time` line still uses venue-local wording or dual-time formatting, the report is not valid yet.
- Good examples:
  - `Exact time: 3:00 PM ET`
  - `Exact time: 7:30 PM`

## Description Quality
- Descriptions should carry useful context, not just generic praise.
- For soccer, mention the stakes when you know them: title race, top-four implications, Champions League qualification, Europa League qualification, relegation pressure, semifinal berth, derby significance, or what a win would likely mean.
- When standings or points context is available from a trustworthy source, include the concrete context rather than vague language. Good examples:
  - `Arsenal enter the match two points behind City, so a win would swing the title race while a loss would hand City clear control.`
  - `Chelsea and Newcastle are separated by one Champions League place, so this result could directly change the top-five picture.`
- For culture items, mention the relevant practical hook: opening night, closing weekend, free admission, after-hours format, special guests, or notable programming.
- If the item is a placeholder for an upcoming tournament stage, the description should explain that the date is official now and the later update workflow should replace it with exact teams once confirmed.

## Price Formatting
- Keep price lines short and scannable.
- Use the format `Price: ...`
- Good examples:
  - `Price: Free with museum admission`
  - `Price: From $150 plus fees`
  - `Price: $9.99 digital album`
  - `Price: Not listed on the cited source`

## Search Gaps
- It is acceptable for some categories to have no strong events in a given month.
- If a category is empty, say that clearly and move on.
- Do not list official late-stage tournament placeholders here if their dates are already known and they are important enough to belong in the main event list.

## Source Section
- Group sources by domain or category when practical.
- Keep source links direct and readable.

## Optional Handoff Notes
- After the `Sources` section, you may add a short `# Handoff notes for future update runs` section.
- Use it only for concise operational notes that would help a later update workflow improve the month.
- Good handoff notes include:
  - unresolved semifinal or final pairings to revisit
  - standings-sensitive matches whose context should be refreshed closer to kickoff
  - recurring culture items that may need more precise dated entries later
