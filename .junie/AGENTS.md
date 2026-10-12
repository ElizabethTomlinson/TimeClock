# Developer & Agent Guidelines for Time Clock

This document contains project-specific information, setup instructions, testing guidelines, and architectural details to assist development on the **Time Clock** application.

---

## 1. Project Overview & Architecture

**Time Clock** is a modular Python desktop time tracking application with zero external runtime dependencies. It uses a decoupled, event-driven architecture structured as follows:

- **`time_clock/models.py`**: Domain dataclasses (`TimeEntry`, `Task`, `AppState`, `EarningEntry`, `MonthlyGoal`, `EarningsPeriodStats`) with explicit dictionary serialization/deserialization methods (`to_dict` / `from_dict`) and duration/ISO-8601 formatting utilities (`format_duration`, `iso_now`, `parse_iso`).
- **`time_clock/config.py`**: `AppConfig` runtime configuration manager loading settings from `~/.config/time_clock/config.json` (or `TIME_CLOCK_CONFIG` / `TIME_CLOCK_DB` environment variables) with default database path pointing to `~/Library/Application Support/TimeClock/time_clock.db` and automatic directory/file generation.
- **`time_clock/storage.py`**: `SQLiteStorage` (and base `Storage`) persisting domain state to SQLite database (default: resolved from `AppConfig.db_path`) with automatic table creation (`tasks`, `time_entries`, `app_state`, `earnings`, `monthly_goals`) and legacy JSON migration handling.
- **`time_clock/events.py`**: In-process synchronous publish-subscribe `EventBus` using the `EventType` enum (`TASK_*`, `CLOCK_IN`, `CLOCK_OUT`, `TICK`, `ENTRY_UPDATED`, `EARNING_ADDED`, `EARNING_DELETED`, `GOAL_UPDATED`, `STATE_LOADED`, `STATE_SAVED`) for decoupling the business logic from GUI components.
- **`time_clock/engine.py`**: `TimeClockEngine` coordinator implementing business rules (clocking in/out, task CRUD, updating active/completed session timestamps, duration calculations, active timer tracking, earnings tracking, monthly goal configuration, and daily needed calculations) and emitting lifecycle events.
- **`time_clock/gui/`**: Tkinter/ttk desktop interface divided into modular panels:
  - `app.py`: `TimeClockApp` main window and container with top header view switcher, `File`, `View`, and `Advanced` menu bars, and window/dock icon configuration.
  - `add_earnings_dialog.py`: `AddEarningsDialog` modal for logging task-associated earnings with customizable date entry defaulting to today.
  - `earnings_goal_dialog.py`: `EarningsGoalDialog` modal for setting monthly earnings target and toggling the 4-week (28-day) month mode.
  - `earnings_panel.py`: `EarningsPanel` view displaying monthly goal statistics, needed daily rate, milestone progress bars, and recent earnings ledger.
  - `edit_session_dialog.py`: `EditClockInOutDialog` modal for editing active session start times and modifying/adding historical sessions.
  - `prompt_dialog.py`: Centered single-value prompt input dialog.
  - `stats_calendar_dialog.py`: `StatsCalendarDialog` modal for viewing historical time statistics (daily, weekly, monthly) via calendar.
  - `task_options_dialog.py`: `TaskOptionsDialog` modal for task creation and editing task options (name and paid/unpaid status).
  - `task_panel.py`: `TaskPanel` for task selection and management with "Add Earnings..." action.
  - `clock_panel.py`: `ClockPanel` for timer display and clock in/out controls.
  - `history_panel.py`: `HistoryPanel` for session logs and statistics.
- **`main.py`**: Application entry point assembling configuration (`load_config()`), storage, engine, and launching the UI.
- **`scripts/`**: Automation scripts:
  - `generate_icon.py`: Pure-Python clock icon renderer compiling multi-resolution PNGs and macOS `assets/AppIcon.icns`.
  - `install_macos.sh`: Standalone installer packaging `Time Clock.app` into `/Applications` or `~/Applications`.
  - `update_macos.sh`: Fast code updater for installed `/Applications/Time Clock.app` bundles preserving user data.

