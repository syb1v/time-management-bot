# Rich Panel and Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a single-message dashboard, detailed linked Sotka lessons, and multi-period progress statistics.

**Architecture:** Persist dashboard identity per chat and route all renders through one panel service that handles text/photo transitions. Extend normalized Sotka records with API metadata and aggregate local/platform progress in dedicated services.

**Tech Stack:** Python 3.12, aiogram 3, SQLAlchemy 2, SQLite, aiohttp, matplotlib, pytest

**Spec:** `docs/superpowers/specs/2026-09-03-rich-panel-and-progress-design.md`

## Global Constraints

- Keep only the three explicitly selected Sotka courses.
- Never log or persist tokens outside environment configuration.
- Keep one dashboard message per authorized chat.
- Always accompany charts with textual statistics.

---

### Task 1: Sotka metadata and schema upgrade

**Files:** `src/time_manager/models.py`, `src/time_manager/db.py`, `src/time_manager/importers.py`, `src/time_manager/sotka.py`, `src/time_manager/services.py`, `tests/test_sotka.py`

- [ ] Extend normalized events and database columns with lesson metadata and progress.
- [ ] Add idempotent SQLite column upgrades.
- [ ] Test exact filtering, individual lesson links, and planning aggregation.

### Task 2: Persistent dashboard

**Files:** `src/time_manager/panel.py`, `src/time_manager/handlers.py`, `src/time_manager/models.py`, `tests/test_panel.py`

- [ ] Persist dashboard message and media type per chat.
- [ ] Implement edit, replace, recreate, and safe-delete behavior.
- [ ] Route callbacks and FSM prompts through the dashboard.

### Task 3: Rich views and statistics

**Files:** `src/time_manager/render.py`, `src/time_manager/keyboards.py`, `src/time_manager/stats.py`, `src/time_manager/handlers.py`, `tests/test_stats.py`

- [ ] Render detailed Sotka lessons and URL buttons.
- [ ] Add 7/30/183/365-day selectors and combined progress metrics.
- [ ] Verify textual and PNG output for all periods.

### Task 4: Runtime verification

**Files:** `README.md`, existing test suite

- [ ] Document dashboard behavior and detailed progress.
- [ ] Run Ruff, mypy, pytest, live API normalization, and Docker build.
- [ ] Restart the local process and inspect fresh logs.
