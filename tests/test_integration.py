"""End-to-end integration tests for TimeClock application workflow."""
import csv
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from time_clock.engine import TimeClockEngine
from time_clock.events import EventBus, EventType
from time_clock.models import format_duration
from time_clock.storage import SQLiteStorage


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.db_file = self.test_dir / "time_clock.db"
        self.storage = SQLiteStorage(self.db_file)
        self.bus = EventBus()
        self.engine = TimeClockEngine(storage=self.storage, event_bus=self.bus)

    def tearDown(self):
        self.storage.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_lifecycle_and_persistence_reload(self):
        # 1. Create multiple tasks
        task_backend = self.engine.create_task("Backend API")
        task_frontend = self.engine.create_task("Frontend UI")

        self.assertEqual(len(self.engine.get_tasks()), 2)
        self.assertEqual(self.engine.state.active_task_id, task_backend.id)

        # 2. Clock in and track time on backend task
        self.engine.select_task(task_backend.id)
        start_time_1 = self.engine.clock_in()
        self.assertTrue(self.engine.state.is_running)

        time.sleep(0.05)
        entry_1 = self.engine.clock_out()
        self.assertFalse(self.engine.state.is_running)
        self.assertGreater(entry_1.duration_seconds, 0)
        self.assertEqual(len(task_backend.entries), 1)

        # 3. Switch to frontend task and clock in
        self.engine.select_task(task_frontend.id)
        start_time_2 = self.engine.clock_in()
        time.sleep(0.05)

        # 4. Switching back to backend task while running should auto clock-out frontend
        self.engine.select_task(task_backend.id)
        self.assertFalse(self.engine.state.is_running)
        self.assertEqual(len(task_frontend.entries), 1)

        # 5. Add a second session to backend task
        self.engine.clock_in()
        time.sleep(0.05)
        entry_2 = self.engine.clock_out()
        self.assertEqual(len(task_backend.entries), 2)
        backend_total = task_backend.total_duration_seconds
        self.assertAlmostEqual(backend_total, entry_1.duration_seconds + entry_2.duration_seconds, places=4)

        # 6. Simulate application restart by loading from SQLite database in a new engine instance
        new_bus = EventBus()
        new_storage = SQLiteStorage(self.db_file)
        restored_engine = TimeClockEngine(storage=new_storage, event_bus=new_bus)

        restored_tasks = restored_engine.get_tasks()
        self.assertEqual(len(restored_tasks), 2)

        restored_backend = restored_engine.get_task(task_backend.id)
        restored_frontend = restored_engine.get_task(task_frontend.id)

        self.assertIsNotNone(restored_backend)
        self.assertIsNotNone(restored_frontend)
        self.assertEqual(restored_backend.name, "Backend API")
        self.assertEqual(restored_frontend.name, "Frontend UI")
        self.assertEqual(len(restored_backend.entries), 2)
        self.assertEqual(len(restored_frontend.entries), 1)
        self.assertAlmostEqual(restored_backend.total_duration_seconds, backend_total, places=4)

        # 7. Test data export from the restored engine
        export_csv_path = self.test_dir / "integration_export.csv"
        restored_engine.export_data(export_csv_path, format="csv")
        self.assertTrue(export_csv_path.exists())

        with open(export_csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        self.assertEqual(len(reader), 3)  # 2 backend entries + 1 frontend entry

        export_json_path = self.test_dir / "integration_export.json"
        restored_engine.export_data(export_json_path, format="json")
        self.assertTrue(export_json_path.exists())

        with open(export_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data["tasks"]), 2)

    def test_app_on_close_auto_clock_out(self):
        task = self.engine.create_task("Emergency Task")
        self.engine.select_task(task.id)
        self.engine.clock_in()
        self.assertTrue(self.engine.state.is_running)

        # Simulate graceful shutdown logic
        if self.engine.state.is_running:
            self.engine.clock_out()

        self.assertFalse(self.engine.state.is_running)

        # Verify disk state has finalized session
        reloaded_state = self.storage.load()
        self.assertFalse(reloaded_state.is_running)
        self.assertEqual(len(reloaded_state.tasks[task.id].entries), 1)

    def test_reporting_workflow_integration(self):
        # 1. Create a task and log a 1-hour session
        task = self.engine.create_task("Reporting Integration Task")
        self.engine.select_task(task.id)
        self.engine.clock_in()
        time.sleep(0.05)
        self.engine.clock_out()

        # Unreported time equals total duration initially
        self.assertAlmostEqual(
            self.engine.get_task_unreported_duration(task.id),
            task.total_duration_seconds,
            places=2,
        )

        # 2. Mark task as reported
        self.engine.mark_task_reported(task.id)
        self.assertEqual(self.engine.get_task_unreported_duration(task.id), 0.0)

        # 3. Log another session after cutoff
        self.engine.clock_in()
        time.sleep(0.05)
        entry_2 = self.engine.clock_out()

        self.assertAlmostEqual(
            self.engine.get_task_unreported_duration(task.id),
            entry_2.duration_seconds,
            places=2,
        )
        self.assertGreater(task.total_duration_seconds, self.engine.get_task_unreported_duration(task.id))

        # 4. Reload across fresh engine and SQLiteStorage instance
        new_storage = SQLiteStorage(self.db_file)
        new_engine = TimeClockEngine(storage=new_storage)
        reloaded_task = new_engine.get_task(task.id)
        self.assertIsNotNone(reloaded_task.last_reported_at)
        self.assertAlmostEqual(
            new_engine.get_task_unreported_duration(task.id),
            entry_2.duration_seconds,
            places=2,
        )
        new_storage.close()


if __name__ == "__main__":
    unittest.main()
