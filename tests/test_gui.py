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


if __name__ == "__main__":
    unittest.main()
