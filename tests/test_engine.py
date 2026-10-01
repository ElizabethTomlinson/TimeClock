"""Unit tests for TimeClockEngine business logic and event integration."""
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from time_clock.engine import TimeClockEngine
from time_clock.events import EventBus, EventType
from time_clock.models import AppState, Task, TimeEntry, iso_now
from time_clock.storage import SQLiteStorage


class TestTimeClockEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.db_path = self.test_dir / "test.db"
        self.storage = SQLiteStorage(self.db_path)
        self.bus = EventBus()
        self.engine = TimeClockEngine(storage=self.storage, event_bus=self.bus)

    def tearDown(self):
        self.storage.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_initialization_dispatches_state_loaded(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventType.STATE_LOADED, lambda e: events.append(e))
        engine = TimeClockEngine(storage=self.storage, event_bus=bus)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, EventType.STATE_LOADED)

    def test_create_task_success(self):
        events = []
        self.bus.subscribe(EventType.TASK_CREATED, lambda e: events.append(e))

        task = self.engine.create_task("Project Planning")
        self.assertEqual(task.name, "Project Planning")
        self.assertEqual(self.engine.state.active_task_id, task.id)
        self.assertIn(task.id, self.engine.state.tasks)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].data.id, task.id)

        # Verify auto-save
        reloaded = self.storage.load()
        self.assertIn(task.id, reloaded.tasks)

    def test_create_task_empty_name_fails(self):
        with self.assertRaises(ValueError):
            self.engine.create_task("   ")

    def test_select_task(self):
        t1 = self.engine.create_task("Task 1")
        t2 = self.engine.create_task("Task 2")

        events = []
        self.bus.subscribe(EventType.TASK_SELECTED, lambda e: events.append(e))

        selected = self.engine.select_task(t1.id)
        self.assertEqual(selected.id, t1.id)
        self.assertEqual(self.engine.state.active_task_id, t1.id)
        self.assertEqual(len(events), 1)

        with self.assertRaises(KeyError):
            self.engine.select_task("non_existent_id")

    def test_rename_task(self):
        t1 = self.engine.create_task("Old Name")
        events = []
        self.bus.subscribe(EventType.TASK_RENAMED, lambda e: events.append(e))

        renamed = self.engine.rename_task(t1.id, "New Name")
        self.assertEqual(renamed.name, "New Name")
        self.assertEqual(self.engine.get_task(t1.id).name, "New Name")
        self.assertEqual(len(events), 1)

        with self.assertRaises(ValueError):
            self.engine.rename_task(t1.id, "  ")

        with self.assertRaises(KeyError):
            self.engine.rename_task("bad_id", "Valid")

    def test_delete_task(self):
        t1 = self.engine.create_task("Task 1")
        t2 = self.engine.create_task("Task 2")

        events = []
        self.bus.subscribe(EventType.TASK_DELETED, lambda e: events.append(e))

        self.engine.select_task(t1.id)
        self.engine.delete_task(t1.id)

        self.assertNotIn(t1.id, self.engine.state.tasks)
        self.assertEqual(self.engine.state.active_task_id, t2.id)
        self.assertEqual(len(events), 1)

        with self.assertRaises(KeyError):
            self.engine.delete_task("non_existent")

    def test_clock_in_and_clock_out(self):
        task = self.engine.create_task("Feature Implementation")
        clock_in_events = []
        clock_out_events = []
        self.bus.subscribe(EventType.CLOCK_IN, lambda e: clock_in_events.append(e))
        self.bus.subscribe(EventType.CLOCK_OUT, lambda e: clock_out_events.append(e))

        start_time = self.engine.clock_in()
        self.assertTrue(self.engine.state.is_running)
        self.assertEqual(self.engine.state.current_session_start, start_time)
        self.assertEqual(len(clock_in_events), 1)

        # Cannot clock in again while running
        with self.assertRaises(ValueError):
            self.engine.clock_in()

        time.sleep(0.05)

        entry = self.engine.clock_out()
        self.assertIsNotNone(entry)
        self.assertFalse(self.engine.state.is_running)
        self.assertIsNone(self.engine.state.current_session_start)
        self.assertEqual(len(clock_out_events), 1)
        self.assertGreaterEqual(entry.duration_seconds, 0.0)
        self.assertEqual(len(task.entries), 1)

        # Cannot clock out when not running
        with self.assertRaises(ValueError):
            self.engine.clock_out()

    def test_clock_in_without_task_fails(self):
        empty_storage = SQLiteStorage(self.test_dir / "empty.db")
        empty_engine = TimeClockEngine(storage=empty_storage)
        with self.assertRaises(ValueError):
            empty_engine.clock_in()
        empty_storage.close()

    def test_switching_task_while_clocked_in_auto_clocks_out(self):
        t1 = self.engine.create_task("Task 1")
        t2 = self.engine.create_task("Task 2")

        self.engine.select_task(t1.id)
        self.engine.clock_in()
        self.assertTrue(self.engine.state.is_running)

        # Switch to Task 2
        self.engine.select_task(t2.id)

        # Should have stopped clock for Task 1
        self.assertFalse(self.engine.state.is_running)
        self.assertEqual(len(t1.entries), 1)
        self.assertEqual(self.engine.state.active_task_id, t2.id)

    def test_tick_event_dispatch(self):
        task = self.engine.create_task("Testing Ticks")
        self.engine.clock_in()

        tick_events = []
        self.bus.subscribe(EventType.TICK, lambda e: tick_events.append(e))

        payload = self.engine.tick()
        self.assertTrue(payload["is_running"])
        self.assertEqual(payload["active_task_id"], task.id)
        self.assertIn("unreported_duration", payload)
        self.assertIn("unreported_duration_formatted", payload)
        self.assertIn("last_reported_at", payload)
        self.assertEqual(len(tick_events), 1)

    def test_mark_and_clear_task_reported(self):
        task = self.engine.create_task("Task for Reporting")
        events = []
        self.bus.subscribe(EventType.TASK_REPORTED, lambda e: events.append(e))

        # 1. Mark as reported with current time
        updated = self.engine.mark_task_reported(task.id)
        self.assertIsNotNone(updated.last_reported_at)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].data.id, task.id)

        # Verify persisted
        reloaded = self.storage.load()
        self.assertEqual(reloaded.tasks[task.id].last_reported_at, updated.last_reported_at)

        # 2. Mark with custom timestamp
        custom_ts = "2026-10-01T15:00:00"
        updated2 = self.engine.mark_task_reported(task.id, custom_ts)
        self.assertEqual(updated2.last_reported_at, custom_ts)
        self.assertEqual(len(events), 2)

        # 3. Clear reported status
        cleared = self.engine.clear_task_reported(task.id)
        self.assertIsNone(cleared.last_reported_at)
        self.assertEqual(len(events), 3)

        reloaded_cleared = self.storage.load()
        self.assertIsNone(reloaded_cleared.tasks[task.id].last_reported_at)

        # Bad task ID error cases
        with self.assertRaises(KeyError):
            self.engine.mark_task_reported("bad_id")
        with self.assertRaises(KeyError):
            self.engine.clear_task_reported("bad_id")

    def test_engine_unreported_duration_calculations(self):
        task = self.engine.create_task("Duration Calculation Task")
        self.engine.select_task(task.id)

        # Add a historical entry
        entry = TimeEntry(
            id="e1",
            start_time="2026-10-01T08:00:00",
            end_time="2026-10-01T09:00:00",
            duration_seconds=3600.0,
        )
        task.entries.append(entry)
        self.engine._save_state()

        # Without cutoff -> 3600
        self.assertEqual(self.engine.get_task_unreported_duration(task.id), 3600.0)

        # With cutoff at 09:00:00 -> 0
        self.engine.mark_task_reported(task.id, "2026-10-01T09:00:00")
        self.assertEqual(self.engine.get_task_unreported_duration(task.id), 0.0)

        # Non-existent task returns 0.0
        self.assertEqual(self.engine.get_task_unreported_duration("unknown"), 0.0)

    def test_get_unreported_tasks_query(self):
        t1 = self.engine.create_task("Project 1")
        t2 = self.engine.create_task("Project 2")
        t3 = self.engine.create_task("Project 3")

        # Initially, 0 unreported tasks
        self.assertEqual(self.engine.get_unreported_tasks(), [])
        self.assertEqual(self.engine.get_unreported_tasks_count(), 0)
        self.assertEqual(self.engine.get_total_unreported_duration(), 0.0)
        self.assertFalse(self.engine.has_unreported_time(t1.id))

        # Add completed entry to t1
        t1.entries.append(
            TimeEntry(
                id="e1",
                start_time="2026-10-01T10:00:00",
                end_time="2026-10-01T11:00:00",
                duration_seconds=3600.0,
            )
        )
        self.engine._save_state()

        self.assertTrue(self.engine.has_unreported_time(t1.id))
        self.assertFalse(self.engine.has_unreported_time(t2.id))
        self.assertEqual(self.engine.get_unreported_tasks_count(), 1)
        self.assertEqual([t.id for t in self.engine.get_unreported_tasks()], [t1.id])
        self.assertEqual(self.engine.get_total_unreported_duration(), 3600.0)

        # Active running session on t2
        self.engine.select_task(t2.id)
        self.engine.clock_in()

        # With include_running=True (default), t2 is also counted
        self.assertTrue(self.engine.has_unreported_time(t2.id, include_running=True))
        self.assertEqual(self.engine.get_unreported_tasks_count(include_running=True), 2)
        # With include_running=False, t2 has 0 recorded entries yet
        self.assertFalse(self.engine.has_unreported_time(t2.id, include_running=False))
        self.assertEqual(self.engine.get_unreported_tasks_count(include_running=False), 1)

        self.engine.clock_out()
        # Mark t1 as reported
        self.engine.mark_task_reported(t1.id, "2026-10-01T12:00:00")
        self.assertFalse(self.engine.has_unreported_time(t1.id))
        self.assertEqual(self.engine.get_unreported_tasks_count(), 1)
        self.assertEqual([t.id for t in self.engine.get_unreported_tasks()], [t2.id])

    def test_archive_task_success(self):
        t1 = self.engine.create_task("Task 1")
        t2 = self.engine.create_task("Task 2")
        self.engine.select_task(t1.id)

        events = []
        self.bus.subscribe(EventType.TASK_ARCHIVED, lambda e: events.append(e))

        archived = self.engine.archive_task(t1.id)
        self.assertTrue(archived.is_archived)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].data.id, t1.id)
        # active task falls back to t2
        self.assertEqual(self.engine.state.active_task_id, t2.id)

        # verify persisted
        reloaded = self.storage.load()
        self.assertTrue(reloaded.tasks[t1.id].is_archived)

        with self.assertRaises(KeyError):
            self.engine.archive_task("non_existent")

    def test_archive_active_running_task_auto_clocks_out(self):
        t1 = self.engine.create_task("Running Task")
        t2 = self.engine.create_task("Backup Task")
        self.engine.select_task(t1.id)
        self.engine.clock_in()

        self.assertTrue(self.engine.state.is_running)

        clock_out_events = []
        archive_events = []
        self.bus.subscribe(EventType.CLOCK_OUT, lambda e: clock_out_events.append(e))
        self.bus.subscribe(EventType.TASK_ARCHIVED, lambda e: archive_events.append(e))

        self.engine.archive_task(t1.id)

        self.assertFalse(self.engine.state.is_running)
        self.assertIsNone(self.engine.state.current_session_start)
        self.assertEqual(len(clock_out_events), 1)
        self.assertEqual(len(archive_events), 1)
        self.assertEqual(len(t1.entries), 1)
        self.assertEqual(self.engine.state.active_task_id, t2.id)

    def test_archive_only_task_clears_active_selection(self):
        t1 = self.engine.create_task("Sole Task")
        self.assertEqual(self.engine.state.active_task_id, t1.id)

        self.engine.archive_task(t1.id)
        self.assertIsNone(self.engine.state.active_task_id)

    def test_unarchive_task(self):
        t1 = self.engine.create_task("Archived Task")
        self.engine.archive_task(t1.id)
        self.assertTrue(t1.is_archived)
        self.assertIsNone(self.engine.state.active_task_id)

        events = []
        self.bus.subscribe(EventType.TASK_UNARCHIVED, lambda e: events.append(e))

        restored = self.engine.unarchive_task(t1.id)
        self.assertFalse(restored.is_archived)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].data.id, t1.id)
        # Because active_task_id was None, restored task becomes active
        self.assertEqual(self.engine.state.active_task_id, t1.id)

        # verify persisted
        reloaded = self.storage.load()
        self.assertFalse(reloaded.tasks[t1.id].is_archived)

        with self.assertRaises(KeyError):
            self.engine.unarchive_task("bad_id")

    def test_get_tasks_filtering(self):
        t1 = self.engine.create_task("Active Task 1")
        t2 = self.engine.create_task("Active Task 2")
        t3 = self.engine.create_task("Archived Task")
        self.engine.archive_task(t3.id)

        active_tasks = self.engine.get_tasks(include_archived=False)
        self.assertEqual(len(active_tasks), 2)
        self.assertEqual({t.id for t in active_tasks}, {t1.id, t2.id})

        all_tasks = self.engine.get_tasks(include_archived=True)
        self.assertEqual(len(all_tasks), 3)
        self.assertEqual({t.id for t in all_tasks}, {t1.id, t2.id, t3.id})

        archived_tasks = self.engine.get_archived_tasks()
        self.assertEqual(len(archived_tasks), 1)
        self.assertEqual(archived_tasks[0].id, t3.id)

    def test_unreported_queries_exclude_archived_tasks(self):
        t_active = self.engine.create_task("Active with time")
        t_archived = self.engine.create_task("Archived with time")

        t_active.entries.append(
            TimeEntry(id="e1", start_time="2026-10-01T08:00:00", end_time="2026-10-01T09:00:00", duration_seconds=3600.0)
        )
        t_archived.entries.append(
            TimeEntry(id="e2", start_time="2026-10-01T08:00:00", end_time="2026-10-01T09:00:00", duration_seconds=3600.0)
        )
        self.engine._save_state()

        self.assertEqual(self.engine.get_unreported_tasks_count(), 2)
        self.assertEqual(self.engine.get_total_unreported_duration(), 7200.0)

        # Archive t_archived
        self.engine.archive_task(t_archived.id)

        self.assertEqual(self.engine.get_unreported_tasks_count(), 1)
        self.assertEqual([t.id for t in self.engine.get_unreported_tasks()], [t_active.id])
        self.assertEqual(self.engine.get_total_unreported_duration(), 3600.0)


if __name__ == "__main__":
    unittest.main()
