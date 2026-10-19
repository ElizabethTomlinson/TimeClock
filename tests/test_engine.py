"""Unit tests for TimeClockEngine business logic and event integration."""
import shutil
import tempfile
import time
import unittest
from datetime import datetime
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

    def test_mark_task_reported_with_earning(self):
        task = self.engine.create_task("Combined Task")
        reported_events = []
        earning_events = []
        self.bus.subscribe(EventType.TASK_REPORTED, lambda e: reported_events.append(e))
        self.bus.subscribe(EventType.EARNING_ADDED, lambda e: earning_events.append(e))

        # Add sessions completed today
        entry = TimeEntry(
            id="e1",
            start_time="2026-10-10T10:00:00",
            end_time="2026-10-10T12:00:00",
            duration_seconds=7200.0,
        )
        task.entries.append(entry)
        self.engine._save_state()
        self.assertEqual(self.engine.get_task_unreported_duration(task.id), 7200.0)

        # 1. Successful combined reporting with explicit reported_at
        updated_task, entry_res = self.engine.mark_task_reported_with_earning(
            task_id=task.id,
            amount=250.0,
            earned_at="2026-10-10T00:00:00",
            note="Milestone 1",
            reported_at="2026-10-10T14:00:00",
        )
        self.assertEqual(entry_res.amount, 250.0)
        self.assertEqual(entry_res.task_id, task.id)
        self.assertEqual(entry_res.note, "Milestone 1")
        self.assertEqual(updated_task.last_reported_at, "2026-10-10T14:00:00")
        self.assertEqual(self.engine.get_task_unreported_duration(task.id), 0.0)
        self.assertEqual(len(reported_events), 1)
        self.assertEqual(len(earning_events), 1)

        # 2. Combined reporting without reported_at defaults cutoff to iso_now(), not earned_at
        task.entries.append(
            TimeEntry(
                id="e2",
                start_time="2026-10-10T15:00:00",
                end_time="2026-10-10T16:00:00",
                duration_seconds=3600.0,
            )
        )
        self.engine._save_state()
        self.assertEqual(self.engine.get_task_unreported_duration(task.id), 3600.0)

        # Even with past date earned_at, cutoff defaults to now and zeros out unreported duration
        updated_task2, entry_res2 = self.engine.mark_task_reported_with_earning(
            task_id=task.id,
            amount=150.0,
            earned_at="2026-10-01T00:00:00",
            note="Past date earning",
        )
        self.assertEqual(entry_res2.earned_at, "2026-10-01T00:00:00")
        self.assertNotEqual(updated_task2.last_reported_at, "2026-10-01T00:00:00")
        self.assertEqual(self.engine.get_task_unreported_duration(task.id), 0.0)

        # 3. Running session test with mark_task_reported_with_earning
        self.engine.select_task(task.id)
        self.engine.clock_in()
        # Immediately reporting with earning sets cutoff to now, zeroing past duration
        updated_task3, entry_res3 = self.engine.mark_task_reported_with_earning(
            task_id=task.id,
            amount=100.0,
        )
        self.assertIsNotNone(updated_task3.last_reported_at)
        # Running duration since last_reported_at is minimal (<= 1s)
        self.assertAlmostEqual(self.engine.get_task_unreported_duration(task.id), 0.0, delta=1.0)
        self.engine.clock_out()

        # Unpaid task rejection
        unpaid = self.engine.create_task("Unpaid Internal", is_unpaid=True)
        with self.assertRaises(ValueError):
            self.engine.mark_task_reported_with_earning(
                task_id=unpaid.id,
                amount=100.0,
            )

        # Non-existent task rejection
        with self.assertRaises(KeyError):
            self.engine.mark_task_reported_with_earning(
                task_id="bad_id",
                amount=100.0,
            )

        # Non-positive amount rejection
        with self.assertRaises(ValueError):
            self.engine.mark_task_reported_with_earning(
                task_id=task.id,
                amount=-50.0,
            )
        with self.assertRaises(ValueError):
            self.engine.mark_task_reported_with_earning(
                task_id=task.id,
                amount=0.0,
            )

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

    def test_get_period_durations_boundaries(self):
        # Reference datetime: Wednesday 2026-10-14 15:00:00
        # Day start: 2026-10-14 00:00:00
        # Week start: Monday 2026-10-12 00:00:00
        # Month start: 2026-10-01 00:00:00
        as_of = datetime(2026, 10, 14, 15, 0, 0)

        t1 = self.engine.create_task("Task 1")
        # 1. Today: 3600s
        t1.entries.append(
            TimeEntry(id="e1", start_time="2026-10-14T10:00:00", end_time="2026-10-14T11:00:00", duration_seconds=3600.0)
        )
        # 2. Earlier this week: 3600s
        t1.entries.append(
            TimeEntry(id="e2", start_time="2026-10-13T10:00:00", end_time="2026-10-13T11:00:00", duration_seconds=3600.0)
        )
        # 3. Earlier this month (prior week): 3600s
        t1.entries.append(
            TimeEntry(id="e3", start_time="2026-10-05T10:00:00", end_time="2026-10-05T11:00:00", duration_seconds=3600.0)
        )
        # 4. Prior month (September): 3600s
        t1.entries.append(
            TimeEntry(id="e4", start_time="2026-09-25T10:00:00", end_time="2026-09-25T11:00:00", duration_seconds=3600.0)
        )
        self.engine._save_state()

        durations = self.engine.get_period_durations(as_of=as_of, include_running=False)
        self.assertEqual(durations["day"], 3600.0)
        self.assertEqual(durations["week"], 7200.0)
        self.assertEqual(durations["month"], 10800.0)

    def test_get_period_durations_includes_archived_tasks(self):
        as_of = datetime(2026, 10, 14, 15, 0, 0)
        t_active = self.engine.create_task("Active Task")
        t_archived = self.engine.create_task("Archived Task")

        t_active.entries.append(
            TimeEntry(id="e1", start_time="2026-10-14T09:00:00", end_time="2026-10-14T10:00:00", duration_seconds=3600.0)
        )
        t_archived.entries.append(
            TimeEntry(id="e2", start_time="2026-10-14T11:00:00", end_time="2026-10-14T12:00:00", duration_seconds=3600.0)
        )
        self.engine.archive_task(t_archived.id)

        durations = self.engine.get_period_durations(as_of=as_of, include_running=False)
        self.assertEqual(durations["day"], 7200.0)
        self.assertEqual(durations["week"], 7200.0)
        self.assertEqual(durations["month"], 7200.0)

    def test_get_period_durations_with_running_timer(self):
        t = self.engine.create_task("Live Task")
        self.engine.select_task(t.id)

        # Set running state starting 2 hours before as_of
        self.engine.state.is_running = True
        self.engine.state.current_session_start = "2026-10-14T13:00:00"
        as_of = datetime(2026, 10, 14, 15, 0, 0)

        durations_with = self.engine.get_period_durations(as_of=as_of, include_running=True)
        durations_without = self.engine.get_period_durations(as_of=as_of, include_running=False)

        self.assertEqual(durations_with["day"], 7200.0)
        self.assertEqual(durations_without["day"], 0.0)

    def test_tick_includes_period_durations(self):
        task = self.engine.create_task("Period Ticks Task")
        self.engine.clock_in()

        tick_events = []
        self.bus.subscribe(EventType.TICK, lambda e: tick_events.append(e))

        payload = self.engine.tick()
        self.assertIn("day_duration", payload)
        self.assertIn("day_duration_formatted", payload)
        self.assertIn("week_duration", payload)
        self.assertIn("week_duration_formatted", payload)
        self.assertIn("month_duration", payload)
        self.assertIn("month_duration_formatted", payload)
        self.assertEqual(len(tick_events), 1)
        self.assertEqual(tick_events[0].data["day_duration_formatted"], payload["day_duration_formatted"])

    def test_update_current_session_start_success(self):
        task = self.engine.create_task("Session Start Task")
        self.engine.select_task(task.id)
        self.engine.clock_in()

        events = []
        self.bus.subscribe(EventType.ENTRY_UPDATED, lambda e: events.append(e))

        past_time = "2026-10-01T08:00:00"
        self.engine.update_current_session_start(past_time)

        self.assertEqual(self.engine.state.current_session_start, past_time)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].data["type"], "active_session")
        self.assertEqual(events[0].data["start_time"], past_time)

        # Verify persisted
        reloaded = self.storage.load()
        self.assertEqual(reloaded.current_session_start, past_time)

    def test_update_current_session_start_not_running_fails(self):
        task = self.engine.create_task("Not Running Task")
        with self.assertRaises(ValueError):
            self.engine.update_current_session_start("2026-10-01T08:00:00")

    def test_update_current_session_start_future_time_fails(self):
        task = self.engine.create_task("Future Time Task")
        self.engine.select_task(task.id)
        self.engine.clock_in()

        future_time = "2099-01-01T00:00:00"
        with self.assertRaises(ValueError):
            self.engine.update_current_session_start(future_time)

    def test_update_time_entry_success_recalculates_duration(self):
        task = self.engine.create_task("Update Entry Task")
        self.engine.select_task(task.id)
        entry = self.engine.add_manual_time_entry(
            task.id, "2026-10-01T09:00:00", "2026-10-01T10:00:00"
        )
        self.assertEqual(entry.duration_seconds, 3600.0)

        events = []
        self.bus.subscribe(EventType.ENTRY_UPDATED, lambda e: events.append(e))

        updated = self.engine.update_time_entry(
            task.id, entry.id, "2026-10-01T08:30:00", "2026-10-01T10:00:00"
        )
        self.assertEqual(updated.duration_seconds, 5400.0)
        self.assertEqual(task.total_duration_seconds, 5400.0)
        self.assertEqual(len(events), 1)

        # Verify persisted
        reloaded = self.storage.load()
        reloaded_entry = reloaded.tasks[task.id].entries[0]
        self.assertEqual(reloaded_entry.duration_seconds, 5400.0)

    def test_update_time_entry_invalid_order_fails(self):
        task = self.engine.create_task("Invalid Order Task")
        entry = self.engine.add_manual_time_entry(
            task.id, "2026-10-01T09:00:00", "2026-10-01T10:00:00"
        )
        with self.assertRaises(ValueError):
            self.engine.update_time_entry(
                task.id, entry.id, "2026-10-01T11:00:00", "2026-10-01T10:00:00"
            )

    def test_add_manual_time_entry_success(self):
        task = self.engine.create_task("Manual Entry Task")
        events = []
        self.bus.subscribe(EventType.ENTRY_UPDATED, lambda e: events.append(e))

        entry = self.engine.add_manual_time_entry(
            task.id, "2026-10-01T14:00:00", "2026-10-01T15:30:00"
        )
        self.assertEqual(entry.duration_seconds, 5400.0)
        self.assertEqual(len(task.entries), 1)
        self.assertEqual(task.entries[0].id, entry.id)
        self.assertEqual(len(events), 1)

        # Verify persistence
        reloaded = self.storage.load()
        self.assertEqual(len(reloaded.tasks[task.id].entries), 1)
        self.assertEqual(reloaded.tasks[task.id].entries[0].duration_seconds, 5400.0)

    def test_create_and_update_unpaid_task(self):
        events = []
        self.bus.subscribe(EventType.TASK_CREATED, lambda e: events.append(e))
        self.bus.subscribe(EventType.TASK_UPDATED, lambda e: events.append(e))

        # 1. Create unpaid task
        unpaid_task = self.engine.create_task("Internal Admin", is_unpaid=True)
        self.assertTrue(unpaid_task.is_unpaid)
        self.assertEqual(len(events), 1)

        # Verify persisted
        reloaded = self.storage.load()
        self.assertTrue(reloaded.tasks[unpaid_task.id].is_unpaid)

        # 2. Update task options (change name and paid status)
        updated = self.engine.update_task_options(
            unpaid_task.id, name="Internal Admin Renamed", is_unpaid=False
        )
        self.assertEqual(updated.name, "Internal Admin Renamed")
        self.assertFalse(updated.is_unpaid)
        self.assertGreaterEqual(len(events), 2)

        # Verify persisted change
        reloaded2 = self.storage.load()
        self.assertEqual(reloaded2.tasks[unpaid_task.id].name, "Internal Admin Renamed")
        self.assertFalse(reloaded2.tasks[unpaid_task.id].is_unpaid)

    def test_unpaid_task_excluded_from_unreported_time(self):
        paid_task = self.engine.create_task("Client Work", is_unpaid=False)
        unpaid_task = self.engine.create_task("Open Source", is_unpaid=True)

        self.engine.add_manual_time_entry(paid_task.id, "2026-10-01T09:00:00", "2026-10-01T10:00:00")
        self.engine.add_manual_time_entry(unpaid_task.id, "2026-10-01T10:00:00", "2026-10-01T12:00:00")

        self.assertEqual(self.engine.get_task_unreported_duration(paid_task.id), 3600.0)
        self.assertEqual(self.engine.get_task_unreported_duration(unpaid_task.id), 0.0)
        self.assertFalse(self.engine.has_unreported_time(unpaid_task.id))
        self.assertTrue(self.engine.has_unreported_time(paid_task.id))

        unreported_tasks = self.engine.get_unreported_tasks()
        self.assertEqual(len(unreported_tasks), 1)
        self.assertEqual(unreported_tasks[0].id, paid_task.id)
        self.assertEqual(self.engine.get_unreported_tasks_count(), 1)
        self.assertEqual(self.engine.get_total_unreported_duration(), 3600.0)

        # Check running active session on unpaid task
        self.engine.select_task(unpaid_task.id)
        self.engine.clock_in()
        self.assertEqual(self.engine.get_task_unreported_duration(unpaid_task.id, include_running=True), 0.0)
        self.assertEqual(self.engine.get_total_unreported_duration(include_running=True), 3600.0)

        # Check get_period_durations includes both paid and unpaid
        period_durations = self.engine.get_period_durations(
            as_of=datetime.fromisoformat("2026-10-01T23:59:59"), include_running=False
        )
        self.assertEqual(period_durations["day"], 10800.0)  # 3600 + 7200

    def test_consolidate_tasks_basic(self):
        # Create 3 tasks with the exact same name
        t1 = self.engine.create_task("Client Work")
        t1.created_at = "2026-10-01T08:00:00"
        t1.entries.append(
            TimeEntry(id="e1", start_time="2026-10-01T09:00:00", end_time="2026-10-01T10:00:00", duration_seconds=3600.0)
        )

        t2 = self.engine.create_task("Client Work")
        t2.created_at = "2026-10-02T08:00:00"
        t2.entries.append(
            TimeEntry(id="e2", start_time="2026-10-02T09:00:00", end_time="2026-10-02T09:30:00", duration_seconds=1800.0)
        )

        t3 = self.engine.create_task("Client Work")
        t3.created_at = "2026-10-03T08:00:00"
        t3.entries.append(
            TimeEntry(id="e3", start_time="2026-10-03T09:00:00", end_time="2026-10-03T11:00:00", duration_seconds=7200.0)
        )
        self.engine._save_state()

        self.engine.add_earning(t1.id, 100.0, "2026-10-01", "Initial deposit")
        self.engine.add_earning(t2.id, 200.0, "2026-10-02", "Milestone 1")
        self.engine.add_earning(t3.id, 300.0, "2026-10-03", "Milestone 2")

        events_emitted = []
        self.bus.subscribe(EventType.TASKS_CONSOLIDATED, lambda e: events_emitted.append(e))

        summary = self.engine.consolidate_tasks_by_name()
        self.assertEqual(summary["groups_consolidated"], 1)
        self.assertEqual(summary["tasks_merged"], 3)
        self.assertEqual(summary["tasks_removed"], 2)
        self.assertEqual(len(events_emitted), 1)

        # Verify only 1 task remains
        self.assertEqual(len(self.engine.state.tasks), 1)
        consolidated = self.engine.get_task(t1.id)
        self.assertIsNotNone(consolidated)
        self.assertEqual(consolidated.name, "Client Work")
        self.assertEqual(consolidated.created_at, "2026-10-01T08:00:00")
        self.assertEqual(len(consolidated.entries), 3)
        self.assertEqual([e.id for e in consolidated.entries], ["e1", "e2", "e3"])
        self.assertEqual(consolidated.total_duration_seconds, 12600.0)

        # Verify earnings reassignment
        earnings = self.storage.get_earnings(task_id=t1.id)
        self.assertEqual(len(earnings), 3)
        self.assertEqual(sum(e.amount for e in earnings), 600.0)

        # Verify persistence across engine reload
        new_engine = TimeClockEngine(storage=self.storage, event_bus=EventBus())
        self.assertEqual(len(new_engine.state.tasks), 1)
        reloaded = new_engine.get_task(t1.id)
        self.assertEqual(len(reloaded.entries), 3)
        self.assertEqual(reloaded.total_duration_seconds, 12600.0)

    def test_consolidate_tasks_with_active_running_session(self):
        t1 = self.engine.create_task("Design Project")
        t1.created_at = "2026-10-01T08:00:00"
        t2 = self.engine.create_task("Design Project")
        t2.created_at = "2026-10-02T08:00:00"
        self.engine._save_state()

        # Select t2 and start timer
        self.engine.select_task(t2.id)
        self.engine.clock_in()
        self.assertTrue(self.engine.state.is_running)
        self.assertEqual(self.engine.state.active_task_id, t2.id)

        summary = self.engine.consolidate_tasks_by_name()
        self.assertEqual(summary["groups_consolidated"], 1)
        self.assertEqual(summary["tasks_merged"], 2)
        self.assertEqual(summary["tasks_removed"], 1)

        # Running status and timer should be preserved on primary task
        self.assertTrue(self.engine.state.is_running)
        self.assertEqual(self.engine.state.active_task_id, t1.id)

        # Clock out and verify entry added to t1
        self.engine.clock_out()
        self.assertFalse(self.engine.state.is_running)
        self.assertEqual(len(t1.entries), 1)

    def test_consolidate_tasks_metadata_resolution(self):
        # Group 1: 1 paid, 1 unpaid -> consolidated paid
        t1 = self.engine.create_task("Dev Task", is_unpaid=True)
        t1.created_at = "2026-10-02T08:00:00"
        t1.last_reported_at = "2026-10-02T12:00:00"
        t2 = self.engine.create_task("Dev Task", is_unpaid=False)
        t2.created_at = "2026-10-01T08:00:00"
        t2.last_reported_at = "2026-10-04T12:00:00"

        # Group 2: all unpaid -> consolidated unpaid
        u1 = self.engine.create_task("Admin", is_unpaid=True)
        u1.created_at = "2026-10-01T08:00:00"
        u2 = self.engine.create_task("Admin", is_unpaid=True)
        u2.created_at = "2026-10-03T08:00:00"

        # Group 3: 1 active, 1 archived -> consolidated active
        a1 = self.engine.create_task("Maintenance")
        a1.created_at = "2026-10-01T08:00:00"
        a2 = self.engine.create_task("Maintenance")
        a2.created_at = "2026-10-05T08:00:00"
        self.engine.archive_task(a2.id)

        # Group 4: all archived -> consolidated archived
        r1 = self.engine.create_task("Old Project")
        r1.created_at = "2026-10-01T08:00:00"
        r2 = self.engine.create_task("Old Project")
        r2.created_at = "2026-10-06T08:00:00"
        self.engine.archive_task(r1.id)
        self.engine.archive_task(r2.id)

        self.engine._save_state()

        summary = self.engine.consolidate_tasks_by_name()
        self.assertEqual(summary["groups_consolidated"], 4)
        self.assertEqual(summary["tasks_merged"], 8)
        self.assertEqual(summary["tasks_removed"], 4)

        dev_task = self.engine.get_task(t2.id)
        self.assertFalse(dev_task.is_unpaid)
        self.assertEqual(dev_task.last_reported_at, "2026-10-04T12:00:00")
        self.assertEqual(dev_task.created_at, "2026-10-01T08:00:00")

        admin_task = self.engine.get_task(u1.id)
        self.assertTrue(admin_task.is_unpaid)

        maint_task = self.engine.get_task(a1.id)
        self.assertFalse(maint_task.is_archived)

        old_task = self.engine.get_task(r1.id)
        self.assertTrue(old_task.is_archived)

    def test_consolidate_tasks_no_duplicates(self):
        self.engine.create_task("Task Alpha")
        self.engine.create_task("Task Beta")
        self.engine.create_task("Task Gamma")

        summary = self.engine.consolidate_tasks_by_name()
        self.assertEqual(summary["groups_consolidated"], 0)
        self.assertEqual(summary["tasks_merged"], 0)
        self.assertEqual(summary["tasks_removed"], 0)
        self.assertEqual(len(self.engine.state.tasks), 3)


if __name__ == "__main__":
    unittest.main()
