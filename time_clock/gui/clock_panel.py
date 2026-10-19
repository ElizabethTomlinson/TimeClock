"""Clock in/out controls and digital stopwatch display UI panel."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from time_clock.engine import TimeClockEngine
from time_clock.events import Event, EventType
from time_clock.gui import theme
from time_clock.gui.add_earnings_dialog import AddEarningsDialog
from time_clock.models import format_duration


class ClockPanel(ctk.CTkFrame):
    """Hero timer card featuring live timer, start timestamps, status indicators, and clock in/out action."""

    def __init__(self, parent: tk.Widget, engine: TimeClockEngine) -> None:
        super().__init__(
            parent,
            corner_radius=theme.RADIUS_CARD,
            fg_color=theme.BG_CARD,
            border_width=1,
            border_color=theme.BORDER_CARD,
        )
        self.engine = engine

        self._build_ui()
        self._register_events()
        self.refresh_display()

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> Any:
        if "text" in kwargs:
            text_val = kwargs.pop("text")
            if hasattr(self, "_header_lbl") and self._header_lbl:
                self._header_lbl.configure(text=text_val)
        if kwargs:
            return super().configure(require_redraw=require_redraw, **kwargs)
        return None

    config = configure

    def cget(self, attribute_name: str) -> Any:
        if attribute_name == "text":
            if hasattr(self, "_header_lbl") and self._header_lbl:
                return self._header_lbl.cget("text")
        return super().cget(attribute_name)

    def __getitem__(self, key: str) -> Any:
        return self.cget(key)

    def _build_ui(self) -> None:
        # Header / Section Title
        self._header_lbl = ctk.CTkLabel(
            self,
            text="Clock Tracker",
            font=theme.get_font(11, weight="bold"),
            text_color=theme.TEXT_MUTED,
            anchor="center",
        )
        self._header_lbl.pack(fill=tk.X, pady=(10, 2))

        # Active Task Label
        self.task_title_var = tk.StringVar(value="No Task Selected")
        self.task_label = ctk.CTkLabel(
            self,
            textvariable=self.task_title_var,
            font=theme.get_font(15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="center",
        )
        self.task_label.pack(fill=tk.X, pady=(0, 2))

        # Status Label (Clocked In / Clocked Out)
        self.status_var = tk.StringVar(value="Status: Idle (Clocked Out)")
        self.status_label = ctk.CTkLabel(
            self,
            textvariable=self.status_var,
            font=theme.get_font(11, weight="bold"),
            text_color=theme.MUTED,
            anchor="center",
        )
        self.status_label.pack(fill=tk.X, pady=(0, 2))

        # Start Time Label
        self.start_time_var = tk.StringVar(value="Start Time: --")
        self.start_time_lbl = ctk.CTkLabel(
            self,
            textvariable=self.start_time_var,
            font=theme.get_font(10),
            text_color=theme.TEXT_SECONDARY,
            anchor="center",
        )
        self.start_time_lbl.pack(fill=tk.X, pady=(0, 6))

        # Large Digital Elapsed Stopwatch Display (Hero Display)
        self.timer_var = tk.StringVar(value="00:00:00")
        self.timer_lbl = ctk.CTkLabel(
            self,
            textvariable=self.timer_var,
            font=theme.get_font(36, weight="bold", mono=True),
            text_color=theme.TEXT_PRIMARY,
            anchor="center",
        )
        self.timer_lbl.pack(fill=tk.X, pady=(2, 6))

        # Unreported Time Spent Label
        self.unreported_time_var = tk.StringVar(value="Unreported Time: 00:00:00")
        self.unreported_time_lbl = ctk.CTkLabel(
            self,
            textvariable=self.unreported_time_var,
            font=theme.get_font(11, weight="bold"),
            text_color=theme.TAG_UNREPORTED,
            anchor="center",
        )
        self.unreported_time_lbl.pack(fill=tk.X, pady=(0, 2))

        # Total Time Spent Label
        self.total_time_var = tk.StringVar(value="Total Time: 00:00:00")
        self.total_time_lbl = ctk.CTkLabel(
            self,
            textvariable=self.total_time_var,
            font=theme.get_font(10),
            text_color=theme.TEXT_SECONDARY,
            anchor="center",
        )
        self.total_time_lbl.pack(fill=tk.X, pady=(0, 2))

        # Last Reported Timestamp Label
        self.last_reported_var = tk.StringVar(value="Last Reported: Never")
        self.last_reported_lbl = ctk.CTkLabel(
            self,
            textvariable=self.last_reported_var,
            font=theme.get_font(9),
            text_color=theme.TEXT_MUTED,
            anchor="center",
        )
        self.last_reported_lbl.pack(fill=tk.X, pady=(0, 8))

        # All Tasks Period Summary Chips (Day, Week, Month)
        self.summary_caption_lbl = ctk.CTkLabel(
            self,
            text="All Tasks Summary",
            font=theme.get_font(10, weight="bold"),
            text_color=theme.TEXT_MUTED,
            anchor="center",
        )
        self.summary_caption_lbl.pack(fill=tk.X, pady=(0, 2))

        period_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        period_frame.pack(fill=tk.X, padx=12, pady=(0, 10))

        self.day_time_var = tk.StringVar(value="Day: 00:00:00")
        self.week_time_var = tk.StringVar(value="Week: 00:00:00")
        self.month_time_var = tk.StringVar(value="Month: 00:00:00")

        # Day Chip
        day_chip = ctk.CTkFrame(
            period_frame,
            corner_radius=theme.RADIUS_CHIP,
            fg_color=theme.BG_APP,
            border_width=1,
            border_color=theme.BORDER_CARD,
        )
        day_chip.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        self.day_label = ctk.CTkLabel(
            day_chip,
            textvariable=self.day_time_var,
            font=theme.get_font(10, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="center",
        )
        self.day_label.pack(fill=tk.BOTH, expand=True, padx=4, pady=3)

        # Week Chip
        week_chip = ctk.CTkFrame(
            period_frame,
            corner_radius=theme.RADIUS_CHIP,
            fg_color=theme.BG_APP,
            border_width=1,
            border_color=theme.BORDER_CARD,
        )
        week_chip.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.week_label = ctk.CTkLabel(
            week_chip,
            textvariable=self.week_time_var,
            font=theme.get_font(10, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="center",
        )
        self.week_label.pack(fill=tk.BOTH, expand=True, padx=4, pady=3)

        # Month Chip
        month_chip = ctk.CTkFrame(
            period_frame,
            corner_radius=theme.RADIUS_CHIP,
            fg_color=theme.BG_APP,
            border_width=1,
            border_color=theme.BORDER_CARD,
        )
        month_chip.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))
        self.month_label = ctk.CTkLabel(
            month_chip,
            textvariable=self.month_time_var,
            font=theme.get_font(10, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="center",
        )
        self.month_label.pack(fill=tk.BOTH, expand=True, padx=4, pady=3)

        # Action Buttons Section
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        # Primary Clock In / Clock Out Button
        self.toggle_btn = ctk.CTkButton(
            btn_frame,
            text="Clock In",
            command=self._on_toggle_clock,
            corner_radius=theme.RADIUS_BUTTON,
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_HOVER,
            font=theme.get_font(12, weight="bold"),
            height=34,
        )
        self.toggle_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        # Mark Reported Button
        self.report_btn = ctk.CTkButton(
            btn_frame,
            text="Mark Reported",
            command=self._on_report_clicked,
            corner_radius=theme.RADIUS_BUTTON,
            fg_color=theme.BG_SECONDARY_BTN,
            hover_color=theme.BG_SECONDARY_BTN_HOVER,
            text_color=theme.TEXT_PRIMARY,
            font=theme.get_font(12),
            height=34,
        )
        self.report_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def _register_events(self) -> None:
        self.engine.event_bus.subscribe(EventType.TASK_CREATED, self._on_task_created_event)
        self.engine.event_bus.subscribe(EventType.TASK_ARCHIVED, self._on_task_archived_event)
        self.engine.event_bus.subscribe(EventType.TASK_UNARCHIVED, self._on_task_unarchived_event)
        self.engine.event_bus.subscribe(EventType.CLOCK_IN, self._on_clock_in_event)
        self.engine.event_bus.subscribe(EventType.CLOCK_OUT, self._on_clock_out_event)
        self.engine.event_bus.subscribe(EventType.TASK_SELECTED, self._on_task_selected_event)
        self.engine.event_bus.subscribe(EventType.TASK_DELETED, self._on_task_deleted_event)
        self.engine.event_bus.subscribe(EventType.TASK_RENAMED, self._on_task_renamed_event)
        self.engine.event_bus.subscribe(EventType.TASK_UPDATED, self._on_task_renamed_event)
        self.engine.event_bus.subscribe(EventType.TASK_REPORTED, self._on_task_reported_event)
        self.engine.event_bus.subscribe(EventType.ENTRY_UPDATED, self._on_entry_updated_event)
        self.engine.event_bus.subscribe(EventType.TASKS_CONSOLIDATED, self._on_tasks_consolidated_event)
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

    def _on_report_clicked(self) -> None:
        active_task = self.engine.get_active_task()
        if not active_task:
            messagebox.showinfo("Select Task", "Please select or create a task first.")
            return
        if active_task.is_unpaid:
            messagebox.showinfo("Unpaid Task", "Unpaid tasks do not track reported time.")
            return

        AddEarningsDialog(
            parent=self.winfo_toplevel(),
            engine=self.engine,
            initial_task_id=active_task.id,
            mark_reported=True,
        )

    def refresh_display(self) -> None:
        """Update all labels and buttons based on current engine state."""
        active_task = self.engine.get_active_task()
        if active_task:
            task_label_text = f"Active Task: {active_task.name} [Unpaid]" if active_task.is_unpaid else f"Active Task: {active_task.name}"
            self.task_title_var.set(task_label_text)
            self.toggle_btn.configure(state=tk.NORMAL)
            if active_task.is_unpaid:
                self.report_btn.configure(state=tk.DISABLED)
            else:
                self.report_btn.configure(state=tk.NORMAL)
            total_duration = active_task.total_duration_seconds
            unreported_duration = self.engine.get_task_unreported_duration(
                active_task.id, include_running=self.engine.state.is_running
            )
            if active_task.is_unpaid:
                self.last_reported_var.set("Last Reported: N/A (Unpaid Task)")
            elif active_task.last_reported_at:
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
            self.status_label.configure(text_color=theme.SUCCESS)
            self.toggle_btn.configure(
                text="Clock Out",
                fg_color=theme.DANGER,
                hover_color=theme.DANGER_HOVER,
            )
            start_display = (self.engine.state.current_session_start or "--").split(".")[0].replace("T", " ")
            self.start_time_var.set(f"Start Time: {start_display}")
            session_dur = self.engine.get_current_session_duration()
            self.timer_var.set(format_duration(session_dur))
            self.total_time_var.set(f"Total Time: {format_duration(total_duration + session_dur)}")
            if active_task and active_task.is_unpaid:
                self.unreported_time_var.set("Unreported Time: 00:00:00 (Unpaid)")
            else:
                self.unreported_time_var.set(f"Unreported Time: {format_duration(unreported_duration)}")
        else:
            self.status_var.set("○ Idle (Clocked Out)")
            self.status_label.configure(text_color=theme.MUTED)
            self.toggle_btn.configure(
                text="Clock In",
                fg_color=theme.SUCCESS,
                hover_color=theme.SUCCESS_HOVER,
            )
            self.start_time_var.set("Start Time: --")
            self.timer_var.set("00:00:00")
            self.total_time_var.set(f"Total Time: {format_duration(total_duration)}")
            if active_task and active_task.is_unpaid:
                self.unreported_time_var.set("Unreported Time: 00:00:00 (Unpaid)")
            else:
                self.unreported_time_var.set(f"Unreported Time: {format_duration(unreported_duration)}")

        periods = self.engine.get_period_durations(include_running=self.engine.state.is_running)
        self.day_time_var.set(f"Day: {format_duration(periods['day'])}")
        self.week_time_var.set(f"Week: {format_duration(periods['week'])}")
        self.month_time_var.set(f"Month: {format_duration(periods['month'])}")

    def _on_task_created_event(self, event: Event) -> None:
        self.refresh_display()

    def _on_tasks_consolidated_event(self, event: Event) -> None:
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

    def _on_entry_updated_event(self, event: Event) -> None:
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
            active_task = self.engine.get_active_task()
            if active_task and active_task.is_unpaid:
                self.unreported_time_var.set("Unreported Time: 00:00:00 (Unpaid)")
                self.last_reported_var.set("Last Reported: N/A (Unpaid Task)")
            else:
                self.unreported_time_var.set(f"Unreported Time: {data.get('unreported_duration_formatted', '00:00:00')}")
        if "day_duration_formatted" in data:
            self.day_time_var.set(f"Day: {data.get('day_duration_formatted', '00:00:00')}")
        if "week_duration_formatted" in data:
            self.week_time_var.set(f"Week: {data.get('week_duration_formatted', '00:00:00')}")
        if "month_duration_formatted" in data:
            self.month_time_var.set(f"Month: {data.get('month_duration_formatted', '00:00:00')}")
