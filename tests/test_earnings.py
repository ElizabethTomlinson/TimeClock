"""Unit and integration tests for earnings domain models, storage, and engine calculations."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from time_clock.engine import TimeClockEngine
from time_clock.events import EventBus, EventType
from time_clock.models import EarningEntry, EarningsPeriodStats, MonthlyGoal
from time_clock.storage import SQLiteStorage


class TestEarningsModelsAndStorage(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_earnings.db"
        self.storage = SQLiteStorage(self.db_path)
        self.event_bus = EventBus()
        self.engine = TimeClockEngine(storage=self.storage, event_bus=self.event_bus)

    def tearDown(self) -> None:
        self.storage.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_earning_entry_dataclass_and_dict(self) -> None:
        entry = EarningEntry(
            id="earn_1",
            task_id="task_1",
            amount=150.50,
            earned_at="2026-10-11T10:00:00",
            note="Consulting work",
        )
        d = entry.to_dict()
        self.assertEqual(d["id"], "earn_1")
        self.assertEqual(d["task_id"], "task_1")
        self.assertEqual(d["amount"], 150.50)
        self.assertEqual(d["earned_at"], "2026-10-11T10:00:00")
        self.assertEqual(d["note"], "Consulting work")

        restored = EarningEntry.from_dict(d)
        self.assertEqual(restored.id, entry.id)
        self.assertEqual(restored.amount, entry.amount)
        self.assertEqual(restored.note, entry.note)

    def test_monthly_goal_dataclass_and_dict(self) -> None:
        goal = MonthlyGoal(month_key="2026-10", goal_amount=4000.0, use_28_day_month=True)
        d = goal.to_dict()
        self.assertEqual(d["month_key"], "2026-10")
        self.assertEqual(d["goal_amount"], 4000.0)
        self.assertTrue(d["use_28_day_month"])

        restored = MonthlyGoal.from_dict(d)
        self.assertEqual(restored.month_key, goal.month_key)
        self.assertEqual(restored.goal_amount, goal.goal_amount)
        self.assertTrue(restored.use_28_day_month)

    def test_storage_earnings_crud_and_cascade(self) -> None:
        task = self.engine.create_task("Client Work")
        entry1 = EarningEntry(
            id="earn_1",
            task_id=task.id,
            amount=100.0,
            earned_at="2026-10-10T12:00:00",
            note="Design phase",
        )
        entry2 = EarningEntry(
            id="earn_2",
            task_id=task.id,
            amount=250.0,
            earned_at="2026-10-11T14:00:00",
            note="Dev phase",
        )
        self.storage.add_earning(entry1)
        self.storage.add_earning(entry2)

        earnings = self.storage.get_earnings()
        self.assertEqual(len(earnings), 2)
        # Ordered by earned_at desc
        self.assertEqual(earnings[0].id, "earn_2")
        self.assertEqual(earnings[1].id, "earn_1")

        # Filter by task
        task_earnings = self.storage.get_earnings(task_id=task.id)
        self.assertEqual(len(task_earnings), 2)

        # Delete single earning
        self.storage.delete_earning("earn_1")
        self.assertEqual(len(self.storage.get_earnings()), 1)

        # Cascade on task deletion
        self.engine.delete_task(task.id)
        self.assertEqual(len(self.storage.get_earnings()), 0)

    def test_storage_monthly_goals(self) -> None:
        default_goal = self.storage.get_monthly_goal("2026-10")
        self.assertEqual(default_goal.goal_amount, 0.0)
        self.assertFalse(default_goal.use_28_day_month)

        goal = MonthlyGoal(month_key="2026-10", goal_amount=5000.0, use_28_day_month=True)
        self.storage.set_monthly_goal(goal)

        saved = self.storage.get_monthly_goal("2026-10")
        self.assertEqual(saved.goal_amount, 5000.0)
        self.assertTrue(saved.use_28_day_month)


class TestEngineEarningsCalculations(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_engine_earnings.db"
        self.storage = SQLiteStorage(self.db_path)
        self.event_bus = EventBus()
        self.engine = TimeClockEngine(storage=self.storage, event_bus=self.event_bus)
        self.task = self.engine.create_task("Development")

    def tearDown(self) -> None:
        self.storage.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_engine_add_and_delete_earning_events(self) -> None:
        added_events = []
        deleted_events = []
        self.event_bus.subscribe(EventType.EARNING_ADDED, lambda e: added_events.append(e))
        self.event_bus.subscribe(EventType.EARNING_DELETED, lambda e: deleted_events.append(e))

        earning = self.engine.add_earning(
            task_id=self.task.id,
            amount=300.0,
            earned_at="2026-10-11T15:30:00",
            note="Milestone 1",
        )
        self.assertEqual(len(added_events), 1)
        self.assertEqual(added_events[0].data["earning"].id, earning.id)
        self.assertEqual(added_events[0].data["task"].id, self.task.id)

        self.engine.delete_earning(earning.id)
        self.assertEqual(len(deleted_events), 1)
        self.assertEqual(deleted_events[0].data["earning_id"], earning.id)
        self.assertEqual(len(self.engine.get_earnings()), 0)

    def test_engine_add_earning_validation(self) -> None:
        with self.assertRaises(KeyError):
            self.engine.add_earning("nonexistent_task", 100.0)

        with self.assertRaises(ValueError):
            self.engine.add_earning(self.task.id, 0.0)

        with self.assertRaises(ValueError):
            self.engine.add_earning(self.task.id, -50.0)

    def test_engine_monthly_goal_setting_and_event(self) -> None:
        goal_events = []
        self.event_bus.subscribe(EventType.GOAL_UPDATED, lambda e: goal_events.append(e))

        goal = self.engine.set_monthly_goal(
            goal_amount=3000.0,
            use_28_day_month=False,
            month_key="2026-11",
        )
        self.assertEqual(goal.goal_amount, 3000.0)
        self.assertEqual(len(goal_events), 1)

        retrieved = self.engine.get_monthly_goal("2026-11")
        self.assertEqual(retrieved.goal_amount, 3000.0)

        with self.assertRaises(ValueError):
            self.engine.set_monthly_goal(goal_amount=-100.0, month_key="2026-11")

    def test_daily_needed_standard_30_day_month(self) -> None:
        # As of 2026-11-10 (November has 30 days)
        # On day 10, remaining days in target period = 30 - 10 + 1 = 21 days
        # Goal = $3,000, Earned = $1,000 -> Remaining Goal = $2,000
        # Needed per day = 2000 / 21 = 95.238095...
        as_of = datetime(2026, 11, 10, 12, 0, 0)
        self.engine.set_monthly_goal(3000.0, use_28_day_month=False, month_key="2026-11")

        self.engine.add_earning(
            task_id=self.task.id,
            amount=1000.0,
            earned_at="2026-11-05T10:00:00",
        )

        stats = self.engine.get_earnings_stats(as_of=as_of)
        self.assertEqual(stats.month_total, 1000.0)
        self.assertAlmostEqual(stats.needed_per_day, 2000.0 / 21.0, places=4)
        self.assertAlmostEqual(stats.month_progress_pct, (1000.0 / 3000.0) * 100.0, places=2)

    def test_daily_needed_28_day_month_option(self) -> None:
        # As of 2026-11-10 (November, 4-week mode = 28 days target)
        # On day 10, remaining days in target period = 28 - 10 + 1 = 19 days
        # Goal = $3,000, Earned = $1,000 -> Remaining Goal = $2,000
        # Needed per day = 2000 / 19 = 105.263157...
        as_of = datetime(2026, 11, 10, 12, 0, 0)
        self.engine.set_monthly_goal(3000.0, use_28_day_month=True, month_key="2026-11")

        self.engine.add_earning(
            task_id=self.task.id,
            amount=1000.0,
            earned_at="2026-11-05T10:00:00",
        )

        stats = self.engine.get_earnings_stats(as_of=as_of)
        self.assertEqual(stats.month_total, 1000.0)
        self.assertTrue(stats.use_28_day_month)
        self.assertAlmostEqual(stats.needed_per_day, 2000.0 / 19.0, places=4)

        # Daily and weekly targets in 28-day mode:
        # daily_target = 3000 / 28 = 107.1428...
        # weekly_target = 3000 / 4 = 750.0
        # In this week (Nov 5 is Thursday in previous week or same week?), let's verify
        daily_target = 3000.0 / 28.0
        weekly_target = 3000.0 / 4.0
        self.assertAlmostEqual(stats.day_progress_pct, 0.0)  # No earning on Nov 10

    def test_earnings_on_day_29_in_28_day_mode(self) -> None:
        # As of 2026-11-29 in 28-day mode
        as_of = datetime(2026, 11, 29, 12, 0, 0)
        self.engine.set_monthly_goal(3000.0, use_28_day_month=True, month_key="2026-11")

        self.engine.add_earning(
            task_id=self.task.id,
            amount=2500.0,
            earned_at="2026-11-20T10:00:00",
        )
        self.engine.add_earning(
            task_id=self.task.id,
            amount=200.0,
            earned_at="2026-11-29T10:00:00",
        )

        stats = self.engine.get_earnings_stats(as_of=as_of)
        # Total month includes days 1-29
        self.assertEqual(stats.month_total, 2700.0)
        self.assertEqual(stats.day_total, 200.0)
        # Day 29 > 28, remaining target days clamps to 1
        self.assertAlmostEqual(stats.needed_per_day, 300.0 / 1.0, places=2)

    def test_overachieved_goal_and_zero_goal(self) -> None:
        as_of = datetime(2026, 10, 15, 12, 0, 0)

        # Zero goal
        self.engine.set_monthly_goal(0.0, use_28_day_month=False, month_key="2026-10")
        stats = self.engine.get_earnings_stats(as_of=as_of)
        self.assertEqual(stats.needed_per_day, 0.0)
        self.assertEqual(stats.month_progress_pct, 0.0)

        # Overachieved goal: $3500 earned on $3000 goal
        self.engine.set_monthly_goal(3000.0, use_28_day_month=False, month_key="2026-10")
        self.engine.add_earning(
            task_id=self.task.id,
            amount=3500.0,
            earned_at="2026-10-10T10:00:00",
        )
        stats = self.engine.get_earnings_stats(as_of=as_of)
        self.assertEqual(stats.needed_per_day, 0.0)
        self.assertAlmostEqual(stats.month_progress_pct, (3500.0 / 3000.0) * 100.0, places=2)

    def test_date_aggregation_day_week_month(self) -> None:
        # Monday 2026-10-12
        as_of = datetime(2026, 10, 12, 14, 0, 0)
        self.engine.set_monthly_goal(2000.0, use_28_day_month=False, month_key="2026-10")

        # Today (Oct 12)
        self.engine.add_earning(self.task.id, 100.0, earned_at="2026-10-12T09:00:00")
        # Same week (Oct 13 - future in week or Oct 12 is Monday so week start is Oct 12)
        # Past day in same month (Oct 05 - previous week)
        self.engine.add_earning(self.task.id, 150.0, earned_at="2026-10-05T11:00:00")
        # Past month (Sept 20)
        self.engine.add_earning(self.task.id, 500.0, earned_at="2026-09-20T11:00:00")

        stats = self.engine.get_earnings_stats(as_of=as_of)
        self.assertEqual(stats.day_total, 100.0)
        self.assertEqual(stats.week_total, 100.0)
        self.assertEqual(stats.month_total, 250.0)  # 100 + 150

    def test_earnings_period_stats_serialization(self) -> None:
        from time_clock.models import EarningsPeriodStats

        stats = EarningsPeriodStats(
            day_total=50.0,
            week_total=200.0,
            month_total=800.0,
            goal_amount=2000.0,
            needed_per_day=75.0,
            use_28_day_month=False,
            day_progress_pct=77.5,
            week_progress_pct=44.2,
            month_progress_pct=40.0,
            week_pace_pct=42.86,
            month_pace_pct=45.16,
            week_expected_total=300.0,
            month_expected_total=900.0,
        )
        d = stats.to_dict()
        self.assertEqual(d["week_pace_pct"], 42.86)
        self.assertEqual(d["month_pace_pct"], 45.16)
        self.assertEqual(d["week_expected_total"], 300.0)
        self.assertEqual(d["month_expected_total"], 900.0)

        restored = EarningsPeriodStats.from_dict(d)
        self.assertEqual(restored.week_pace_pct, 42.86)
        self.assertEqual(restored.month_pace_pct, 45.16)
        self.assertEqual(restored.week_expected_total, 300.0)
        self.assertEqual(restored.month_expected_total, 900.0)

    def test_earnings_period_stats_pace_calculation(self) -> None:
        # Wednesday 2026-10-14 (weekday 2 -> day 3 of 7)
        as_of = datetime(2026, 10, 14, 15, 0, 0)
        # Goal = $3,100 across 31 days in October -> daily target = $100, weekly target = $700
        self.engine.set_monthly_goal(3100.0, use_28_day_month=False, month_key="2026-10")

        stats = self.engine.get_earnings_stats(as_of=as_of)
        # Week pace: day 3 of 7 -> (3/7) * 100%
        self.assertAlmostEqual(stats.week_pace_pct, (3.0 / 7.0) * 100.0, places=4)
        self.assertAlmostEqual(stats.week_expected_total, 300.0, places=2)

        # Month pace: day 14 of 31 -> (14/31) * 100%
        self.assertAlmostEqual(stats.month_pace_pct, (14.0 / 31.0) * 100.0, places=4)
        self.assertAlmostEqual(stats.month_expected_total, 1400.0, places=2)

    def test_28_day_month_pace_clamping(self) -> None:
        # Day 14 of 28-day cycle: 14/28 = 50%
        self.engine.set_monthly_goal(2800.0, use_28_day_month=True, month_key="2026-11")
        as_of_14 = datetime(2026, 11, 14, 12, 0, 0)
        stats_14 = self.engine.get_earnings_stats(as_of=as_of_14)
        self.assertAlmostEqual(stats_14.month_pace_pct, 50.0, places=4)
        self.assertAlmostEqual(stats_14.month_expected_total, 1400.0, places=2)

        # Day 28 of 28-day cycle: 28/28 = 100%
        as_of_28 = datetime(2026, 11, 28, 12, 0, 0)
        stats_28 = self.engine.get_earnings_stats(as_of=as_of_28)
        self.assertAlmostEqual(stats_28.month_pace_pct, 100.0, places=4)
        self.assertAlmostEqual(stats_28.month_expected_total, 2800.0, places=2)

        # Day 29 of 28-day cycle: clamped to 100%
        as_of_29 = datetime(2026, 11, 29, 12, 0, 0)
        stats_29 = self.engine.get_earnings_stats(as_of=as_of_29)
        self.assertAlmostEqual(stats_29.month_pace_pct, 100.0, places=4)
        self.assertAlmostEqual(stats_29.month_expected_total, 2800.0, places=2)

    def test_zero_goal_pace_stats(self) -> None:
        as_of = datetime(2026, 10, 14, 12, 0, 0)
        self.engine.set_monthly_goal(0.0, use_28_day_month=False, month_key="2026-10")
        stats = self.engine.get_earnings_stats(as_of=as_of)
        self.assertEqual(stats.week_pace_pct, 0.0)
        self.assertEqual(stats.month_pace_pct, 0.0)
        self.assertEqual(stats.week_expected_total, 0.0)
        self.assertEqual(stats.month_expected_total, 0.0)


class TestAddEarningsDialogGUI(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_gui_earnings.db"
        self.storage = SQLiteStorage(self.db_path)
        self.event_bus = EventBus()
        self.engine = TimeClockEngine(storage=self.storage, event_bus=self.event_bus)
        self.task = self.engine.create_task("Test Task")

        try:
            import tkinter as tk
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception:
            self.skipTest("Tkinter display not available in this test environment.")

        from unittest.mock import patch
        self._orig_toplevel_init = tk.Toplevel.__init__

        def silent_toplevel_init(top_self, *args, **kwargs):
            self._orig_toplevel_init(top_self, *args, **kwargs)
            try:
                top_self.withdraw()
            except Exception:
                pass

        self._toplevel_patcher = patch.object(tk.Toplevel, "__init__", silent_toplevel_init)
        self._toplevel_patcher.start()

        self._grab_patcher = patch.object(tk.Toplevel, "grab_set", return_value=None)
        self._grab_patcher.start()

        self._lift_patcher = patch.object(tk.Toplevel, "lift", return_value=None)
        self._lift_patcher.start()

        self._wait_patcher = patch.object(tk.Toplevel, "wait_window", return_value=None)
        self._wait_patcher.start()

    def tearDown(self) -> None:
        if hasattr(self, "_toplevel_patcher"):
            self._toplevel_patcher.stop()
        if hasattr(self, "_grab_patcher"):
            self._grab_patcher.stop()
        if hasattr(self, "_lift_patcher"):
            self._lift_patcher.stop()
        if hasattr(self, "_wait_patcher"):
            self._wait_patcher.stop()

        if hasattr(self, "root") and self.root:
            try:
                self.root.destroy()
            except Exception:
                pass
        self.storage.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_earnings_dialog_default_date_and_submission(self) -> None:
        from time_clock.gui.add_earnings_dialog import AddEarningsDialog

        dialog = AddEarningsDialog(
            parent=self.root,
            engine=self.engine,
            initial_task_id=self.task.id,
        )
        # Verify default date is today's date
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(dialog.date_var.get(), today_str)

        # Set amount and note
        dialog.amount_var.set("250.00")
        dialog.note_var.set("UI test earning")
        dialog._on_ok()

        earnings = self.engine.get_earnings()
        self.assertEqual(len(earnings), 1)
        self.assertEqual(earnings[0].amount, 250.0)
        self.assertEqual(earnings[0].note, "UI test earning")
        self.assertTrue(earnings[0].earned_at.startswith(today_str))

    def test_add_earnings_dialog_custom_date(self) -> None:
        from time_clock.gui.add_earnings_dialog import AddEarningsDialog

        dialog = AddEarningsDialog(
            parent=self.root,
            engine=self.engine,
            initial_task_id=self.task.id,
        )
        dialog.amount_var.set("180.50")
        dialog.date_var.set("2026-10-05")
        dialog.note_var.set("Custom date earning")
        dialog._on_ok()

        earnings = self.engine.get_earnings()
        self.assertEqual(len(earnings), 1)
        self.assertEqual(earnings[0].amount, 180.50)
        self.assertTrue(earnings[0].earned_at.startswith("2026-10-05"))

    @patch("time_clock.gui.add_earnings_dialog.messagebox.showerror")
    def test_add_earnings_dialog_invalid_inputs(self, mock_error) -> None:
        from time_clock.gui.add_earnings_dialog import AddEarningsDialog

        dialog = AddEarningsDialog(
            parent=self.root,
            engine=self.engine,
            initial_task_id=self.task.id,
        )
        # Invalid amount
        dialog.amount_var.set("invalid")
        dialog._on_ok()
        self.assertEqual(len(self.engine.get_earnings()), 0)
        mock_error.assert_called()

        # Invalid date
        mock_error.reset_mock()
        dialog.amount_var.set("100")
        dialog.date_var.set("not-a-date")
        dialog._on_ok()
        self.assertEqual(len(self.engine.get_earnings()), 0)
        mock_error.assert_called()

    def test_add_earnings_dialog_date_picker_components(self) -> None:
        from time_clock.gui.add_earnings_dialog import AddEarningsDialog

        dialog = AddEarningsDialog(
            parent=self.root,
            engine=self.engine,
            initial_task_id=self.task.id,
        )
        dialog.year_var.set("2026")
        dialog.month_var.set("08")
        dialog.day_var.set("15")
        dialog._on_date_component_changed()

        self.assertEqual(dialog.date_var.get(), "2026-08-15")
        dialog.amount_var.set("320.00")
        dialog._on_ok()

        earnings = self.engine.get_earnings()
        self.assertEqual(len(earnings), 1)
        self.assertEqual(earnings[0].amount, 320.0)
        self.assertTrue(earnings[0].earned_at.startswith("2026-08-15"))

    def test_calendar_picker_dialog(self) -> None:
        from datetime import date
        from time_clock.gui.add_earnings_dialog import CalendarPickerDialog

        cal = CalendarPickerDialog(
            parent=self.root,
            initial_date=date(2026, 5, 10),
        )
        self.assertEqual(cal.current_year, 2026)
        self.assertEqual(cal.current_month, 5)

        # Navigate next month
        cal._next_month()
        self.assertEqual(cal.current_month, 6)
        # Navigate previous month
        cal._prev_month()
        self.assertEqual(cal.current_month, 5)

        # Select a date
        cal._select_date(date(2026, 5, 22))
        self.assertEqual(cal.result, date(2026, 5, 22))

    def test_add_earnings_dialog_default_task_when_none_available(self) -> None:
        from time_clock.gui.add_earnings_dialog import AddEarningsDialog

        # Delete all existing tasks to simulate empty state
        for t_id in list(self.engine.state.tasks.keys()):
            self.engine.delete_task(t_id)
        self.assertEqual(len(self.engine.get_tasks()), 0)

        dialog = AddEarningsDialog(
            parent=self.root,
            engine=self.engine,
        )
        # Verify a default task was created and selected
        tasks = self.engine.get_tasks()
        self.assertGreaterEqual(len(tasks), 1)
        self.assertEqual(tasks[0].name, "General")
        self.assertIn("General", dialog.task_var.get())

        # Save an earning with the default task
        dialog.amount_var.set("100.00")
        dialog._on_ok()

        earnings = self.engine.get_earnings()
        self.assertEqual(len(earnings), 1)
        self.assertEqual(earnings[0].task_id, tasks[0].id)
        self.assertEqual(earnings[0].amount, 100.0)

    def test_earnings_goal_dialog_submission(self) -> None:
        from time_clock.gui.earnings_goal_dialog import EarningsGoalDialog

        month_key = "2026-10"
        dialog = EarningsGoalDialog(
            parent=self.root,
            engine=self.engine,
            month_key=month_key,
        )
        dialog.goal_var.set("4500.00")
        dialog.use_28_var.set(True)
        dialog._on_ok()

        saved = self.engine.get_monthly_goal(month_key)
        self.assertEqual(saved.goal_amount, 4500.0)
        self.assertTrue(saved.use_28_day_month)

    def test_earnings_panel_view_and_refresh(self) -> None:
        from time_clock.gui.earnings_panel import EarningsPanel

        # Set goal and add earning
        self.engine.set_monthly_goal(3000.0, use_28_day_month=True)
        earning = self.engine.add_earning(self.task.id, 500.0, note="First payment")

        panel = EarningsPanel(parent=self.root, engine=self.engine)
        self.root.update_idletasks()

        self.assertIn("3,000.00", panel.goal_lbl_var.get())
        self.assertIn("500.00", panel.earned_lbl_var.get())
        self.assertIn("28 Days", panel.cycle_lbl_var.get())

        # Check Treeview contains the entry
        children = panel.tree.get_children()
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0], earning.id)

        # Delete entry via panel action
        from unittest.mock import patch
        with patch("time_clock.gui.earnings_panel.messagebox.askyesno", return_value=True):
            panel.tree.selection_set(earning.id)
            panel._on_delete_selected_earning()

        self.assertEqual(len(self.engine.get_earnings()), 0)
        self.assertEqual(len(panel.tree.get_children()), 0)


if __name__ == "__main__":
    unittest.main()
