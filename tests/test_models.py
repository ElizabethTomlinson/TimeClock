"""Unit tests for models and formatting helpers."""
import unittest
from datetime import datetime

from time_clock.models import (
    AppState,
    PeriodDurations,
    Task,
    TimeEntry,
    calculate_interval_overlap,
    format_duration,
    get_period_bounds,
    iso_now,
    parse_iso,
)


class TestModels(unittest.TestCase):
    def test_format_duration(self):
        self.assertEqual(format_duration(0), "00:00:00")
        self.assertEqual(format_duration(5), "00:00:05")
        self.assertEqual(format_duration(65), "00:01:05")
        self.assertEqual(format_duration(3600), "01:00:00")
        self.assertEqual(format_duration(3665.4), "01:01:05")
        self.assertEqual(format_duration(-10), "00:00:00")

    def test_iso_helpers(self):
        now_str = iso_now()
        dt = parse_iso(now_str)
        self.assertIsInstance(dt, datetime)

    def test_time_entry_serialization(self):
        entry = TimeEntry(
            id="entry-1",
            start_time="2026-09-30T10:00:00",
            end_time="2026-09-30T10:15:30",
            duration_seconds=930.0,
        )
        data = entry.to_dict()
        restored = TimeEntry.from_dict(data)

        self.assertEqual(restored.id, "entry-1")
        self.assertEqual(restored.start_time, "2026-09-30T10:00:00")
        self.assertEqual(restored.end_time, "2026-09-30T10:15:30")
        self.assertEqual(restored.duration_seconds, 930.0)

    def test_task_duration_aggregation(self):
        task = Task(id="t-1", name="Coding", created_at="2026-09-30T09:00:00")
        self.assertEqual(task.total_duration_seconds, 0.0)

        task.entries.append(TimeEntry(id="e1", start_time="2026-09-30T09:00:00", duration_seconds=120.0))
        task.entries.append(TimeEntry(id="e2", start_time="2026-09-30T10:00:00", duration_seconds=240.5))

        self.assertEqual(task.total_duration_seconds, 360.5)

    def test_task_serialization(self):
        task = Task(
            id="t-1",
            name="Documentation",
            created_at="2026-09-30T09:00:00",
            last_reported_at="2026-09-30T09:30:00",
            entries=[
                TimeEntry(id="e1", start_time="2026-09-30T09:00:00", end_time="2026-09-30T09:30:00", duration_seconds=1800.0)
            ],
        )
        data = task.to_dict()
        restored = Task.from_dict(data)

        self.assertEqual(restored.id, task.id)
        self.assertEqual(restored.name, task.name)
        self.assertEqual(restored.created_at, task.created_at)
        self.assertEqual(restored.last_reported_at, "2026-09-30T09:30:00")
        self.assertFalse(restored.is_archived)
        self.assertEqual(len(restored.entries), 1)
        self.assertEqual(restored.entries[0].duration_seconds, 1800.0)

    def test_task_archive_serialization(self):
        task = Task(
            id="t-archived",
            name="Old Project",
            created_at="2026-09-01T08:00:00",
            is_archived=True,
        )
        data = task.to_dict()
        self.assertTrue(data.get("is_archived"))
        restored = Task.from_dict(data)
        self.assertTrue(restored.is_archived)

        # Default is_archived when missing
        restored_default = Task.from_dict({"id": "t2", "name": "Active", "created_at": "2026-09-01T08:00:00"})
        self.assertFalse(restored_default.is_archived)

    def test_task_unpaid_serialization_and_defaults(self):
        task = Task(
            id="t-unpaid",
            name="Unpaid Activity",
            created_at="2026-09-01T08:00:00",
            is_unpaid=True,
        )
        data = task.to_dict()
        self.assertTrue(data.get("is_unpaid"))
        restored = Task.from_dict(data)
        self.assertTrue(restored.is_unpaid)

        # Default is_unpaid is False when missing or default
        restored_default = Task.from_dict({"id": "t2", "name": "Paid Work", "created_at": "2026-09-01T08:00:00"})
        self.assertFalse(restored_default.is_unpaid)
        task_default = Task(id="t3", name="Default Task", created_at="2026-09-01T08:00:00")
        self.assertFalse(task_default.is_unpaid)

    def test_unpaid_task_unreported_duration(self):
        task = Task(
            id="t-unpaid",
            name="Unpaid Project",
            created_at="2026-10-01T08:00:00",
            is_unpaid=True,
            entries=[
                TimeEntry(id="e1", start_time="2026-10-01T08:00:00", end_time="2026-10-01T09:00:00", duration_seconds=3600.0),
                TimeEntry(id="e2", start_time="2026-10-01T09:30:00", end_time="2026-10-01T10:00:00", duration_seconds=1800.0),
            ],
        )
        # Total duration is still computed
        self.assertEqual(task.total_duration_seconds, 5400.0)
        # Unreported duration is always 0.0 for unpaid tasks
        self.assertEqual(task.calculate_unreported_duration(), 0.0)
        self.assertEqual(task.calculate_unreported_duration(as_of="2026-10-01T08:30:00"), 0.0)

    def test_unreported_duration_no_cutoff(self):
        task = Task(
            id="t1",
            name="No Cutoff",
            created_at="2026-10-01T08:00:00",
            entries=[
                TimeEntry(id="e1", start_time="2026-10-01T08:00:00", end_time="2026-10-01T09:00:00", duration_seconds=3600.0),
                TimeEntry(id="e2", start_time="2026-10-01T09:30:00", end_time="2026-10-01T10:00:00", duration_seconds=1800.0),
            ],
        )
        self.assertEqual(task.calculate_unreported_duration(), 5400.0)

    def test_unreported_duration_all_reported(self):
        task = Task(
            id="t1",
            name="All Reported",
            created_at="2026-10-01T08:00:00",
            last_reported_at="2026-10-01T11:00:00",
            entries=[
                TimeEntry(id="e1", start_time="2026-10-01T08:00:00", end_time="2026-10-01T09:00:00", duration_seconds=3600.0),
                TimeEntry(id="e2", start_time="2026-10-01T09:30:00", end_time="2026-10-01T10:00:00", duration_seconds=1800.0),
            ],
        )
        self.assertEqual(task.calculate_unreported_duration(), 0.0)

    def test_unreported_duration_partial_and_spanning_entries(self):
        task = Task(
            id="t1",
            name="Mixed Entries",
            created_at="2026-10-01T08:00:00",
            last_reported_at="2026-10-01T10:00:00",
            entries=[
                # Completed before cutoff -> 0
                TimeEntry(id="e1", start_time="2026-10-01T08:00:00", end_time="2026-10-01T09:00:00", duration_seconds=3600.0),
                # Spanning across cutoff (09:30 - 10:30) -> 30 min (1800s) unreported
                TimeEntry(id="e2", start_time="2026-10-01T09:30:00", end_time="2026-10-01T10:30:00", duration_seconds=3600.0),
                # Started and finished after cutoff (11:00 - 12:00) -> 3600s unreported
                TimeEntry(id="e3", start_time="2026-10-01T11:00:00", end_time="2026-10-01T12:00:00", duration_seconds=3600.0),
            ],
        )
        # Total unreported = 1800 + 3600 = 5400
        self.assertEqual(task.calculate_unreported_duration(), 5400.0)
        # Total duration = 3600 + 3600 + 3600 = 10800
        self.assertEqual(task.total_duration_seconds, 10800.0)

        # Overriding with custom as_of parameter
        self.assertEqual(task.calculate_unreported_duration(as_of="2026-10-01T11:30:00"), 1800.0)

    def test_app_state_serialization(self):
        state = AppState(
            tasks={
                "t1": Task(id="t1", name="Task 1", created_at="2026-09-30T08:00:00"),
                "t2": Task(id="t2", name="Task 2", created_at="2026-09-30T08:30:00"),
            },
            active_task_id="t1",
            is_running=True,
            current_session_start="2026-09-30T09:00:00",
        )
        data = state.to_dict()
        restored = AppState.from_dict(data)

        self.assertEqual(len(restored.tasks), 2)
        self.assertIn("t1", restored.tasks)
        self.assertIn("t2", restored.tasks)
        self.assertEqual(restored.active_task_id, "t1")
        self.assertTrue(restored.is_running)
        self.assertEqual(restored.current_session_start, "2026-09-30T09:00:00")

    def test_get_period_bounds(self):
        # Wednesday 2026-10-07 14:30:00
        ref_dt = datetime(2026, 10, 7, 14, 30, 0)
        bounds = get_period_bounds(ref_dt)
        self.assertEqual(bounds["day"], datetime(2026, 10, 7, 0, 0, 0))
        self.assertEqual(bounds["week"], datetime(2026, 10, 5, 0, 0, 0))  # Monday
        self.assertEqual(bounds["month"], datetime(2026, 10, 1, 0, 0, 0))

        # Sunday 2026-10-11 23:59:59
        ref_sunday = datetime(2026, 10, 11, 23, 59, 59)
        bounds_sunday = get_period_bounds(ref_sunday)
        self.assertEqual(bounds_sunday["day"], datetime(2026, 10, 11, 0, 0, 0))
        self.assertEqual(bounds_sunday["week"], datetime(2026, 10, 5, 0, 0, 0))
        self.assertEqual(bounds_sunday["month"], datetime(2026, 10, 1, 0, 0, 0))

        # Monday 2026-10-05 00:00:00
        ref_monday = datetime(2026, 10, 5, 0, 0, 0)
        bounds_monday = get_period_bounds(ref_monday)
        self.assertEqual(bounds_monday["day"], datetime(2026, 10, 5, 0, 0, 0))
        self.assertEqual(bounds_monday["week"], datetime(2026, 10, 5, 0, 0, 0))
        self.assertEqual(bounds_monday["month"], datetime(2026, 10, 1, 0, 0, 0))

    def test_calculate_interval_overlap(self):
        w_start = datetime(2026, 10, 1, 0, 0, 0)
        w_end = datetime(2026, 10, 1, 12, 0, 0)

        # 1. Full containment
        self.assertEqual(
            calculate_interval_overlap(
                datetime(2026, 10, 1, 2, 0, 0),
                datetime(2026, 10, 1, 4, 0, 0),
                w_start,
                w_end,
            ),
            7200.0,
        )

        # 2. Straddling start
        self.assertEqual(
            calculate_interval_overlap(
                datetime(2026, 9, 30, 23, 0, 0),
                datetime(2026, 10, 1, 1, 0, 0),
                w_start,
                w_end,
            ),
            3600.0,
        )

        # 3. Straddling end
        self.assertEqual(
            calculate_interval_overlap(
                datetime(2026, 10, 1, 11, 0, 0),
                datetime(2026, 10, 1, 13, 0, 0),
                w_start,
                w_end,
            ),
            3600.0,
        )

        # 4. Completely outside before
        self.assertEqual(
            calculate_interval_overlap(
                datetime(2026, 9, 30, 20, 0, 0),
                datetime(2026, 9, 30, 22, 0, 0),
                w_start,
                w_end,
            ),
            0.0,
        )

        # 5. Completely outside after
        self.assertEqual(
            calculate_interval_overlap(
                datetime(2026, 10, 1, 13, 0, 0),
                datetime(2026, 10, 1, 14, 0, 0),
                w_start,
                w_end,
            ),
            0.0,
        )

        # 6. Spanning entire window
        self.assertEqual(
            calculate_interval_overlap(
                datetime(2026, 9, 30, 0, 0, 0),
                datetime(2026, 10, 2, 0, 0, 0),
                w_start,
                w_end,
            ),
            43200.0,
        )

    def test_period_durations_dataclass(self):
        pd = PeriodDurations(day=3661.0, week=7200.0, month=10800.0)
        self.assertEqual(
            pd.formatted_dict(),
            {
                "day": "01:01:01",
                "week": "02:00:00",
                "month": "03:00:00",
            },
        )
        self.assertEqual(
            pd.to_dict(),
            {
                "day": 3661.0,
                "week": 7200.0,
                "month": 10800.0,
            },
        )


if __name__ == "__main__":
    unittest.main()
