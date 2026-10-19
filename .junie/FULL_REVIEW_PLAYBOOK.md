# Full Documentation and Agent Review Playbook

This playbook documents the scope of work performed during project auditing, architecture analysis, guidelines configuration, and documentation overhaul for the **Time Clock** application. It also establishes the standard operating procedure (SOP) and review checklist to execute whenever a **"full documentation and agent review"** is requested.

---

## 1. Overview & Purpose

A **Full Documentation and Agent Review** is a holistic, end-to-end audit of the `Time Clock` project. Its purpose is to ensure:
1. **Codebase-Documentation Synchronization:** All architectural documentation, user guides, data contracts, and configuration workflows accurately reflect the Python source code.
2. **Agent Knowledge Alignment:** `.junie/AGENTS.md` contains up-to-date architectural specifications, database schemas, event definitions, headless testing practices, and domain rules.
3. **Core Subsystem & Domain Integrity:** Domain dataclasses (`models.py`), SQLite persistence (`storage.py`), publish-subscribe event dispatching (`events.py`), core business logic coordinator (`engine.py`), and CSV/JSON export routines (`export.py`) are fully synchronized.
4. **GUI & Dialog Consistency:** CustomTkinter and Tkinter/ttk desktop views (`app.py`, `clock_panel.py`, `task_panel.py`, `history_panel.py`, `earnings_panel.py`) and modal dialogs (`add_earnings_dialog.py`, `earnings_goal_dialog.py`, `edit_session_dialog.py`, `stats_calendar_dialog.py`, `task_options_dialog.py`, `prompt_dialog.py`) match documented workflows and theme conventions.
5. **Build & Test Verification:** 100% of test suites pass cleanly across all unit and headless GUI test modules (`python3 -m unittest discover tests`).

---

## 2. Summary of Work Performed (What Was Done Here)

During the foundational project audit and documentation review, the following core initiatives were executed:

### Phase 1: Comprehensive Codebase & Architecture Walkthrough
- **Analyzed Domain Layer (`time_clock/models.py`):** Audited domain models (`TimeEntry`, `Task`, `AppState`, `EarningEntry`, `MonthlyGoal`, `EarningsPeriodStats`), dictionary serialization/deserialization methods (`to_dict` / `from_dict`), and time formatting/parsing utilities (`format_duration`, `iso_now`, `parse_iso`).
- **Audited Configuration Management (`time_clock/config.py`):** Inspected runtime config loader (`AppConfig`), resolution of default database path (`~/Library/Application Support/TimeClock/time_clock.db`), fallback handling for invalid/corrupted config files, and environment variable overrides (`TIME_CLOCK_CONFIG`, `TIME_CLOCK_DB`).
- **Audited Persistence Layer (`time_clock/storage.py`):** Verified SQLite schema creation (`tasks`, `time_entries`, `app_state`, `earnings`, `monthly_goals`), atomic transaction handling, foreign key cascade/reassignment routines (`reassign_task_data`), and legacy JSON migration logic.
- **Audited In-Process Event Bus (`time_clock/events.py`):** Reviewed synchronous publish-subscribe `EventBus` implementation, event normalization, and all `EventType` enumerations governing reactive UI updates without interval polling.
- **Audited Business Logic Engine (`time_clock/engine.py`):** Inspected `TimeClockEngine` coordination logic: clock in/out, task CRUD, task consolidation (`consolidate_tasks_by_name`), running session adjustments, duration calculations, earnings ledger tracking, monthly goal pace calculations (including 28-day 4-week horizon), daily needed rate formulas, and reporting cutoff management.
- **Audited Data Export Layer (`time_clock/export.py`):** Verified CSV and formatted JSON export utilities for single-task histories and complete application state.
- **Audited User Interface & Design System (`time_clock/gui/`):** Evaluated CustomTkinter views, dialogs, theme definitions (`theme.py`), menu bar actions (`File`, `View`, `Advanced`), keyboard bindings, and modal lifecycle behaviors.
- **Audited Packaging & Automation Scripts (`scripts/`):** Reviewed standalone installer (`install_macos.sh`), application updater (`update_macos.sh`), and the pure-Python icon generator (`generate_icon.py`).

### Phase 2: Agent Guidelines Harmonization (`.junie/AGENTS.md`)
- Documented project architecture, module breakdown, configuration paths, and default database locations.
- Standardized environment setup instructions, prerequisites (Python 3.8+, `customtkinter>=5.2.0`), and launch commands.
- Established strict testing guidelines: temporary directories for disk persistence tests (`tempfile.mkdtemp()`), headless `tk.Tk()` root handling (`root.withdraw()`), and silent dialog mocking.
- Documented core domain contracts: ISO-8601 UTC timestamp standard, event bus publication requirements, and unpaid tasks (`Task.is_unpaid = True`) handling.

### Phase 3: User Documentation Maintenance (`README.md`)
- Enforced strict separation between user-facing documentation (`README.md`) and internal developer guidelines (`.junie/AGENTS.md`).
- Documented all user features: task management, paid vs. unpaid tasks, 3-click header sorting, unified edit dialog, earnings tracking & pacing markers, historical calendar statistics, reporting cutoffs, and data export.

### Phase 4: Verification & Quality Assurance
- Executed full test suite (`python3 -m unittest discover tests`) across all test modules (`test_models`, `test_config`, `test_sqlite_storage`, `test_events`, `test_engine`, `test_export`, `test_earnings`, `test_gui`, `test_theme`, `test_integration`), achieving 100% pass rate.

---

## 3. Standard Operating Procedure (SOP) for Full Reviews

