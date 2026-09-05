# Study Time Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a private aiogram bot that generates, tracks, and visualizes a healthy school and Sotka study schedule.

**Architecture:** A deterministic domain planner consumes normalized school/Sotka events and user settings, then persists daily blocks in async SQLite. Aiogram handlers render one navigable panel, FSM dialogs collect values, APScheduler sends reminders, and a chart service renders aggregate history.

**Tech Stack:** Python 3.12, aiogram 3, SQLAlchemy 2, aiosqlite, APScheduler, matplotlib, pytest, Ruff, mypy, Docker Compose

**Spec:** `docs/superpowers/specs/2026-09-03-study-time-bot-design.md`

## Global Constraints

- Use `Europe/Moscow` for user-facing dates and timezone-aware UTC in storage.
- Permit only Telegram IDs `1359806027` and `6499614618`.
- Preserve sleep before allocating optional study.
- Do not read browser cookies or persist API credentials in source control.
- Use Telegram HTML formatting and escape all dynamic values.

---

### Task 1: Application foundation and persistence

**Files:** `pyproject.toml`, `.env.example`, `src/time_manager/config.py`, `src/time_manager/db.py`, `src/time_manager/models.py`, `tests/test_db.py`

**Interfaces:** Produces `Settings`, `Database`, SQLAlchemy models, and database initialization used by all later tasks.

- [ ] Add dependency/tool configuration and environment validation.
- [ ] Write a failing database initialization/default-settings test.
- [ ] Implement async SQLite models and WAL initialization.
- [ ] Run `pytest tests/test_db.py -v` and make it pass.

### Task 2: Schedule importers

**Files:** `src/time_manager/importers.py`, `tests/test_importers.py`

**Interfaces:** Produces `parse_school_schedule(text)` and `parse_sotka_schedule(text, year)` returning normalized event values.

- [ ] Write parsing tests against representative markdown rows.
- [ ] Implement strict parsers with clear validation errors.
- [ ] Run `pytest tests/test_importers.py -v` and make it pass.

### Task 3: Deterministic planning service

**Files:** `src/time_manager/planner.py`, `src/time_manager/services.py`, `tests/test_planner.py`

**Interfaces:** Produces `build_day_plan(...)`, plan regeneration, homework input, and completion transitions.

- [ ] Write tests for 08:00/08:50 starts, Thursday extras, sleep boundary, splitting, and overflow.
- [ ] Implement interval reservation and focus-block allocation.
- [ ] Implement persistence orchestration and completion transitions.
- [ ] Run `pytest tests/test_planner.py -v` and make it pass.

### Task 4: Telegram interface and authorization

**Files:** `src/time_manager/bot.py`, `src/time_manager/handlers.py`, `src/time_manager/keyboards.py`, `src/time_manager/render.py`, `tests/test_bot.py`

**Interfaces:** Produces `create_dispatcher(container)` and callback/FSM flows for panels, homework, actions, and settings.

- [ ] Write authorization, rendering, and callback-data tests.
- [ ] Implement allowlist middleware and role checks.
- [ ] Implement home/day/week/Sotka/settings panels and FSM value entry.
- [ ] Implement Done/Partial/Move/Skip callbacks and panel refresh.
- [ ] Run `pytest tests/test_bot.py -v` and make it pass.

### Task 5: Notifications and statistics

**Files:** `src/time_manager/jobs.py`, `src/time_manager/stats.py`, `tests/test_stats.py`

**Interfaces:** Produces reminder polling and `build_stats`/`render_chart` for 7/30 day ranges.

- [ ] Write aggregation and PNG smoke tests.
- [ ] Implement textual statistics and charts.
- [ ] Implement idempotent due-reminder delivery respecting quiet hours.
- [ ] Run `pytest tests/test_stats.py -v` and make it pass.

### Task 6: Runtime and deployment

**Files:** `src/time_manager/main.py`, `Dockerfile`, `docker-compose.yml`, `README.md`, `.gitignore`

**Interfaces:** Produces the executable `python -m time_manager.main` and documented VPS deployment.

- [ ] Wire startup, import, plan generation, polling, and graceful shutdown.
- [ ] Add non-root Docker image and persistent SQLite volume.
- [ ] Document bot creation, environment setup, HAR sanitization, deployment, backup, and operation.
- [ ] Run `ruff check .`, `mypy src`, `pytest -q`, and `docker compose config`.
