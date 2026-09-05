# Study Time Bot Design

## Goal

Build a private Telegram bot that creates a realistic Moscow-time study plan for an 11th-grade student while protecting sleep, school, travel, meals, rest, homework, and Sotka coursework.

## Users and access

- Telegram ID `1359806027` is the student and can manage plans, settings, completion marks, and statistics.
- Telegram ID `6499614618` is the owner and can view plans/statistics and manage global synchronization.
- Every message and callback is rejected before handler execution unless the sender is on the allowlist.

## Architecture

The application uses Python 3.12, aiogram 3, async SQLAlchemy with SQLite/WAL, and APScheduler. A deterministic planner reserves fixed events and wellbeing blocks first, then allocates homework and Sotka recordings into focus blocks. Telegram messages use HTML formatting and inline keyboards.

School lessons are imported from `raspisanie_11g.md`. Sotka content is accessed through an adapter interface. The initial adapter imports `vebinary_sotka_sentyabr_2026.md`; an authenticated HTTP adapter will be added after a sanitized HAR reveals the permitted endpoint contract. API credentials must only be supplied through environment variables.

## Planning rules

Priority is sleep, school/travel, meals, rest, school homework, then Sotka. Default weekday sleep is 21:45-05:45. Departure times for 08:00 and 08:50 starts are configured separately. Travel home is configurable from 30 to 60 minutes.

The student enters one aggregate homework duration per date. Sotka recordings can be split into focus blocks and should be completed before the next event in the same subject. The planner never schedules study after bedtime. Overflow remains visible as debt rather than silently reducing sleep.

## Telegram experience

The home panel exposes Today, Week, Check in, Homework hours, Sotka, Statistics, and Settings. Plan blocks support Done, Partial, Move, and Skip actions. Numeric/time entry uses FSM flows with cancellation. Notifications are sent before blocks and avoid configured quiet hours.

## Statistics

The bot provides 7- and 30-day textual summaries and PNG charts for completion, sleep, planned versus completed homework/Sotka hours, debt, and streaks. Generated charts must be accessible through an accompanying textual summary.

## Reliability and deployment

All persisted timestamps are timezone-aware UTC; local planning uses `Europe/Moscow`. Sotka synchronization is cached and failures retain previous data. Docker Compose runs one polling bot process on a VPS. The SQLite database lives in a mounted data directory and should be backed up as a file while the process is stopped or through SQLite's backup mechanism.

## Verification

Unit tests cover parsing, early/late school starts, Thursday extras, Sotka splitting, overflow, sleep boundaries, roles, and completion state changes. Integration smoke tests initialize the database, generate a plan, render statistics, and construct the aiogram dispatcher without contacting Telegram.
