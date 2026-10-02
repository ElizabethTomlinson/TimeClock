"""Task session history UI panel."""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from time_clock.engine import TimeClockEngine
from time_clock.events import Event, EventType
from time_clock.models import Task, format_duration, parse_iso

logger = logging.getLogger(__name__)


class HistoryPanel(ttk.LabelFrame):
    """Panel displaying historical session logs for the selected task."""

    def __init__(self, parent: tk.Widget, engine: TimeClockEngine) -> None:
        super().__init__(parent, text="Session History", padding=10)
        self.engine = engine

        self._build_ui()
        self._register_events()
        self.refresh_history()

    def _build_ui(self) -> None:
        # History Table / Treeview
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("index", "start", "end", "duration")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=6
        )

        self.tree.heading("index", text="#")
        self.tree.heading("start", text="Start Time")
        self.tree.heading("end", text="End Time")
        self.tree.heading("duration", text="Duration")

        self.tree.column("index", width=35, anchor=tk.CENTER)
        self.tree.column("start", width=145, anchor=tk.W)
        self.tree.column("end", width=145, anchor=tk.W)
        self.tree.column("duration", width=80, anchor=tk.E)

        self.tree.tag_configure("reported", foreground="#888888")
        self.tree.tag_configure("unreported", foreground="")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Footer frame with summary and export button
        footer_frame = ttk.Frame(self)
        footer_frame.pack(fill=tk.X, pady=(6, 0))

        self.export_btn = ttk.Button(
            footer_frame,
            text="Export...",
            width=10,
            command=self._on_export_clicked,
        )
        self.export_btn.pack(side=tk.LEFT)

        self.summary_var = tk.StringVar(value="Sessions: 0 | Total: 00:00:00 | Unreported: 00:00:00")
        summary_lbl = ttk.Label(
            footer_frame,
            textvariable=self.summary_var,
            font=("Helvetica", 9, "italic"),
            anchor=tk.E,
        )
        summary_lbl.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def _on_export_clicked(self) -> Optional[str]:
        """Trigger file export dialog for current task session history."""
        file_path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(),
            title="Export Session History",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile="session_history.csv",
        )
        if not file_path:
            return None

        fmt = "json" if file_path.lower().endswith(".json") else "csv"
        active_task = self.engine.get_active_task()
        task_id = active_task.id if active_task else None

        try:
            self.engine.export_data(file_path=file_path, format=fmt, task_id=task_id)
            messagebox.showinfo(
                "Export Successful",
                f"Session history successfully exported to:\n{file_path}",
                parent=self.winfo_toplevel(),
            )
            return file_path
        except Exception as e:
            logger.exception("Failed to export session history: %s", e)
            messagebox.showerror(
                "Export Failed",
                f"Could not export session history:\n{e}",
                parent=self.winfo_toplevel(),
            )
            return None

    def _register_events(self) -> None:
        self.engine.event_bus.subscribe(EventType.TASK_CREATED, self._on_task_created_event)
        self.engine.event_bus.subscribe(EventType.TASK_ARCHIVED, self._on_task_archived_event)
        self.engine.event_bus.subscribe(EventType.TASK_UNARCHIVED, self._on_task_unarchived_event)
        self.engine.event_bus.subscribe(EventType.CLOCK_OUT, self._on_clock_out_event)
        self.engine.event_bus.subscribe(EventType.TASK_SELECTED, self._on_task_selected_event)
        self.engine.event_bus.subscribe(EventType.TASK_DELETED, self._on_task_deleted_event)
        self.engine.event_bus.subscribe(EventType.TASK_RENAMED, self._on_task_renamed_event)
        self.engine.event_bus.subscribe(EventType.TASK_REPORTED, self._on_task_reported_event)
        self.engine.event_bus.subscribe(EventType.ENTRY_UPDATED, self._on_entry_updated_event)
        self.engine.event_bus.subscribe(EventType.STATE_LOADED, self._on_state_loaded_event)

    def refresh_history(self) -> None:
        """Reload historical entries for currently active task."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        active_task = self.engine.get_active_task()
        if not active_task:
            self.configure(text="Session History (No Task Selected)")
            self.summary_var.set("Sessions: 0 | Total: 00:00:00 | Unreported: 00:00:00")
            return

        self.configure(text=f"Session History - {active_task.name}")
        entries = active_task.entries

        cutoff_dt = parse_iso(active_task.last_reported_at) if active_task.last_reported_at else None

        for idx, entry in enumerate(entries, start=1):
            start_str = entry.start_time.split(".")[0].replace("T", " ")
            end_str = (entry.end_time or "--").split(".")[0].replace("T", " ")
            dur_str = format_duration(entry.duration_seconds)

            tag = "unreported"
            if cutoff_dt and entry.end_time:
                try:
                    if parse_iso(entry.end_time) <= cutoff_dt:
                        tag = "reported"
                except Exception:
                    pass

            self.tree.insert("", tk.END, values=(idx, start_str, end_str, dur_str), tags=(tag,))

        total_str = format_duration(active_task.total_duration_seconds)
        unrep_str = format_duration(active_task.calculate_unreported_duration())
        self.summary_var.set(f"Sessions: {len(entries)} | Total: {total_str} | Unreported: {unrep_str}")

    def _on_task_created_event(self, event: Event) -> None:
        self.refresh_history()

    def _on_task_archived_event(self, event: Event) -> None:
        self.refresh_history()

    def _on_task_unarchived_event(self, event: Event) -> None:
        self.refresh_history()

    def _on_clock_out_event(self, event: Event) -> None:
        self.refresh_history()

    def _on_task_selected_event(self, event: Event) -> None:
        self.refresh_history()

    def _on_task_deleted_event(self, event: Event) -> None:
        self.refresh_history()

    def _on_task_renamed_event(self, event: Event) -> None:
        self.refresh_history()

    def _on_task_reported_event(self, event: Event) -> None:
        self.refresh_history()

    def _on_entry_updated_event(self, event: Event) -> None:
        self.refresh_history()

    def _on_state_loaded_event(self, event: Event) -> None:
        self.refresh_history()
