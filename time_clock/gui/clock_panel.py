"""Clock in/out controls and digital stopwatch display UI panel."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Optional

from time_clock.engine import TimeClockEngine
from time_clock.events import Event, EventType
from time_clock.models import Task, format_duration, iso_now, parse_iso


class ClockPanel(ttk.LabelFrame):
    """Panel featuring live timer, start timestamps, status indicators, and clock in/out action."""

    def __init__(self, parent: tk.Widget, engine: TimeClockEngine) -> None:
        super().__init__(parent, text="Clock Tracker", padding=15)
        self.engine = engine

        self._build_ui()
        self._register_events()
        self.refresh_display()

    def _build_ui(self) -> None:
        # Active Task Label
        self.task_title_var = tk.StringVar(value="No Task Selected")
        task_label = ttk.Label(
            self,
            textvariable=self.task_title_var,
            font=("Helvetica", 14, "bold"),
            anchor=tk.CENTER
        )
        task_label.pack(fill=tk.X, pady=(0, 5))

        # Status Label (Clocked In / Clocked Out)
        self.status_var = tk.StringVar(value="Status: Idle (Clocked Out)")
        self.status_label = ttk.Label(
            self,
            textvariable=self.status_var,
            font=("Helvetica", 11),
            anchor=tk.CENTER
        )
        self.status_label.pack(fill=tk.X, pady=(0, 5))

        # Start Time Label
        self.start_time_var = tk.StringVar(value="Start Time: --")
        start_time_lbl = ttk.Label(
            self,
            textvariable=self.start_time_var,
            font=("Helvetica", 10),
            anchor=tk.CENTER
        )
        start_time_lbl.pack(fill=tk.X, pady=(0, 10))

        # Large Digital Elapsed Stopwatch Display
        self.timer_var = tk.StringVar(value="00:00:00")
        timer_lbl = ttk.Label(
            self,
            textvariable=self.timer_var,
            font=("Helvetica", 32, "bold"),
            anchor=tk.CENTER
        )
        timer_lbl.pack(fill=tk.X, pady=(5, 10))

        # Unreported Time Spent Label
        self.unreported_time_var = tk.StringVar(value="Unreported Time: 00:00:00")
        unreported_time_lbl = ttk.Label(
            self,
            textvariable=self.unreported_time_var,
            font=("Helvetica", 11, "bold"),
            anchor=tk.CENTER
        )
        unreported_time_lbl.pack(fill=tk.X, pady=(0, 3))

        # Total Time Spent Label
        self.total_time_var = tk.StringVar(value="Total Time: 00:00:00")
        total_time_lbl = ttk.Label(
            self,
            textvariable=self.total_time_var,
            font=("Helvetica", 10),
            anchor=tk.CENTER
        )
        total_time_lbl.pack(fill=tk.X, pady=(0, 3))

        # Last Reported Timestamp Label
        self.last_reported_var = tk.StringVar(value="Last Reported: Never")
        last_reported_lbl = ttk.Label(
            self,
            textvariable=self.last_reported_var,
            font=("Helvetica", 9, "italic"),
            anchor=tk.CENTER
        )
        last_reported_lbl.pack(fill=tk.X, pady=(0, 10))

        # All Tasks Period Summary Section
        period_frame = ttk.LabelFrame(self, text="All Tasks Summary", padding=6)
        period_frame.pack(fill=tk.X, pady=(0, 12))

        period_cols = ttk.Frame(period_frame)
        period_cols.pack(fill=tk.X, expand=True)

        self.day_time_var = tk.StringVar(value="Day: 00:00:00")
        self.week_time_var = tk.StringVar(value="Week: 00:00:00")
        self.month_time_var = tk.StringVar(value="Month: 00:00:00")

        self.day_label = ttk.Label(
            period_cols,
            textvariable=self.day_time_var,
            font=("Helvetica", 10, "bold"),
            anchor=tk.CENTER,
        )
        self.day_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.week_label = ttk.Label(
            period_cols,
            textvariable=self.week_time_var,
            font=("Helvetica", 10, "bold"),
            anchor=tk.CENTER,
        )
        self.week_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.month_label = ttk.Label(
            period_cols,
            textvariable=self.month_time_var,
            font=("Helvetica", 10, "bold"),
            anchor=tk.CENTER,
        )
        self.month_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Action Buttons Section
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=(0, 0))

        # Primary Clock In / Clock Out Button
        self.toggle_btn = ttk.Button(
            btn_frame,
            text="Clock In",
            command=self._on_toggle_clock,
            style="Accent.TButton" if "Accent.TButton" in ttk.Style().theme_names() else "TButton"
        )
        self.toggle_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=6)

        # Mark Reported Button
        self.report_btn = ttk.Button(
            btn_frame,
            text="Mark Reported",
            command=self._on_mark_reported_menu,
        )
        self.report_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, ipady=6)

    def _register_events(self) -> None:
        self.engine.event_bus.subscribe(EventType.TASK_CREATED, self._on_task_created_event)
        self.engine.event_bus.subscribe(EventType.TASK_ARCHIVED, self._on_task_archived_event)
        self.engine.event_bus.subscribe(EventType.TASK_UNARCHIVED, self._on_task_unarchived_event)
        self.engine.event_bus.subscribe(EventType.CLOCK_IN, self._on_clock_in_event)
        self.engine.event_bus.subscribe(EventType.CLOCK_OUT, self._on_clock_out_event)
        self.engine.event_bus.subscribe(EventType.TASK_SELECTED, self._on_task_selected_event)
        self.engine.event_bus.subscribe(EventType.TASK_DELETED, self._on_task_deleted_event)
        self.engine.event_bus.subscribe(EventType.TASK_RENAMED, self._on_task_renamed_event)
        self.engine.event_bus.subscribe(EventType.TASK_REPORTED, self._on_task_reported_event)
        self.engine.event_bus.subscribe(EventType.TICK, self._on_tick_event)
        self.engine.event_bus.subscribe(EventType.STATE_LOADED, self._on_state_loaded_event)

    def _on_toggle_clock(self) -> None:
        if not self.engine.get_active_task():
            messagebox.showinfo("Select Task", "Please select or create a task before clocking in.")
            return

        try:
            if self.engine.state.is_running:
                self.engine.clock_out()
            else:
                self.engine.clock_in()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_mark_reported_menu(self) -> None:
        active_task = self.engine.get_active_task()
        if not active_task:
            messagebox.showinfo("Select Task", "Please select or create a task first.")
            return

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Mark as Reported Now", command=self._mark_reported_now)
        menu.add_command(label="Custom Timestamp...", command=self._mark_reported_custom)
        menu.add_command(label="Clear Reported Status", command=self._clear_reported_status)

        try:
            x = self.report_btn.winfo_rootx()
            y = self.report_btn.winfo_rooty() + self.report_btn.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _mark_reported_now(self) -> None:
        active_task = self.engine.get_active_task()
        if active_task:
            try:
                self.engine.mark_task_reported(active_task.id)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _mark_reported_custom(self) -> None:
        active_task = self.engine.get_active_task()
        if not active_task:
            return

        initial = active_task.last_reported_at or iso_now()
        ts = simpledialog.askstring(
            "Reported Cutoff Timestamp",
            "Enter ISO-8601 timestamp (e.g. 2026-10-01T09:00:00):",
            initialvalue=initial,
        )
        if ts and ts.strip():
            clean_ts = ts.strip()
            try:
                parse_iso(clean_ts)
            except Exception:
                messagebox.showerror(
                    "Invalid Timestamp",
                    f"'{clean_ts}' is not a valid ISO timestamp format.\nExample: 2026-10-01T09:00:00",
                )
                return
            try:
                self.engine.mark_task_reported(active_task.id, clean_ts)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _clear_reported_status(self) -> None:
        active_task = self.engine.get_active_task()
        if active_task:
            try:
                self.engine.clear_task_reported(active_task.id)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def refresh_display(self) -> None:
        """Update all labels and buttons based on current engine state."""
        active_task = self.engine.get_active_task()
        if active_task:
            self.task_title_var.set(f"Active Task: {active_task.name}")
            self.toggle_btn.configure(state=tk.NORMAL)
            self.report_btn.configure(state=tk.NORMAL)
            total_duration = active_task.total_duration_seconds
            unreported_duration = self.engine.get_task_unreported_duration(
                active_task.id, include_running=self.engine.state.is_running
            )
            if active_task.last_reported_at:
                lr_display = active_task.last_reported_at.split(".")[0].replace("T", " ")
                self.last_reported_var.set(f"Last Reported: {lr_display}")
            else:
                self.last_reported_var.set("Last Reported: Never")
        else:
            self.task_title_var.set("No Task Selected")
            self.toggle_btn.configure(state=tk.DISABLED)
            self.report_btn.configure(state=tk.DISABLED)
            total_duration = 0.0
            unreported_duration = 0.0
            self.last_reported_var.set("Last Reported: Never")

        if self.engine.state.is_running:
            self.status_var.set("● Clocked In (Running)")
            self.toggle_btn.configure(text="Clock Out")
            start_display = (self.engine.state.current_session_start or "--").split(".")[0].replace("T", " ")
            self.start_time_var.set(f"Start Time: {start_display}")
            session_dur = self.engine.get_current_session_duration()
            self.timer_var.set(format_duration(session_dur))
            self.total_time_var.set(f"Total Time: {format_duration(total_duration + session_dur)}")
            self.unreported_time_var.set(f"Unreported Time: {format_duration(unreported_duration)}")
        else:
            self.status_var.set("○ Idle (Clocked Out)")
            self.toggle_btn.configure(text="Clock In")
            self.start_time_var.set("Start Time: --")
            self.timer_var.set("00:00:00")
            self.total_time_var.set(f"Total Time: {format_duration(total_duration)}")
            self.unreported_time_var.set(f"Unreported Time: {format_duration(unreported_duration)}")

        periods = self.engine.get_period_durations(include_running=self.engine.state.is_running)
        self.day_time_var.set(f"Day: {format_duration(periods['day'])}")
        self.week_time_var.set(f"Week: {format_duration(periods['week'])}")
        self.month_time_var.set(f"Month: {format_duration(periods['month'])}")

    def _on_task_created_event(self, event: Event) -> None:
        self.refresh_display()

    def _on_task_archived_event(self, event: Event) -> None:
        self.refresh_display()

    def _on_task_unarchived_event(self, event: Event) -> None:
        self.refresh_display()

    def _on_clock_in_event(self, event: Event) -> None:
        self.refresh_display()

    def _on_clock_out_event(self, event: Event) -> None:
        self.refresh_display()

    def _on_task_selected_event(self, event: Event) -> None:
        self.refresh_display()

    def _on_task_deleted_event(self, event: Event) -> None:
        self.refresh_display()

    def _on_task_renamed_event(self, event: Event) -> None:
        self.refresh_display()

    def _on_task_reported_event(self, event: Event) -> None:
        self.refresh_display()

    def _on_state_loaded_event(self, event: Event) -> None:
        self.refresh_display()

    def _on_tick_event(self, event: Event) -> None:
        data = event.data
        if not data:
            return
        if data.get("is_running"):
            self.timer_var.set(data.get("session_duration_formatted", "00:00:00"))
            self.total_time_var.set(f"Total Time: {data.get('total_duration_formatted', '00:00:00')}")
            self.unreported_time_var.set(f"Unreported Time: {data.get('unreported_duration_formatted', '00:00:00')}")
        if "day_duration_formatted" in data:
            self.day_time_var.set(f"Day: {data.get('day_duration_formatted', '00:00:00')}")
        if "week_duration_formatted" in data:
            self.week_time_var.set(f"Week: {data.get('week_duration_formatted', '00:00:00')}")
        if "month_duration_formatted" in data:
            self.month_time_var.set(f"Month: {data.get('month_duration_formatted', '00:00:00')}")