---

## 2. Build & Configuration Instructions

### Prerequisites
- Python 3.8+ (standard installation including `tkinter`).
- No external packages (pip dependencies or virtual environments) are required for core execution or testing.

### Running the Application
From the repository root:
```bash
python3 main.py
```
By default, application state is stored at `data/time_clock.db`. The directory and database tables are created automatically on launch.

---

## 3. Testing Information

The project uses Python's standard library `unittest` framework.

### Running Existing Tests

- **Run all test suites**:
  ```bash
  python3 -m unittest discover tests
  ```
- **Run a specific test module**:
  ```bash
  python3 -m unittest tests/test_engine.py
  # or using module path:
  python3 -m unittest tests.test_models
  ```
- **Run a specific test case or method**:
  ```bash
  python3 -m unittest tests.test_models.TestModels.test_format_duration
  ```

### Guidelines for Adding New Tests

1. Place new test files in the `tests/` directory named `test_<module_or_feature>.py`.
2. Define a class inheriting from `unittest.TestCase` with test methods prefixed with `test_`.
3. For tests involving disk persistence (`SQLiteStorage` / `TimeClockEngine`), use `tempfile.mkdtemp()` in `setUp()` and remove the temporary directory in `tearDown()` to prevent side effects on real user data.
4. For GUI tests (`time_clock/gui/`), create a hidden `tk.Tk()` root (`root.withdraw()`) and catch `tk.TclError` in `setUp()` by calling `self.skipTest(...)` to support headless test environments. Ensure all `tk.Toplevel` dialogs are automatically withdrawn on creation and mock mapped states (`winfo_ismapped`) rather than calling `deiconify()` to keep the entire test suite completely silent without window popups or stealing OS focus. Call `root.update_idletasks()` after engine state changes to flush event listeners.

### Example Working Test

To demonstrate adding a unit test for a utility or engine feature:

```python
import unittest
from time_clock.models import format_duration


class TestSample(unittest.TestCase):
    """Demonstration unit test verifying duration string formatting."""

    def test_sample_duration_formatting(self):
        # Format 3661 seconds as HH:MM:SS (01 hour, 01 minute, 01 second)
        self.assertEqual(format_duration(3661), "01:01:01")


if __name__ == "__main__":
    unittest.main()
```

Execute the test via:
```bash
python3 -m unittest tests/test_sample.py
```

---

## 4. Additional Development & Debugging Guidelines

- **Typing & Compatibility**: Use strict type hints and include `from __future__ import annotations` across all modules.
- **Code Style**: Follow PEP 8 (4-space indents, snake_case functions/variables, PascalCase classes, UPPER_SNAKE_CASE constants).
- **Event Bus Contract**: Whenever modifying `TimeClockEngine` or adding new domain actions, emit the appropriate `EventType` via `self.event_bus.emit(...)`. UI panels subscribe to these events rather than querying engine state on intervals.
- **Time Representation**: All timestamps are stored in UTC ISO-8601 strings (`iso_now()`) and parsed via `parse_iso()`. Durations are represented in seconds (`float`).
- **Unpaid Tasks Domain Contract**: Unpaid tasks (`Task.is_unpaid = True`) accumulate total time and period statistics but return `0.0` for unreported durations and are excluded from unreported task aggregates.

---

## 5. User Documentation Maintenance (`README.md`)

`README.md` is strictly reserved for user-facing documentation to ensure end users have an intuitive and comprehensive guide.

Whenever new features are added, modified, or deprecated:
1. **Synchronize `README.md`**: Update `README.md` to document any new UI elements, panels, menus, options, workflows, or export formats from the user's perspective.
2. **Preserve User-Facing Focus**: Do not include internal implementation details, developer setup, code architectures, class names, or unit test instructions in `README.md`. Keep explanations centered on practical usage, step-by-step instructions, and expected behavior.
3. **Keep Developer Information in `AGENTS.md`**: Document internal architectural contracts, database schemas, event definitions, testing procedures, or backend patterns here in `.junie/AGENTS.md`.
