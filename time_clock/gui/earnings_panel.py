"""Earnings management panel with goal metrics, dynamic progress bars, and ledger history."""
from __future__ import annotations

import calendar
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any, Optional

from time_clock.engine import TimeClockEngine
from time_clock.events import Event, EventType
from time_clock.gui.add_earnings_dialog import AddEarningsDialog
from time_clock.gui.earnings_goal_dialog import EarningsGoalDialog
from time_clock.models import EarningsPeriodStats, parse_iso


class PacedProgressBar(tk.Canvas):
    """Custom canvas progress bar widget supporting a visual cycle pace marker."""

    def __init__(
        self,
        parent: tk.Widget,
        height: int = 18,
        bg_color: str = "#e5e5e5",
        fill_color: str = "#0078d4",
        marker_color: str = "#c42b1c",
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("height", height)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("bg", bg_color)
        super().__init__(parent, **kwargs)

        self._value: float = 0.0
        self._pace_marker: Optional[float] = None
        self._bg_color: str = bg_color
        self._fill_color: str = fill_color
        self._marker_color: str = marker_color

        self.bind("<Configure>", self._on_configure)

    @property
    def value(self) -> float:
        return self._value

    @property
    def pace_marker(self) -> Optional[float]:
        return self._pace_marker

    def __getitem__(self, key: str) -> Any:
        if key == "value":
            return self._value
        return super().__getitem__(key)

    def __setitem__(self, key: str, value: Any) -> None:
        if key == "value":
            self.set_progress(float(value), self._pace_marker)
        else:
            super().__setitem__(key, value)

    def set_progress(self, value: float, pace_marker: Optional[float] = None) -> None:
        """Set progress percentage (0.0 to 100.0) and optional pace marker percentage."""
        self._value = max(0.0, min(100.0, float(value)))
        if pace_marker is not None:
            self._pace_marker = max(0.0, min(100.0, float(pace_marker)))
        else:
            self._pace_marker = None
        self._redraw()

    def _on_configure(self, event: Optional[tk.Event] = None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()

        if width <= 1:
            width = self.winfo_reqwidth()
        if height <= 1:
            try:
                height = int(self.cget("height"))
            except Exception:
                height = 18

        if width <= 1 or height <= 1:
            return

        # Background trough
        self.create_rectangle(
            0, 0, width, height,
            fill=self._bg_color,
            outline="",
            tags="track",
        )

        # Progress fill
        if self._value > 0:
            fill_width = (self._value / 100.0) * width
            self.create_rectangle(
                0, 0, fill_width, height,
                fill=self._fill_color,
                outline="",
                tags="fill",
            )

        # Pace marker needle with top/bottom guide ticks
        if self._pace_marker is not None:
            marker_x = (self._pace_marker / 100.0) * width
            marker_x = max(1.0, min(float(width - 2), marker_x))

            # Vertical guide line
            self.create_line(
                marker_x, 0, marker_x, height,
                fill=self._marker_color,
                width=2,
                tags="pace_marker",
            )
            # Top tick guide
            self.create_polygon(
                marker_x - 3, 0,
                marker_x + 3, 0,
                marker_x, 4,
                fill=self._marker_color,
                outline="",
                tags="pace_marker_tick_top",
            )
            # Bottom tick guide
            self.create_polygon(
                marker_x - 3, height,
                marker_x + 3, height,
                marker_x, height - 4,
                fill=self._marker_color,
                outline="",
                tags="pace_marker_tick_bottom",
            )


class EarningsPanel(ttk.Frame):
    """Dedicated view for tracking earnings milestones, monthly targets, and earnings ledger."""

    def __init__(self, parent: tk.Widget, engine: TimeClockEngine) -> None:
        super().__init__(parent, padding=12)
        self.engine = engine

        self._build_ui()
        self._register_events()
        self.refresh()

    def _build_ui(self) -> None:
        # Top Container: Goal Overview and Action Buttons
        overview_frame = ttk.LabelFrame(self, text="Monthly Goal & Targets", padding=12)
        overview_frame.pack(fill=tk.X, pady=(0, 10))

        # Metrics Grid
        metrics_grid = ttk.Frame(overview_frame)
        metrics_grid.pack(fill=tk.X, side=tk.LEFT, expand=True)

        self.month_lbl_var = tk.StringVar(value="Month: --")
        month_lbl = ttk.Label(metrics_grid, textvariable=self.month_lbl_var, font=("Helvetica", 11, "bold"))
        month_lbl.grid(row=0, column=0, sticky=tk.W, padx=(0, 20), pady=2)

        self.cycle_lbl_var = tk.StringVar(value="Cycle: Calendar Month")
        cycle_lbl = ttk.Label(metrics_grid, textvariable=self.cycle_lbl_var, foreground="#555555")
        cycle_lbl.grid(row=0, column=1, sticky=tk.W, padx=(0, 20), pady=2)

        self.goal_lbl_var = tk.StringVar(value="Target Goal: $0.00")
        goal_lbl = ttk.Label(metrics_grid, textvariable=self.goal_lbl_var, font=("Helvetica", 10))
        goal_lbl.grid(row=1, column=0, sticky=tk.W, padx=(0, 20), pady=2)

        self.earned_lbl_var = tk.StringVar(value="Earned This Month: $0.00")
        earned_lbl = ttk.Label(metrics_grid, textvariable=self.earned_lbl_var, font=("Helvetica", 10))
        earned_lbl.grid(row=1, column=1, sticky=tk.W, padx=(0, 20), pady=2)

        self.needed_lbl_var = tk.StringVar(value="Needed Per Day: $0.00 / day")
        needed_lbl = ttk.Label(
            metrics_grid,
            textvariable=self.needed_lbl_var,
            font=("Helvetica", 11, "bold"),
            foreground="#005fb8",
        )
        needed_lbl.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(4, 2))

        # Top Right Action Buttons
        btn_box = ttk.Frame(overview_frame)
        btn_box.pack(side=tk.RIGHT, fill=tk.Y)

        self.set_goal_btn = ttk.Button(btn_box, text="Set Monthly Goal...", command=self._on_configure_goal)
        self.set_goal_btn.pack(fill=tk.X, pady=(0, 6))

        self.add_earn_btn = ttk.Button(btn_box, text="Add Earnings...", command=self._on_add_earnings)
        self.add_earn_btn.pack(fill=tk.X)

        # Middle Container: Progress Bars Card
        progress_frame = ttk.LabelFrame(self, text="Milestone Progress", padding=12)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        # Daily Progress
        self.day_text_var = tk.StringVar(value="Daily Progress: $0.00 / $0.00 (0.0%)")
        day_lbl = ttk.Label(progress_frame, textvariable=self.day_text_var, anchor=tk.W)
        day_lbl.pack(fill=tk.X, pady=(2, 2))

        self.day_pb = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, mode="determinate", maximum=100.0)
        self.day_pb.pack(fill=tk.X, pady=(0, 8))

        # Weekly Progress
        self.week_text_var = tk.StringVar(value="Weekly Progress: $0.00 / $0.00 (0.0%)")
        week_lbl = ttk.Label(progress_frame, textvariable=self.week_text_var, anchor=tk.W)
        week_lbl.pack(fill=tk.X, pady=(2, 2))

        self.week_pb = PacedProgressBar(progress_frame, height=18)
        self.week_pb.pack(fill=tk.X, pady=(0, 8))

        # Monthly Progress
        self.month_text_var = tk.StringVar(value="Monthly Progress: $0.00 / $0.00 (0.0%)")
        month_pb_lbl = ttk.Label(progress_frame, textvariable=self.month_text_var, anchor=tk.W)
        month_pb_lbl.pack(fill=tk.X, pady=(2, 2))

        self.month_pb = PacedProgressBar(progress_frame, height=18)
        self.month_pb.pack(fill=tk.X, pady=(0, 4))

        # Bottom Container: Earnings Ledger History
        ledger_frame = ttk.LabelFrame(self, text="Earnings Ledger", padding=12)
        ledger_frame.pack(fill=tk.BOTH, expand=True)

        tree_frame = ttk.Frame(ledger_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("date", "task", "note", "amount")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=6,
        )
        self.tree.heading("date", text="Date")
        self.tree.heading("task", text="Task")
        self.tree.heading("note", text="Note")
        self.tree.heading("amount", text="Amount")

        self.tree.column("date", width=140, anchor=tk.W)
        self.tree.column("task", width=180, anchor=tk.W)
        self.tree.column("note", width=220, anchor=tk.W)
        self.tree.column("amount", width=100, anchor=tk.E)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Ledger Action Buttons
        ledger_btn_frame = ttk.Frame(ledger_frame)
        ledger_btn_frame.pack(fill=tk.X, pady=(8, 0))

        self.delete_btn = ttk.Button(ledger_btn_frame, text="Delete Entry", command=self._on_delete_selected_earning)
        self.delete_btn.pack(side=tk.RIGHT)

        self.refresh_btn = ttk.Button(ledger_btn_frame, text="Refresh", command=self.refresh)
        self.refresh_btn.pack(side=tk.RIGHT, padx=(0, 6))

    def _register_events(self) -> None:
        self.engine.event_bus.subscribe(EventType.EARNING_ADDED, self._on_event_refresh)
        self.engine.event_bus.subscribe(EventType.EARNING_DELETED, self._on_event_refresh)
        self.engine.event_bus.subscribe(EventType.GOAL_UPDATED, self._on_event_refresh)
        self.engine.event_bus.subscribe(EventType.TASK_CREATED, self._on_event_refresh)
        self.engine.event_bus.subscribe(EventType.TASK_DELETED, self._on_event_refresh)
        self.engine.event_bus.subscribe(EventType.TASK_RENAMED, self._on_event_refresh)
        self.engine.event_bus.subscribe(EventType.TASK_UPDATED, self._on_event_refresh)
        self.engine.event_bus.subscribe(EventType.TASKS_CONSOLIDATED, self._on_event_refresh)
        self.engine.event_bus.subscribe(EventType.STATE_LOADED, self._on_event_refresh)

    def _on_event_refresh(self, event: Event) -> None:
        self.refresh()

    def _on_configure_goal(self) -> None:
        EarningsGoalDialog(
            parent=self.winfo_toplevel(),
            engine=self.engine,
        )

    def _on_add_earnings(self) -> None:
        AddEarningsDialog(
            parent=self.winfo_toplevel(),
            engine=self.engine,
        )

    def _on_delete_selected_earning(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select Entry", "Please select an earnings entry to delete.", parent=self.winfo_toplevel())
            return
        earning_id = selection[0]
        confirm = messagebox.askyesno(
            "Confirm Delete",
            "Are you sure you want to delete this earnings entry?",
            parent=self.winfo_toplevel(),
        )
        if confirm:
            try:
                self.engine.delete_earning(earning_id)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self.winfo_toplevel())

    def refresh(self) -> None:
        """Refresh statistics cards, progress indicators, and earnings ledger table."""
        now_dt = datetime.now()
        stats: EarningsPeriodStats = self.engine.get_earnings_stats(as_of=now_dt)

        # 1. Update Month & Overview Headers
        month_name = now_dt.strftime("%B %Y")
        self.month_lbl_var.set(f"Month: {month_name}")

        cycle_str = "4-Week Billing Cycle (28 Days)" if stats.use_28_day_month else "Calendar Month Cycle"
        self.cycle_lbl_var.set(f"Cycle: {cycle_str}")

        if stats.goal_amount > 0:
            self.goal_lbl_var.set(f"Target Goal: ${stats.goal_amount:,.2f}")
        else:
            self.goal_lbl_var.set("Target Goal: Not Set ($0.00)")

        self.earned_lbl_var.set(f"Earned This Month: ${stats.month_total:,.2f}")

        if stats.goal_amount > 0:
            if stats.month_total >= stats.goal_amount:
                self.needed_lbl_var.set("Needed Per Day: $0.00 / day (Goal Met! 🎉)")
            else:
                self.needed_lbl_var.set(f"Needed Per Day: ${stats.needed_per_day:,.2f} / day")
        else:
            self.needed_lbl_var.set("Needed Per Day: $0.00 / day")

        # 2. Update Progress Bars
        _, num_days = calendar.monthrange(now_dt.year, now_dt.month)
        target_days = 28.0 if stats.use_28_day_month else float(num_days)

        daily_target = (stats.goal_amount / target_days) if stats.goal_amount > 0 else 0.0
        weekly_target = (daily_target * 7.0) if stats.goal_amount > 0 else 0.0

        # Day PB
        day_clamped = max(0.0, min(100.0, stats.day_progress_pct))
        self.day_pb["value"] = day_clamped
        if daily_target > 0:
            self.day_text_var.set(
                f"Daily Progress: ${stats.day_total:,.2f} / ${daily_target:,.2f} ({stats.day_progress_pct:.1f}%)"
            )
        else:
            self.day_text_var.set(f"Daily Total: ${stats.day_total:,.2f} (No Goal Set)")

        # Week PB
        if weekly_target > 0:
            self.week_pb.set_progress(stats.week_progress_pct, stats.week_pace_pct)
            day_of_week = now_dt.weekday() + 1
            week_diff = stats.week_total - stats.week_expected_total
            if round(week_diff, 2) > 0:
                week_pace_delta = f"+${week_diff:,.2f} ahead"
            elif round(week_diff, 2) < 0:
                week_pace_delta = f"-${abs(week_diff):,.2f} behind"
            else:
                week_pace_delta = "On track"

            self.week_text_var.set(
                f"Weekly Progress: ${stats.week_total:,.2f} / ${weekly_target:,.2f} ({stats.week_progress_pct:.1f}%) • "
                f"Target Pace: {stats.week_pace_pct:.1f}% (Day {day_of_week}/7, {week_pace_delta})"
            )
        else:
            self.week_pb.set_progress(stats.week_progress_pct, None)
            self.week_text_var.set(f"Weekly Total: ${stats.week_total:,.2f} (No Goal Set)")

        # Month PB
        if stats.goal_amount > 0:
            self.month_pb.set_progress(stats.month_progress_pct, stats.month_pace_pct)
            effective_month_day = min(now_dt.day, int(target_days))
            month_diff = stats.month_total - stats.month_expected_total
            if round(month_diff, 2) > 0:
                month_pace_delta = f"+${month_diff:,.2f} ahead"
            elif round(month_diff, 2) < 0:
                month_pace_delta = f"-${abs(month_diff):,.2f} behind"
            else:
                month_pace_delta = "On track"

            self.month_text_var.set(
                f"Monthly Progress: ${stats.month_total:,.2f} / ${stats.goal_amount:,.2f} ({stats.month_progress_pct:.1f}%) • "
                f"Target Pace: {stats.month_pace_pct:.1f}% (Day {effective_month_day}/{int(target_days)}, {month_pace_delta})"
            )
        else:
            self.month_pb.set_progress(stats.month_progress_pct, None)
            self.month_text_var.set(f"Monthly Total: ${stats.month_total:,.2f} (No Goal Set)")

        # 3. Reload Treeview
        selected_id = self.tree.selection()[0] if self.tree.selection() else None
        for item in self.tree.get_children():
            self.tree.delete(item)

        earnings = self.engine.get_earnings()
        for e in earnings:
            task = self.engine.get_task(e.task_id)
            task_name = task.name if task else "[Deleted Task]"

            # Format date display
            date_disp = e.earned_at
            try:
                dt = parse_iso(e.earned_at.replace(" ", "T"))
                date_disp = dt.strftime("%Y-%m-%d %H:%M") if "T" in e.earned_at else dt.strftime("%Y-%m-%d")
            except Exception:
                pass

            amount_disp = f"${e.amount:,.2f}"
            self.tree.insert(
                "",
                tk.END,
                iid=e.id,
                values=(date_disp, task_name, e.note, amount_disp),
            )

        if selected_id and self.tree.exists(selected_id):
            self.tree.selection_set(selected_id)
