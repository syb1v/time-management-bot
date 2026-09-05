# Rich Panel and Progress Design

## Goal

Replace the accumulating Telegram conversation with one persistent dashboard and turn Sotka data into actionable links and measurable progress.

## Dashboard lifecycle

Each authorized chat has one stored dashboard message. Navigation edits the dashboard when its media type permits it. Switching between text and chart deletes the previous dashboard and creates one replacement. Missing or manually deleted dashboards are recreated. User input messages and transient prompts are deleted where Telegram permissions permit it.

## Sotka details

Only the exact courses for Russian with Dasha, social studies with Alexey, and profile mathematics with Alexander are accepted. Every API lesson stores its course ID, lesson ID, start time, duration, platform completion flags, and canonical URL. Same-day mathematics blocks remain individually linked but are aggregated for planning workload.

## Progress and statistics

The Sotka view presents date/time in Moscow, teacher/course, duration, viewing status, homework status, deadline, and direct lesson buttons. Combined progress includes platform viewing/homework flags and local planned-block completion. Statistics support 7, 30, 183, and 365 days with textual accessibility summaries and a chart.

## Reliability

Schema upgrades run idempotently on existing SQLite databases. API failures preserve cached metadata and plans. Telegram delete/edit failures caused by already deleted or unchanged messages do not break callback handling.
