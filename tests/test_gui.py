"""Unit tests for Tkinter GUI panels."""
import os
import shutil
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from time_clock.engine import TimeClockEngine
from time_clock.events import EventBus
from time_clock.gui.app import TimeClockApp
from time_clock.models import TimeEntry
from time_clock.storage import SQLiteStorage


class TestGUI(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.storage = SQLiteStorage(self.test_dir / "gui_test.db")
        self.bus = EventBus()
        self.engine = TimeClockEngine(storage=self.storage, event_bus=self.bus)

        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError:
            self.skipTest("Tkinter display not available in this test environment.")

    def tearDown(self):
        if hasattr(self, "root") and self.root:
            try:
                self.root.destroy()
            except Exception:
                pass
        self.storage.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_gui_panels_initialization(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.assertIsNotNone(app.task_panel)
        self.assertIsNotNone(app.clock_panel)
        self.assertIsNotNone(app.history_panel)
        self.assertIsNotNone(app.history_panel.export_btn)

    def test_task_creation_updates_panels(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("UI Testing Task")
        self.root.update_idletasks()

        self.assertIn("UI Testing Task", app.clock_panel.task_title_var.get())
        children = app.task_panel.tree.get_children()
        self.assertEqual(len(children), 1)

    def test_clock_in_out_updates_clock_panel(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("Clock In Task")
        self.root.update_idletasks()

        self.engine.clock_in()
        self.root.update_idletasks()
        self.assertIn("Clocked In", app.clock_panel.status_var.get())
        self.assertEqual(app.clock_panel.toggle_btn.cget("text"), "Clock Out")

        self.engine.clock_out()
        self.root.update_idletasks()
        self.assertIn("Clocked Out", app.clock_panel.status_var.get())
        self.assertEqual(app.clock_panel.toggle_btn.cget("text"), "Clock In")
        self.assertIn("Sessions: 1", app.history_panel.summary_var.get())

    @patch("time_clock.gui.app.filedialog.asksaveasfilename")
    @patch("time_clock.gui.app.messagebox.showinfo")
    def test_app_prompt_export_csv(self, mock_info, mock_filedialog):
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.engine.create_task("Export UI Task")
        export_file = str(self.test_dir / "ui_export.csv")
        mock_filedialog.return_value = export_file

        result = app.prompt_export("csv")
        self.assertEqual(result, export_file)
        self.assertTrue(Path(export_file).exists())
        mock_info.assert_called_once()

    @patch("time_clock.gui.history_panel.filedialog.asksaveasfilename")
    @patch("time_clock.gui.history_panel.messagebox.showinfo")
    def test_history_panel_export_button(self, mock_info, mock_filedialog):
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("History Export Task")
        self.engine.clock_in()
        self.engine.clock_out()

        export_file = str(self.test_dir / "history_export.csv")
        mock_filedialog.return_value = export_file

        result = app.history_panel._on_export_clicked()
        self.assertEqual(result, export_file)
        self.assertTrue(Path(export_file).exists())
        mock_info.assert_called_once()

    def test_clock_panel_unreported_time_display_and_events(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("Reported UI Task")
        self.root.update_idletasks()

        self.assertIn("Unreported Time: 00:00:00", app.clock_panel.unreported_time_var.get())
        self.assertEqual(app.clock_panel.last_reported_var.get(), "Last Reported: Never")

        # Mark reported
        self.engine.mark_task_reported(task.id, "2026-10-01T09:00:00")
        self.root.update_idletasks()
        self.assertIn("2026-10-01 09:00:00", app.clock_panel.last_reported_var.get())

        # Clear reported
        self.engine.clear_task_reported(task.id)
        self.root.update_idletasks()
        self.assertEqual(app.clock_panel.last_reported_var.get(), "Last Reported: Never")

    def test_task_panel_unreported_column(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("Column Test Task")
        self.root.update_idletasks()

        # Check column names
        cols = app.task_panel.tree.cget("columns")
        self.assertIn("unreported_time", cols)

        # Check values
        item_vals = app.task_panel.tree.item(task.id, "values")
        self.assertEqual(len(item_vals), 3)
        self.assertEqual(item_vals[0], "Column Test Task")
        self.assertEqual(item_vals[1], "00:00:00")
        self.assertEqual(item_vals[2], "00:00:00")

    def test_history_panel_unreported_summary(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("History Summary Task")
        self.engine.clock_in()
        self.engine.clock_out()
        self.root.update_idletasks()

        summary = app.history_panel.summary_var.get()
        self.assertIn("Sessions: 1", summary)
        self.assertIn("Total:", summary)
        self.assertIn("Unreported:", summary)

    def test_task_panel_unreported_tag_assignment(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("Tagged Task")
        self.root.update_idletasks()

        # Initially 0 sessions -> all_reported
        tags = app.task_panel.tree.item(task.id, "tags")
        self.assertEqual(tags, ("all_reported",))

        # Add a completed session in the past -> has_unreported
        task.entries.append(
            TimeEntry(
                id="e1",
                start_time="2020-01-01T10:00:00",
                end_time="2020-01-01T11:00:00",
                duration_seconds=3600.0,
            )
        )
        self.engine._save_state()
        app.task_panel.refresh_task_list()
        self.root.update_idletasks()

        tags = app.task_panel.tree.item(task.id, "tags")
        self.assertEqual(tags, ("has_unreported",))
        self.assertEqual(app.task_panel.tree.set(task.id, "unreported_time"), "01:00:00")

        # Mark reported -> all_reported
        self.engine.mark_task_reported(task.id)
        self.root.update_idletasks()

        tags = app.task_panel.tree.item(task.id, "tags")
        self.assertEqual(tags, ("all_reported",))
        self.assertEqual(app.task_panel.tree.set(task.id, "unreported_time"), "00:00:00")

        # Clear reported -> has_unreported
        self.engine.clear_task_reported(task.id)
        self.root.update_idletasks()

        tags = app.task_panel.tree.item(task.id, "tags")
        self.assertEqual(tags, ("has_unreported",))
        self.assertEqual(app.task_panel.tree.set(task.id, "unreported_time"), "01:00:00")

    def test_task_panel_aggregate_unreported_summary(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        t1 = self.engine.create_task("Task Alpha")
        t2 = self.engine.create_task("Task Beta")
        self.root.update_idletasks()

        self.assertEqual(app.task_panel.summary_var.get(), "Unreported: 0 projects (00:00:00)")

        # Log session on t1
        t1.entries.append(
            TimeEntry(
                id="e1",
                start_time="2020-01-01T10:00:00",
                end_time="2020-01-01T11:00:00",
                duration_seconds=3600.0,
            )
        )
        self.engine._save_state()
        app.task_panel.refresh_task_list()
        self.root.update_idletasks()

        self.assertTrue(app.task_panel.summary_var.get().startswith("Unreported: 1 project ("))

        # Log session on t2
        t2.entries.append(
            TimeEntry(
                id="e2",
                start_time="2020-01-01T11:00:00",
                end_time="2020-01-01T12:00:00",
                duration_seconds=3600.0,
            )
        )
        self.engine._save_state()
        app.task_panel.refresh_task_list()
        self.root.update_idletasks()

        self.assertTrue(app.task_panel.summary_var.get().startswith("Unreported: 2 projects ("))

        # Mark t1 reported
        self.engine.mark_task_reported(t1.id)
        self.root.update_idletasks()

        self.assertTrue(app.task_panel.summary_var.get().startswith("Unreported: 1 project ("))

        # Delete t2
        self.engine.delete_task(t2.id)
        self.root.update_idletasks()

        self.assertEqual(app.task_panel.summary_var.get(), "Unreported: 0 projects (00:00:00)")

    def test_task_panel_live_tick_unreported_update(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("Live Tick Task")
        self.root.update_idletasks()

        self.assertEqual(app.task_panel.tree.item(task.id, "tags"), ("all_reported",))

        # Clock in
        self.engine.clock_in()
        self.root.update_idletasks()

        # Tick
        self.engine.tick()
        self.root.update_idletasks()

        self.assertEqual(app.task_panel.tree.item(task.id, "tags"), ("has_unreported",))
        self.assertTrue(app.task_panel.summary_var.get().startswith("Unreported: 1 project ("))

    @patch("time_clock.gui.task_panel.simpledialog.askstring")
    def test_task_panel_dialog_add_task_success(self, mock_askstring):
        mock_askstring.return_value = "Dialog Project"
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.root.update_idletasks()

        app.task_panel._on_add_task()
        self.root.update_idletasks()

        tasks = self.engine.get_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].name, "Dialog Project")
        children = app.task_panel.tree.get_children()
        self.assertEqual(len(children), 1)
        self.assertEqual(app.task_panel.tree.item(children[0], "values")[0], "Dialog Project")

    @patch("time_clock.gui.task_panel.simpledialog.askstring")
    def test_task_panel_dialog_add_task_cancelled(self, mock_askstring):
        mock_askstring.return_value = None
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.root.update_idletasks()

        app.task_panel._on_add_task()
        self.root.update_idletasks()

        tasks = self.engine.get_tasks()
        self.assertEqual(len(tasks), 0)
        self.assertEqual(len(app.task_panel.tree.get_children()), 0)

    @patch("time_clock.gui.task_panel.messagebox.showwarning")
    @patch("time_clock.gui.task_panel.simpledialog.askstring")
    def test_task_panel_dialog_add_task_empty(self, mock_askstring, mock_showwarning):
        mock_askstring.return_value = "   "
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.root.update_idletasks()

        app.task_panel._on_add_task()
        self.root.update_idletasks()

        mock_showwarning.assert_called_once()
        tasks = self.engine.get_tasks()
        self.assertEqual(len(tasks), 0)

    @patch("time_clock.gui.task_panel.messagebox.showerror")
    @patch("time_clock.gui.task_panel.simpledialog.askstring")
    def test_task_panel_dialog_add_task_error(self, mock_askstring, mock_showerror):
        mock_askstring.return_value = "Error Project"
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.root.update_idletasks()

        with patch.object(self.engine, "create_task", side_effect=ValueError("Simulated creation failure")):
            app.task_panel._on_add_task()
            self.root.update_idletasks()

        mock_showerror.assert_called_once()

    def test_app_window_configuration(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.assertEqual(self.root.title(), "Time Clock")
        self.assertEqual(self.root.minsize(), (820, 520))

    def test_task_panel_show_archived_filter(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        t1 = self.engine.create_task("Active Task")
        t2 = self.engine.create_task("Archived Task")
        self.engine.archive_task(t2.id)
        self.root.update_idletasks()

        # By default, show_archived_var is False -> only t1 is displayed
        children = app.task_panel.tree.get_children()
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0], t1.id)

        # Toggle show_archived_var to True -> both t1 and t2 displayed
        app.task_panel.show_archived_var.set(True)
        app.task_panel.refresh_task_list()
        self.root.update_idletasks()

        children = app.task_panel.tree.get_children()
        self.assertEqual(len(children), 2)
        self.assertIn(t1.id, children)
        self.assertIn(t2.id, children)

        # Verify archived task display and tag
        item_values = app.task_panel.tree.item(t2.id, "values")
        self.assertIn("[Archived]", item_values[0])
        self.assertEqual(app.task_panel.tree.item(t2.id, "tags"), ("archived",))

    @patch("time_clock.gui.task_panel.messagebox.askyesno")
    def test_task_panel_archive_and_unarchive_actions(self, mock_askyesno):
        mock_askyesno.return_value = True
        app = TimeClockApp(root=self.root, engine=self.engine)
        t1 = self.engine.create_task("Task To Archive")
        t2 = self.engine.create_task("Remaining Task")
        self.engine.select_task(t1.id)
        self.root.update_idletasks()

        self.assertEqual(app.task_panel.archive_btn.cget("text"), "Archive")

        # Archive t1 via button
        app.task_panel._on_archive_toggle_clicked()
        self.root.update_idletasks()

        self.assertTrue(t1.is_archived)
        mock_askyesno.assert_called_once()

        # Turn on show archived
        app.task_panel.show_archived_var.set(True)
        app.task_panel.refresh_task_list()
        self.root.update_idletasks()

        # Select archived task t1
        app.task_panel.tree.selection_set(t1.id)
        app.task_panel._update_archive_button_state()
        self.assertEqual(app.task_panel.archive_btn.cget("text"), "Unarchive")

        # Unarchive t1
        app.task_panel._on_archive_toggle_clicked()
        self.root.update_idletasks()

        self.assertFalse(t1.is_archived)

    def test_archiving_active_task_updates_clock_and_history_panels(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        t1 = self.engine.create_task("Task A")
        t2 = self.engine.create_task("Task B")
        self.engine.select_task(t1.id)
        self.root.update_idletasks()

        self.assertIn("Task A", app.clock_panel.task_title_var.get())
        self.assertIn("Task A", app.history_panel.cget("text"))

        # Archive Task A
        self.engine.archive_task(t1.id)
        self.root.update_idletasks()

        # Active task switched to Task B and panels updated automatically
        self.assertIn("Task B", app.clock_panel.task_title_var.get())
        self.assertIn("Task B", app.history_panel.cget("text"))

    def test_clock_panel_period_counters_display(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.root.update_idletasks()

        # Initial state: 00:00:00
        self.assertEqual(app.clock_panel.day_time_var.get(), "Day: 00:00:00")
        self.assertEqual(app.clock_panel.week_time_var.get(), "Week: 00:00:00")
        self.assertEqual(app.clock_panel.month_time_var.get(), "Month: 00:00:00")

        # Create tasks: one active, one archived
        t1 = self.engine.create_task("Project 1")
        t2 = self.engine.create_task("Project 2")

        # Add today's entries
        from datetime import datetime
        now = datetime.now()
        start_t1 = now.replace(hour=8, minute=0, second=0, microsecond=0).isoformat()
        end_t1 = now.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
        start_t2 = now.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
        end_t2 = now.replace(hour=10, minute=0, second=0, microsecond=0).isoformat()

        t1.entries.append(TimeEntry(id="e1", start_time=start_t1, end_time=end_t1, duration_seconds=3600.0))
        t2.entries.append(TimeEntry(id="e2", start_time=start_t2, end_time=end_t2, duration_seconds=3600.0))
        self.engine._save_state()

        # Archive t2
        self.engine.archive_task(t2.id)
        self.root.update_idletasks()

        # Both entries should be counted in Day, Week, and Month (2 hours = 02:00:00)
        self.assertEqual(app.clock_panel.day_time_var.get(), "Day: 02:00:00")
        self.assertEqual(app.clock_panel.week_time_var.get(), "Week: 02:00:00")
        self.assertEqual(app.clock_panel.month_time_var.get(), "Month: 02:00:00")

    def test_clock_panel_period_counters_tick_update(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        t = self.engine.create_task("Live Period Task")
        self.root.update_idletasks()

        self.engine.clock_in()
        self.root.update_idletasks()

        # Trigger tick
        self.engine.tick()
        self.root.update_idletasks()

        self.assertIn("Day:", app.clock_panel.day_time_var.get())
        self.assertIn("Week:", app.clock_panel.week_time_var.get())
        self.assertIn("Month:", app.clock_panel.month_time_var.get())


if __name__ == "__main__":
    unittest.main()