When instructed to **"do a full documentation and agent review"** (or similar requests), execute the following 7-step procedure:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│             Full Documentation and Agent Review Workflow                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
   Step 1: Codebase & Dependency Audit (Inspect dependencies, models, engine)
                                      │
                                      ▼
   Step 2: Core Domain, Storage & Event Bus Check (Verify models, SQLite, bus)
                                      │
                                      ▼
   Step 3: GUI & CustomTkinter Architecture Check (Verify panels, dialogs)
                                      │
                                      ▼
   Step 4: Agent Guidelines Alignment (Sync .junie/AGENTS.md with codebase)
                                      │
                                      ▼
   Step 5: User Documentation Synchronization (Sync README.md with features)
                                      │
                                      ▼
   Step 6: Automated Test Suite Verification (Run python3 -m unittest discover)
                                      │
                                      ▼
   Step 7: Structured Summary & Reporting (Output clear audit findings)
```

### Step 1: Codebase & Dependency Audit
1. Inspect `requirements.txt` for added, updated, or removed dependencies.
2. Review project entry point (`main.py`) and top-level imports.
3. Check `scripts/` (`install_macos.sh`, `update_macos.sh`, `generate_icon.py`) for changes in packaging or deployment paths.

### Step 2: Core Domain, Storage & Event Bus Check
1. Inspect `time_clock/models.py` for changes to domain dataclasses, serialization methods, or formatting utilities.
2. Inspect `time_clock/config.py` for new configuration parameters or environment variables.
3. Inspect `time_clock/storage.py` for SQLite schema migrations, new table definitions, or query updates.
4. Inspect `time_clock/events.py` for newly added `EventType` enum members and event payloads.
5. Inspect `time_clock/engine.py` for business logic changes, new coordination methods, or event emission requirements.
6. Inspect `time_clock/export.py` for CSV/JSON export schema alterations.

### Step 3: GUI & CustomTkinter Architecture Check
1. Check `time_clock/gui/app.py` for new view modes, menu bar items, or top-level shortcuts.
2. Inspect panels (`clock_panel.py`, `task_panel.py`, `history_panel.py`, `earnings_panel.py`) for reactive event bindings and UI layout updates.
3. Inspect dialogs (`task_options_dialog.py`, `edit_session_dialog.py`, `add_earnings_dialog.py`, `earnings_goal_dialog.py`, `stats_calendar_dialog.py`, `prompt_dialog.py`) for input validation and modal lifecycles.
4. Check `time_clock/gui/theme.py` for theme tokens, color palette updates, and font definitions.

### Step 4: Agent Guidelines Alignment (`.junie/AGENTS.md`)
1. Update module listings, component responsibilities, and architecture overviews in `.junie/AGENTS.md`.
2. Ensure database schema documentation, event contracts, and domain rules match current code.
3. Keep test writing instructions, mock conventions, and headless test requirements up to date.

### Step 5: User Documentation Synchronization (`README.md`)
1. Ensure `README.md` covers all user-accessible features, UI panels, dialogs, menu actions, sorting workflows, and export formats.
2. Verify that `README.md` maintains a strictly user-facing perspective without leaking backend class names or internal implementation details.

### Step 6: Automated Test Suite Verification
1. Run the entire test suite across all modules:
   ```bash
   python3 -m unittest discover tests
   ```
2. Verify that all tests pass without errors or regressions.
3. Ensure GUI tests run headlessly and silently without popping up windows or stealing OS focus.

### Step 7: Structured Summary & Reporting
Produce a structured summary report detailing:
- Key architectural findings and identified discrepancies.
- Documentation and guideline updates made.
- Test execution and verification results.

---

## 4. Trigger Phrases & Usage

You can trigger this full review process at any time by issuing prompts such as:
- *"Do a full documentation and agent review"*
- *"Please perform a full doc and agent audit"*
- *"Review all documentation, agent guidelines, and architecture against the latest code"*
- *"Run a full documentation review focusing on [specific component, e.g., earnings panel, SQLite storage, or task options dialog]"*

---

## 5. Review Checklist

Use this checklist during every full review:

- [ ] **Dependencies & Setup:** `requirements.txt` matches imported packages (`customtkinter>=5.2.0`).
- [ ] **Domain Models & Serialization:** `time_clock/models.py` dataclasses, `to_dict()`, `from_dict()`, and duration helpers are documented.
- [ ] **Configuration & Environment:** `AppConfig` paths (`~/.config/time_clock/config.json`) and environment variable overrides (`TIME_CLOCK_CONFIG`, `TIME_CLOCK_DB`) match code and docs.
- [ ] **SQLite Persistence:** `time_clock/storage.py` schemas (`tasks`, `time_entries`, `app_state`, `earnings`, `monthly_goals`), migrations, and reassignments are documented.
- [ ] **Event Bus & Event Types:** `EventType` enums and event payloads in `time_clock/events.py` match subscribers in `time_clock/gui/`.
- [ ] **Engine Business Logic:** `TimeClockEngine` methods (timers, task CRUD, consolidation, earnings, pacing markers, daily needed calculations) are documented.
- [ ] **Export Functionality:** `time_clock/export.py` CSV fields and JSON structures match documentation.
- [ ] **GUI Panels & Dialogs:** All panels and dialogs in `time_clock/gui/` reflect documented features and menu bar items.
- [ ] **Packaging & Scripts:** `install_macos.sh`, `update_macos.sh`, and `generate_icon.py` operate on correct paths and bundle IDs.
- [ ] **Agent Guidelines (`.junie/AGENTS.md`):** Contains up-to-date developer instructions, testing rules, and architectural contracts.
- [ ] **User Guide (`README.md`):** Purely user-facing, accurate, and synchronized with all GUI features.
- [ ] **Test Suite Execution:** All tests in `tests/` pass with zero failures and zero errors (`python3 -m unittest discover tests`).
