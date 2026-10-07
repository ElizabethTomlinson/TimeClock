"""Main TimeClock application window and UI coordinator."""
from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from time_clock.engine import TimeClockEngine
from time_clock.events import EventBus
from time_clock.gui.clock_panel import ClockPanel
from time_clock.gui.edit_session_dialog import EditClockInOutDialog
from time_clock.gui.history_panel import HistoryPanel
from time_clock.gui.stats_calendar_dialog import StatsCalendarDialog
from time_clock.gui.task_panel import TaskPanel
from time_clock.storage import Storage

logger = logging.getLogger(__name__)


class TimeClockApp:
    """Main application window for the Time Clock."""

    def __init__(
            self,
            root: Optional[tk.Tk] = None,
            engine: Optional[TimeClockEngine] = None,
            storage: Optional[Storage] = None,
            event_bus: Optional[EventBus] = None,
    ) -> None:
        self.root = root or tk.Tk()
        self._owns_root = root is None
        self.engine = engine or TimeClockEngine(storage=storage, event_bus=event_bus)
        self.storage = storage or self.engine.storage
        self._after_id: Optional[str] = None

        self._configure_window()
        self._setup_styles()
        self._build_menu()
        self._build_layout()
        self._setup_lifecycle()

    def _configure_window(self) -> None:
        self.root.title("Time Clock")
        width = 1424
        height = 680
        self.root.minsize(820, 520)
        self.root.update_idletasks()
        try:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = max(0, (screen_width - width) // 2)
            y = max(0, (screen_height - height) // 2)
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            self.root.geometry(f"{width}x{height}")
        self._set_app_icon()

    def _set_app_icon(self) -> None:
        """Attempt to set the application window/dock icon if asset exists."""
        candidate_paths = [
            Path(__file__).resolve().parent.parent.parent / "assets" / "icon.png",
            Path(__file__).resolve().parent.parent.parent / "assets" / "AppIcon_1024.png",
            Path(__file__).resolve().parent.parent / "assets" / "icon.png",
            Path("assets/icon.png").resolve(),
        ]
        for icon_path in candidate_paths:
            if icon_path.exists():
                try:
                    self._icon_image = tk.PhotoImage(file=str(icon_path))
                    self.root.iconphoto(True, self._icon_image)
                    break
                except Exception as e:
                    logger.debug("Could not set window icon from %s: %s", icon_path, e)

    def _setup_styles(self) -> None:
        self.style = ttk.Style(self.root)
        available_themes = self.style.theme_names()
        if "aqua" in available_themes:
            self.style.theme_use("aqua")
        elif "clam" in available_themes:
            self.style.theme_use("clam")

    def _build_menu(self) -> None:
        """Create the top menu bar with File operations and Advanced tools."""
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(
            label="Export Data as CSV...",
            command=self._export_as_csv,
            underline=15,
        )
        file_menu.add_command(
            label="Export Data as JSON...",
            command=self._export_as_json,
            underline=15,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Exit",
            command=self.on_close,
            underline=1,
        )

        menubar.add_cascade(label="File", menu=file_menu, underline=0)

        advanced_menu = tk.Menu(menubar, tearoff=False)
        advanced_menu.add_command(
            label="Edit Task...",
            command=self._open_edit_clock_in_out,
            underline=0,
        )
        advanced_menu.add_command(
            label="Delete Task...",
            command=self._delete_task,
            underline=0,
        )

        advanced_menu.add_command(
            label="Historical Time Stats...",
            command=self._open_stats_calendar,
            underline=0,
        )
        menubar.add_cascade(label="Advanced", menu=advanced_menu, underline=0)

        self.root.config(menu=menubar)

    def _open_edit_clock_in_out(self) -> None:
        """Open the modal dialog for editing clock in/out times and sessions."""
        active_id = None
        if hasattr(self, "task_panel") and self.task_panel:
            selection = self.task_panel.tree.selection()
            if selection:
                active_id = selection[0]
            elif self.engine.state.active_task_id:
                active_id = self.engine.state.active_task_id
        EditClockInOutDialog(parent=self.root, engine=self.engine, initial_task_id=active_id)

    def _edit_task_options(self) -> None:
        """Prompt user to edit options (name, paid/unpaid status) for the selected or active task."""
        if hasattr(self, "task_panel") and self.task_panel:
            self.task_panel._on_edit_options()

    def _delete_task(self) -> None:
        """Prompt user to delete the currently selected task."""
        if hasattr(self, "task_panel") and self.task_panel:
            self.task_panel._on_delete_task()

    def _export_as_csv(self) -> None:
        """Prompt user for file location and export full tracking data as CSV."""
        self.prompt_export("csv")

    def _export_as_json(self) -> None:
        """Prompt user for file location and export full tracking data as JSON."""
        self.prompt_export("json")

    def prompt_export(self, format_type: str) -> Optional[str]:
        """Display save file dialog and export application tracking data."""
        fmt = format_type.lower()
        if fmt == "csv":
            file_path = filedialog.asksaveasfilename(
                parent=self.root,
                title="Export Data as CSV",
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
                initialfile="time_clock_export.csv",
            )
        elif fmt == "json":
            file_path = filedialog.asksaveasfilename(
                parent=self.root,
                title="Export Data as JSON",
                defaultextension=".json",
                filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
                initialfile="time_clock_export.json",
            )
        else:
            return None

        if not file_path:
            return None

        try:
            self.engine.export_data(file_path=file_path, format=fmt)
            messagebox.showinfo(
                "Export Successful",
                f"Data successfully exported to:\n{file_path}",
                parent=self.root,
            )
            return file_path
        except Exception as e:
            logger.exception("Failed to export data: %s", e)
            messagebox.showerror(
                "Export Failed",
                f"Could not export data:\n{e}",
                parent=self.root,
            )
            return None

    def _build_layout(self) -> None:
        main_container = ttk.Frame(self.root, padding=12)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left Column: TaskPanel
        self.task_panel = TaskPanel(main_container, self.engine)
        self.task_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # Right Column: ClockPanel & HistoryPanel
        right_container = ttk.Frame(main_container)
        right_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

        self.clock_panel = ClockPanel(right_container, self.engine)
        self.clock_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=False, pady=(0, 8))

        self.history_panel = HistoryPanel(right_container, self.engine)
        self.history_panel.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

    def _setup_lifecycle(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._schedule_tick()

    def _schedule_tick(self) -> None:
        self._on_tick()
        self._after_id = self.root.after(1000, self._schedule_tick)

    def _on_tick(self) -> None:
        try:
            self.engine.tick()
        except Exception as e:
            logger.exception("Error in timer tick: %s", e)

    def on_close(self) -> None:
        """Handle window closing cleanly by stopping UI tick timers and closing storage."""
        if self._after_id:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

        try:
            if hasattr(self, "storage") and self.storage:
                self.storage.close()
        except Exception as e:
            logger.warning("Error closing storage on app exit: %s", e)

        self.root.destroy()

    def _open_stats_calendar(self) -> None:
        """Open the modal dialog for viewing historical time statistics via calendar."""

        StatsCalendarDialog(parent=self.root, engine=self.engine)

    def run(self) -> None:
        """Start the Tkinter event loop."""
        self.root.mainloop()
