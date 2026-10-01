# Developer & Agent Guidelines for Time Clock

This document contains project-specific information, setup instructions, testing guidelines, and architectural details to assist development on the **Time Clock** application.

---

## 1. Project Overview & Architecture

**Time Clock** is a modular Python desktop time tracking application with zero external runtime dependencies. It uses a decoupled, event-driven architecture structured as follows:

- **`time_clock/models.py`**: Domain dataclasses (`TimeEntry`, `Task`, `AppState`) with explicit dictionary serialization/deserialization methods (`to_dict` / `from_dict`) and duration/ISO-8601 formatting utilities (`format_duration`, `iso_now`, `parse_iso`).
- **`time_clock/storage.py`**: `SQLiteStorage` (and base `Storage`) persisting domain state to SQLite database (default: `data/time_clock.db`) with automatic table creation and legacy JSON migration handling.
- **`time_clock/events.py`**: In-process synchronous publish-subscribe `EventBus` using the `EventType` enum for decoupling the business logic from GUI components.
- **`time_clock/engine.py`**: `TimeClockEngine` coordinator implementing business rules (clocking in/out, task CRUD, duration calculations, active timer tracking) and emitting lifecycle events.
- **`time_clock/gui/`**: Tkinter/ttk desktop interface divided into modular panels:
  - `app.py`: `TimeClockApp` main window and container.
  - `task_panel.py`: `TaskPanel` for task selection and management.
  - `clock_panel.py`: `ClockPanel` for timer display and clock in/out controls.
  - `history_panel.py`: `HistoryPanel` for session logs and statistics.
- **`main.py`**: Application entry point assembling dependencies and launching the UI.

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
4. For GUI tests (`time_clock/gui/`), create a hidden `tk.Tk()` root (`root.withdraw()`) and catch `tk.TclError` in `setUp()` by calling `self.skipTest(...)` to support headless test environments. Call `root.update_idletasks()` after engine state changes to flush event listeners.

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

---

## 5. User Documentation Maintenance (`README.md`)

`README.md` is strictly reserved for user-facing documentation to ensure end users have an intuitive and comprehensive guide.

Whenever new features are added, modified, or deprecated:
1. **Synchronize `README.md`**: Update `README.md` to document any new UI elements, panels, menus, options, workflows, or export formats from the user's perspective.
2. **Preserve User-Facing Focus**: Do not include internal implementation details, developer setup, code architectures, class names, or unit test instructions in `README.md`. Keep explanations centered on practical usage, step-by-step instructions, and expected behavior.
3. **Keep Developer Information in `AGENTS.md`**: Document internal architectural contracts, database schemas, event definitions, testing procedures, or backend patterns here in `.junie/AGENTS.md`.
