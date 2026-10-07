"""Unit tests for Tkinter GUI panels."""
import shutil
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from time_clock.engine import TimeClockEngine
from time_clock.events import EventBus
from time_clock.gui.app import TimeClockApp
from time_clock.gui.edit_session_dialog import EditClockInOutDialog
from time_clock.gui.prompt_dialog import InputDialog, ask_string
from time_clock.gui.stats_calendar_dialog import StatsCalendarDialog
from time_clock.gui.task_options_dialog import TaskOptionsDialog, ask_task_options
from time_clock.models import TimeEntry
from time_clock.storage import SQLiteStorage
from datetime import date, timedelta


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

    def tearDown(self):
        if hasattr(self, "_toplevel_patcher"):
            self._toplevel_patcher.stop()
        if hasattr(self, "_grab_patcher"):
            self._grab_patcher.stop()
        if hasattr(self, "_lift_patcher"):
            self._lift_patcher.stop()

        if hasattr(self, "root") and self.root:
            try:
                for after_id in self.root.tk.eval("after info").split():
                    try:
                        self.root.after_cancel(after_id)
                    except Exception:
                        pass
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
        self.assertIn("paid", cols)
        self.assertIn("unreported_time", cols)

        # Check values
        item_vals = app.task_panel.tree.item(task.id, "values")
        self.assertEqual(len(item_vals), 4)
        self.assertEqual(item_vals[0], "💰")
        self.assertEqual(item_vals[1], "Column Test Task")
        self.assertEqual(item_vals[2], "00:00:00")
        self.assertEqual(item_vals[3], "00:00:00")

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

    @patch("time_clock.gui.task_panel.ask_task_options")
    def test_task_panel_dialog_add_task_success(self, mock_askoptions):
        mock_askoptions.return_value = ("Dialog Project", False)
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.root.update_idletasks()

        app.task_panel._on_add_task()
        self.root.update_idletasks()

        tasks = self.engine.get_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].name, "Dialog Project")
        self.assertFalse(tasks[0].is_unpaid)
        children = app.task_panel.tree.get_children()
        self.assertEqual(len(children), 1)
        self.assertEqual(app.task_panel.tree.item(children[0], "values")[0], "💰")
        self.assertEqual(app.task_panel.tree.item(children[0], "values")[1], "Dialog Project")

    @patch("time_clock.gui.task_panel.ask_task_options")
    def test_task_panel_dialog_add_task_cancelled(self, mock_askoptions):
        mock_askoptions.return_value = None
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.root.update_idletasks()

        app.task_panel._on_add_task()
        self.root.update_idletasks()

        tasks = self.engine.get_tasks()
        self.assertEqual(len(tasks), 0)
        self.assertEqual(len(app.task_panel.tree.get_children()), 0)

    @patch("time_clock.gui.task_panel.messagebox.showwarning")
    @patch("time_clock.gui.task_panel.ask_task_options")
    def test_task_panel_dialog_add_task_empty(self, mock_askoptions, mock_showwarning):
        mock_askoptions.return_value = ("   ", False)
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.root.update_idletasks()

        app.task_panel._on_add_task()
        self.root.update_idletasks()

        mock_showwarning.assert_called_once()
        tasks = self.engine.get_tasks()
        self.assertEqual(len(tasks), 0)

    @patch("time_clock.gui.task_panel.messagebox.showerror")
    @patch("time_clock.gui.task_panel.ask_task_options")
    def test_task_panel_dialog_add_task_error(self, mock_askoptions, mock_showerror):
        mock_askoptions.return_value = ("Error Project", False)
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
        self.assertIn("[Archived]", item_values[1])
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

    def test_advanced_menu_exists(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        menubar = self.root.nametowidget(self.root.cget("menu"))
        self.assertIsNotNone(menubar)

        # Check for Advanced cascade and its items
        found_advanced = False
        num_items = menubar.index("end") + 1
        for i in range(num_items):
            try:
                label = menubar.entrycget(i, "label")
                if label == "Advanced":
                    found_advanced = True
                    advanced_menu = menubar.nametowidget(menubar.entrycget(i, "menu"))
                    adv_labels = [
                        advanced_menu.entrycget(j, "label")
                        for j in range(advanced_menu.index("end") + 1)
                    ]
                    self.assertIn("Edit Task...", adv_labels)
                    self.assertIn("Delete Task...", adv_labels)
                    self.assertIn("Historical Time Stats...", adv_labels)
                    self.assertNotIn("Edit Task Options...", adv_labels)
                    break
            except Exception:
                pass
        self.assertTrue(found_advanced, "Advanced menu should exist on top menubar")

    def test_task_panel_no_delete_button(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        button_texts = []
        for child in app.task_panel.winfo_children():
            if isinstance(child, tk.Frame) or isinstance(child, ttk.Frame):
                for subchild in child.winfo_children():
                    if isinstance(subchild, ttk.Button):
                        button_texts.append(subchild.cget("text"))
        self.assertNotIn("Delete", button_texts)

    @patch("time_clock.gui.task_panel.messagebox.askyesno")
    def test_advanced_menu_delete_task_confirmed(self, mock_askyesno):
        mock_askyesno.return_value = True
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("Task To Delete Via Menu")
        self.engine.select_task(task.id)
        self.root.update_idletasks()

        app._delete_task()
        self.root.update_idletasks()

        mock_askyesno.assert_called_once()
        self.assertNotIn(task.id, self.engine.state.tasks)

    @patch("time_clock.gui.task_panel.messagebox.askyesno")
    def test_advanced_menu_delete_task_cancelled(self, mock_askyesno):
        mock_askyesno.return_value = False
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("Task Keep")
        self.engine.select_task(task.id)
        self.root.update_idletasks()

        app._delete_task()
        self.root.update_idletasks()

        mock_askyesno.assert_called_once()
        self.assertIn(task.id, self.engine.state.tasks)

    @patch("time_clock.gui.task_panel.messagebox.showinfo")
    def test_advanced_menu_delete_task_no_selection(self, mock_showinfo):
        app = TimeClockApp(root=self.root, engine=self.engine)
        app.task_panel.tree.selection_set([])
        self.root.update_idletasks()

        app._delete_task()
        self.root.update_idletasks()

        mock_showinfo.assert_called_once()

    @patch("time_clock.gui.edit_session_dialog.messagebox.showinfo")
    def test_edit_clock_in_out_dialog_active_session(self, mock_info):
        app = TimeClockApp(root=self.root, engine=self.engine)
        t = self.engine.create_task("Active Session Task")
        self.engine.select_task(t.id)
        self.engine.clock_in()
        self.root.update_idletasks()

        dialog = EditClockInOutDialog(parent=self.root, engine=self.engine)
        self.root.update_idletasks()

        self.assertIn("actively clocked in", dialog.active_status_lbl.cget("text"))
        self.assertEqual(str(dialog.active_apply_btn.cget("state")), "normal")

        # Change active start time
        dialog.active_start_var.set("2026-10-01 07:00:00")
        dialog._on_apply_active_start()
        self.root.update_idletasks()

        self.assertEqual(self.engine.state.current_session_start, "2026-10-01T07:00:00")
        mock_info.assert_called_once()
        dialog.destroy()

    @patch("time_clock.gui.edit_session_dialog.messagebox.showinfo")
    def test_edit_clock_in_out_dialog_past_entries(self, mock_info):
        app = TimeClockApp(root=self.root, engine=self.engine)
        t = self.engine.create_task("Past Entries Task")
        entry = self.engine.add_manual_time_entry(
            t.id, "2026-10-01T09:00:00", "2026-10-01T10:00:00"
        )
        self.root.update_idletasks()

        dialog = EditClockInOutDialog(parent=self.root, engine=self.engine)
        self.root.update_idletasks()

        children = dialog.tree.get_children()
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0], entry.id)

        # Select entry
        dialog.tree.selection_set(entry.id)
        dialog._on_tree_select()

        self.assertEqual(dialog.entry_start_var.get(), "2026-10-01 09:00:00")
        self.assertEqual(dialog.entry_end_var.get(), "2026-10-01 10:00:00")

        # Edit and save
        dialog.entry_start_var.set("2026-10-01 08:00:00")
        dialog._on_save_entry()
        self.root.update_idletasks()

        self.assertEqual(t.entries[0].duration_seconds, 7200.0)
        self.assertIn("02:00:00", app.history_panel.summary_var.get())
        dialog.destroy()

    @patch("time_clock.gui.edit_session_dialog.messagebox.showinfo")
    def test_edit_clock_in_out_dialog_add_manual_entry(self, mock_info):
        app = TimeClockApp(root=self.root, engine=self.engine)
        t = self.engine.create_task("Manual Insert Task")
        self.root.update_idletasks()

        dialog = EditClockInOutDialog(parent=self.root, engine=self.engine)
        dialog.entry_start_var.set("2026-10-01 13:00:00")
        dialog.entry_end_var.set("2026-10-01 14:15:00")
        dialog._on_add_manual_entry()
        self.root.update_idletasks()

        self.assertEqual(len(t.entries), 1)
        self.assertEqual(t.entries[0].duration_seconds, 4500.0)
        self.assertIn("01:15:00", app.history_panel.summary_var.get())
        dialog.destroy()

    @patch("time_clock.gui.edit_session_dialog.messagebox.showerror")
    def test_edit_clock_in_out_dialog_validation_errors(self, mock_error):
        app = TimeClockApp(root=self.root, engine=self.engine)
        t = self.engine.create_task("Validation Error Task")
        entry = self.engine.add_manual_time_entry(
            t.id, "2026-10-01T09:00:00", "2026-10-01T10:00:00"
        )
        dialog = EditClockInOutDialog(parent=self.root, engine=self.engine)

        # Invalid format
        dialog.tree.selection_set(entry.id)
        dialog._on_tree_select()
        dialog.entry_start_var.set("not-a-date")
        dialog._on_save_entry()
        mock_error.assert_called()

        # End time earlier than start time
        mock_error.reset_mock()
        dialog.entry_start_var.set("2026-10-01 12:00:00")
        dialog.entry_end_var.set("2026-10-01 11:00:00")
        dialog._on_save_entry()
        mock_error.assert_called()
        dialog.destroy()

    def test_edit_clock_in_out_dialog_unsubscribes_on_destroy(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        t = self.engine.create_task("Unsubscribe Task")
        self.engine.select_task(t.id)

        dialog = EditClockInOutDialog(parent=self.root, engine=self.engine)
        self.root.update_idletasks()

        # Destroy dialog
        dialog.destroy()
        self.root.update_idletasks()

        # Verify that subsequent clock operations and events do not raise TclError
        self.engine.clock_in()
        self.root.update_idletasks()

        self.engine.clock_out()
        self.root.update_idletasks()

        self.engine.add_manual_time_entry(t.id, "2026-10-01T09:00:00", "2026-10-01T10:00:00")
        self.root.update_idletasks()

    def test_app_window_configuration_centering(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.root.update_idletasks()
        geom = self.root.geometry()
        # Geometry should start with 1424x680 and have offset coordinates
        self.assertTrue(geom.startswith("1424x680"))

    @patch.object(InputDialog, "wait_window")
    def test_input_dialog_ok(self, mock_wait):
        def auto_ok(d):
            self.root.update_idletasks()
            d.entry_var.set("Created From Test")
            d._on_ok()

        mock_wait.side_effect = auto_ok
        res = ask_string("Test Dialog", "Enter text:", parent=self.root)
        self.assertEqual(res, "Created From Test")

    @patch.object(InputDialog, "wait_window")
    def test_input_dialog_cancel(self, mock_wait):
        def auto_cancel(d):
            self.root.update_idletasks()
            d._on_cancel()

        mock_wait.side_effect = auto_cancel
        res = ask_string("Test Cancel Dialog", "Enter text:", initialvalue="Default", parent=self.root)
        self.assertIsNone(res)

    @patch.object(InputDialog, "wait_window")
    def test_input_dialog_parent_relative_centering(self, mock_wait):
        with patch.object(self.root, "winfo_ismapped", return_value=1), \
                patch.object(self.root, "winfo_width", return_value=800), \
                patch.object(self.root, "winfo_height", return_value=600), \
                patch.object(self.root, "winfo_rootx", return_value=1200), \
                patch.object(self.root, "winfo_rooty", return_value=300):
            def close_dialog(d):
                self.root.update_idletasks()
                geom = d.geometry()
                self.assertTrue(geom.startswith("380x150+"))
                d._on_cancel()

            mock_wait.side_effect = close_dialog
            ask_string("Position Test", "Enter text:", parent=self.root)

    def test_app_on_close_preserves_running_timer(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("Close Window Running Task")
        self.engine.clock_in()
        self.root.update_idletasks()
        self.assertTrue(self.engine.state.is_running)

        app.on_close()
        self.assertTrue(self.engine.state.is_running)

        # Check loaded storage state
        reloaded = self.storage.load()
        self.assertTrue(reloaded.is_running)
        self.assertIsNotNone(reloaded.current_session_start)
        self.assertEqual(len(reloaded.tasks[task.id].entries), 0)

    def test_app_initialization_with_running_timer(self):
        task = self.engine.create_task("Pre-running Task")
        start_ts = self.engine.clock_in()

        # Initialize UI when engine is already running
        app = TimeClockApp(root=self.root, engine=self.engine)
        self.root.update_idletasks()

        self.assertIn("Clocked In", app.clock_panel.status_var.get())
        self.assertEqual(app.clock_panel.toggle_btn.cget("text"), "Clock Out")
        self.assertIn(start_ts.split(".")[0].replace("T", " "), app.clock_panel.start_time_var.get())

        app._on_tick()
        self.root.update_idletasks()
        self.assertIn("Clocked In", app.clock_panel.status_var.get())

    @patch.object(TaskOptionsDialog, "wait_window")
    def test_task_options_dialog_ok(self, mock_wait):
        def auto_ok(d):
            self.root.update_idletasks()
            d.name_var.set("Created Unpaid Task")
            d.is_unpaid_var.set(True)
            d._on_ok()

        mock_wait.side_effect = auto_ok
        res = ask_task_options("New Task", initial_name="", initial_is_unpaid=False, parent=self.root)
        self.assertEqual(res, ("Created Unpaid Task", True))

    @patch.object(TaskOptionsDialog, "wait_window")
    def test_task_options_dialog_cancel(self, mock_wait):
        def auto_cancel(d):
            self.root.update_idletasks()
            d._on_cancel()

        mock_wait.side_effect = auto_cancel
        res = ask_task_options("New Task", initial_name="Something", initial_is_unpaid=False, parent=self.root)
        self.assertIsNone(res)

    @patch("time_clock.gui.task_panel.EditClockInOutDialog")
    def test_task_panel_edit_options(self, mock_dialog_cls):
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("Original Task", is_unpaid=False)
        self.engine.select_task(task.id)
        self.root.update_idletasks()

        app.task_panel._on_edit_options()
        self.root.update_idletasks()

        mock_dialog_cls.assert_called_once_with(
            parent=app.task_panel.winfo_toplevel(),
            engine=self.engine,
            initial_task_id=task.id,
        )

    def test_unpaid_task_display_in_panels(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        unpaid_task = self.engine.create_task("Internal Sync", is_unpaid=True)
        self.engine.select_task(unpaid_task.id)
        self.engine.add_manual_time_entry(unpaid_task.id, "2026-10-01T09:00:00", "2026-10-01T10:00:00")
        self.root.update_idletasks()

        # TaskPanel tree check
        item_vals = app.task_panel.tree.item(unpaid_task.id, "values")
        self.assertEqual(item_vals[0], "")
        self.assertIn("Internal Sync [Unpaid]", item_vals[1])
        self.assertEqual(item_vals[2], "01:00:00")
        self.assertEqual(item_vals[3], "00:00:00")
        self.assertEqual(app.task_panel.tree.item(unpaid_task.id, "tags"), ("unpaid",))
        self.assertEqual(str(app.task_panel.report_btn.cget("state")), "disabled")

        # ClockPanel title & buttons check
        self.assertEqual(app.clock_panel.task_title_var.get(), "Active Task: Internal Sync [Unpaid]")
        self.assertEqual(str(app.clock_panel.report_btn.cget("state")), "disabled")
        self.assertEqual(app.clock_panel.last_reported_var.get(), "Last Reported: N/A (Unpaid Task)")
        self.assertIn("(Unpaid)", app.clock_panel.unreported_time_var.get())

        # HistoryPanel check
        self.assertIn("[Unpaid]", app.history_panel.cget("text"))
        self.assertIn("(Unpaid)", app.history_panel.summary_var.get())

        # EditClockInOutDialog combobox check
        dialog = EditClockInOutDialog(parent=self.root, engine=self.engine)
        self.root.update_idletasks()
        self.assertIn("Internal Sync [Unpaid]", dialog.task_cb["values"])
        dialog.destroy()

    @patch("time_clock.gui.task_panel.TaskPanel._on_edit_options")
    def test_app_advanced_menu_edit_task_options(self, mock_on_edit_options):
        app = TimeClockApp(root=self.root, engine=self.engine)
        app._edit_task_options()
        mock_on_edit_options.assert_called_once()

    def test_report_button_disabled_for_unpaid_and_enabled_for_paid(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        paid_task = self.engine.create_task("Paid Client Task", is_unpaid=False)
        unpaid_task = self.engine.create_task("Internal Admin Task", is_unpaid=True)

        # Select paid task -> report buttons enabled
        self.engine.select_task(paid_task.id)
        self.root.update_idletasks()
        self.assertEqual(str(app.task_panel.report_btn.cget("state")), "normal")
        self.assertEqual(str(app.clock_panel.report_btn.cget("state")), "normal")

        # Select unpaid task -> report buttons disabled
        self.engine.select_task(unpaid_task.id)
        self.root.update_idletasks()
        self.assertEqual(str(app.task_panel.report_btn.cget("state")), "disabled")
        self.assertEqual(str(app.clock_panel.report_btn.cget("state")), "disabled")

        # Select paid task again -> report buttons re-enabled
        self.engine.select_task(paid_task.id)
        self.root.update_idletasks()
        self.assertEqual(str(app.task_panel.report_btn.cget("state")), "normal")
        self.assertEqual(str(app.clock_panel.report_btn.cget("state")), "normal")

    def test_unpaid_task_mark_reported_guards(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        unpaid_task = self.engine.create_task("Unpaid Guard Task", is_unpaid=True)
        self.engine.select_task(unpaid_task.id)
        self.root.update_idletasks()

        # Attempt to mark reported through panel actions on unpaid task
        app.task_panel._mark_reported_now(unpaid_task.id)
        self.assertIsNone(unpaid_task.last_reported_at)

        app.clock_panel._mark_reported_now()
        self.assertIsNone(unpaid_task.last_reported_at)

        app.task_panel._clear_reported_status(unpaid_task.id)
        self.assertIsNone(unpaid_task.last_reported_at)

    @patch.object(TaskOptionsDialog, "wait_window")
    def test_task_options_dialog_dimensions(self, mock_wait):
        with patch.object(self.root, "winfo_ismapped", return_value=1), \
                patch.object(self.root, "winfo_width", return_value=800), \
                patch.object(self.root, "winfo_height", return_value=600), \
                patch.object(self.root, "winfo_rootx", return_value=100), \
                patch.object(self.root, "winfo_rooty", return_value=100):
            def inspect_and_close(d):
                self.root.update_idletasks()
                geom = d.geometry()
                self.assertTrue(geom.startswith("420x280+") or "x" in geom)
                d._on_cancel()

            mock_wait.side_effect = inspect_and_close
            ask_task_options(
                "Dialog Dimensions Test",
                initial_name="Dimension Check",
                initial_is_unpaid=True,
                parent=self.root,
            )

    def test_task_panel_paid_and_unpaid_emoji_column(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        paid_task = self.engine.create_task("Paid Client Feature", is_unpaid=False)
        unpaid_task = self.engine.create_task("Internal Maintenance", is_unpaid=True)
        self.root.update_idletasks()

        paid_vals = app.task_panel.tree.item(paid_task.id, "values")
        self.assertEqual(paid_vals[0], "💰")
        self.assertIn("Paid Client Feature", paid_vals[1])

        unpaid_vals = app.task_panel.tree.item(unpaid_task.id, "values")
        self.assertEqual(unpaid_vals[0], "")
        self.assertIn("Internal Maintenance [Unpaid]", unpaid_vals[1])

        # Toggle paid to unpaid
        self.engine.update_task_options(paid_task.id, is_unpaid=True)
        self.root.update_idletasks()
        paid_vals = app.task_panel.tree.item(paid_task.id, "values")
        self.assertEqual(paid_vals[0], "")
        self.assertIn("[Unpaid]", paid_vals[1])

        # Toggle unpaid to paid
        self.engine.update_task_options(unpaid_task.id, is_unpaid=False)
        self.root.update_idletasks()
        unpaid_vals = app.task_panel.tree.item(unpaid_task.id, "values")
        self.assertEqual(unpaid_vals[0], "💰")
        self.assertNotIn("[Unpaid]", unpaid_vals[1])

    @patch("time_clock.gui.edit_session_dialog.messagebox.showwarning")
    @patch("time_clock.gui.edit_session_dialog.messagebox.showinfo")
    def test_unified_dialog_edit_task_options_and_switching(self, mock_info, mock_warn):
        t1 = self.engine.create_task("Initial Task One", is_unpaid=False)
        t2 = self.engine.create_task("Initial Task Two", is_unpaid=True)
        self.root.update_idletasks()

        dialog = EditClockInOutDialog(parent=self.root, engine=self.engine, initial_task_id=t1.id)
        self.root.update_idletasks()

        # Check initial values in dialog for t1
        self.assertEqual(dialog.task_name_var.get(), "Initial Task One")
        self.assertFalse(dialog.is_unpaid_var.get())

        # Modify options for t1 and save
        dialog.task_name_var.set("Updated Task One")
        dialog.is_unpaid_var.set(True)
        dialog._on_save_task_options()
        self.root.update_idletasks()
        mock_info.assert_called_once()

        # Verify engine state was updated
        self.assertEqual(self.engine.get_task(t1.id).name, "Updated Task One")
        self.assertTrue(self.engine.get_task(t1.id).is_unpaid)

        # Test switching to t2 in combobox
        dialog.task_cb.current(1)
        dialog._on_task_selected()
        self.root.update_idletasks()

        self.assertEqual(dialog.selected_task_id, t2.id)
        self.assertEqual(dialog.task_name_var.get(), "Initial Task Two")
        self.assertTrue(dialog.is_unpaid_var.get())

        # Test empty task name validation
        dialog.task_name_var.set("   ")
        dialog._on_save_task_options()
        mock_warn.assert_called_once()
        self.assertEqual(self.engine.get_task(t2.id).name, "Initial Task Two")

        dialog.destroy()

    def test_stats_calendar_dialog_initialization_and_default_stats(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        dialog = StatsCalendarDialog(parent=self.root, engine=self.engine)
        self.root.update_idletasks()

        today = date.today()
        self.assertEqual(dialog.selected_date, today)
        self.assertIn(today.strftime("%Y-%m-%d"), dialog.selected_date_var.get())
        self.assertIn("Daily:", dialog.day_var.get())
        self.assertIn("Weekly:", dialog.week_var.get())
        self.assertIn("Monthly:", dialog.month_var.get())
        dialog.destroy()

    def test_stats_calendar_dialog_navigation(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        dialog = StatsCalendarDialog(parent=self.root, engine=self.engine)
        self.root.update_idletasks()

        orig_month = dialog.current_month
        orig_year = dialog.current_year

        # Previous month
        dialog._prev_month()
        self.root.update_idletasks()
        expected_prev_month = 12 if orig_month == 1 else orig_month - 1
        expected_prev_year = orig_year - 1 if orig_month == 1 else orig_year
        self.assertEqual(dialog.current_month, expected_prev_month)
        self.assertEqual(dialog.current_year, expected_prev_year)

        # Next month (back to original)
        dialog._next_month()
        self.root.update_idletasks()
        self.assertEqual(dialog.current_month, orig_month)
        self.assertEqual(dialog.current_year, orig_year)
        dialog.destroy()

    def test_stats_calendar_dialog_past_date_selection_updates_stats(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        task = self.engine.create_task("Historical Task")
        # Add past entry on 2026-05-15
        self.engine.add_manual_time_entry(
            task.id, "2026-05-15T10:00:00", "2026-05-15T12:00:00"
        )
        self.root.update_idletasks()

        dialog = StatsCalendarDialog(parent=self.root, engine=self.engine)
        past_date = date(2026, 5, 15)
        dialog._select_date(past_date)
        self.root.update_idletasks()

        self.assertEqual(dialog.selected_date, past_date)
        self.assertEqual(dialog.day_var.get(), "Daily: 02:00:00")
        self.assertEqual(dialog.week_var.get(), "Weekly: 02:00:00")
        self.assertEqual(dialog.month_var.get(), "Monthly: 02:00:00")
        dialog.destroy()

    def test_stats_calendar_dialog_future_dates_prevented(self):
        app = TimeClockApp(root=self.root, engine=self.engine)
        dialog = StatsCalendarDialog(parent=self.root, engine=self.engine)
        self.root.update_idletasks()

        today = date.today()
        future_date = today + timedelta(days=10)

        # Attempt selecting future date
        dialog._select_date(future_date)
        self.root.update_idletasks()

        # Date should remain today
        self.assertEqual(dialog.selected_date, today)

        # In current month view, verify future day buttons have disabled state
        dialog.current_year = future_date.year
        dialog.current_month = future_date.month
        dialog._render_calendar()
        self.root.update_idletasks()

        if future_date.day in dialog._day_buttons:
            btn = dialog._day_buttons[future_date.day]
            self.assertEqual(str(btn.cget("state")), "disabled")

        dialog.destroy()

    @patch("time_clock.gui.app.StatsCalendarDialog")
    def test_app_open_stats_calendar(self, mock_dialog):
        app = TimeClockApp(root=self.root, engine=self.engine)
        app._open_stats_calendar()
        mock_dialog.assert_called_once_with(parent=self.root, engine=self.engine)


if __name__ == "__main__":
    unittest.main()
