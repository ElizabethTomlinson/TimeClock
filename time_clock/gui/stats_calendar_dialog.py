"""Modal dialog for viewing historical time statistics using a calendar."""
from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk
from typing import Dict, Optional

from time_clock.engine import TimeClockEngine
from time_clock.models import format_duration


class StatsCalendarDialog(tk.Toplevel):
    """Modal dialog allowing users to pick a date and view daily, weekly, and monthly stats."""

    def __init__(self, parent: tk.Widget, engine: TimeClockEngine) -> None:
        super().__init__(parent)
        self.engine = engine

        self.title("Historical Time Stats")
        self.geometry("420x500")
        self.minsize(360, 440)
        self.grab_set()

        self.protocol("WM_DELETE_WINDOW", self.destroy)

        today = date.today()
        self.current_year = today.year
        self.current_month = today.month
        self.selected_date: date = today
        self._day_buttons: Dict[int, ttk.Button] = {}

        self._build_ui()

        # Center on parent window
        self.update_idletasks()
        try:
            w = 420
            h = 500
            parent_top = parent.winfo_toplevel() if parent is not None else None
            if parent_top is not None and parent_top.winfo_ismapped():
                parent_top.update_idletasks()
                pw = parent_top.winfo_width()
                ph = parent_top.winfo_height()
                px = parent_top.winfo_rootx()
                py = parent_top.winfo_rooty()
                x = px + max(0, (pw - w) // 2)
                y = py + max(0, (ph - h) // 2)
            else:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                x = max(0, (sw - w) // 2)
                y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

        self.lift()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text="Select a date to view statistics:",
            font=("Helvetica", 11)
        ).pack(pady=(0, 8))

        # Calendar Frame
        cal_container = ttk.LabelFrame(main_frame, text="Calendar", padding=8)
        cal_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Month Navigation Header
        nav_frame = ttk.Frame(cal_container)
        nav_frame.pack(fill=tk.X, pady=(0, 6))

        prev_btn = ttk.Button(nav_frame, text="<", width=3, command=self._prev_month)
        prev_btn.pack(side=tk.LEFT)

        self.month_year_var = tk.StringVar()
        month_lbl = ttk.Label(
            nav_frame,
            textvariable=self.month_year_var,
            font=("Helvetica", 11, "bold"),
            anchor=tk.CENTER
        )
        month_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        next_btn = ttk.Button(nav_frame, text=">", width=3, command=self._next_month)
        next_btn.pack(side=tk.RIGHT)

        # Days Header
        days_header = ttk.Frame(cal_container)
        days_header.pack(fill=tk.X, pady=(0, 4))
        for col_idx, day_name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            lbl = ttk.Label(days_header, text=day_name, anchor=tk.CENTER, font=("Helvetica", 9, "bold"), width=4)
            lbl.grid(row=0, column=col_idx, sticky="nsew", padx=2)
            days_header.columnconfigure(col_idx, weight=1)

        # Days Grid Frame
        self.days_grid = ttk.Frame(cal_container)
        self.days_grid.pack(fill=tk.BOTH, expand=True)
        for c in range(7):
            self.days_grid.columnconfigure(c, weight=1)

        # Statistics Section
        stats_frame = ttk.LabelFrame(main_frame, text="Time Statistics", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 10))

        self.selected_date_var = tk.StringVar()
        ttk.Label(stats_frame, textvariable=self.selected_date_var, font=("Helvetica", 10, "italic")).pack(anchor=tk.W, pady=(0, 4))

        self.day_var = tk.StringVar(value="Daily: 00:00:00")
        self.week_var = tk.StringVar(value="Weekly: 00:00:00")
        self.month_var = tk.StringVar(value="Monthly: 00:00:00")

        ttk.Label(stats_frame, textvariable=self.day_var, font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=2)
        ttk.Label(stats_frame, textvariable=self.week_var, font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=2)
        ttk.Label(stats_frame, textvariable=self.month_var, font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=2)

        # Bottom Close Button
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(4, 0))

        close_btn = ttk.Button(bottom_frame, text="Close", command=self.destroy, width=12)
        close_btn.pack(side=tk.RIGHT)

        self._render_calendar()
        self._update_stats()

    def _render_calendar(self) -> None:
        for widget in self.days_grid.winfo_children():
            widget.destroy()
        self._day_buttons.clear()

        self.month_year_var.set(f"{calendar.month_name[self.current_month]} {self.current_year}")

        cal = calendar.monthcalendar(self.current_year, self.current_month)
        today = date.today()

        for row_idx, week in enumerate(cal):
            self.days_grid.rowconfigure(row_idx, weight=1)
            for col_idx, day in enumerate(week):
                if day == 0:
                    lbl = ttk.Label(self.days_grid, text="", width=4)
                    lbl.grid(row=row_idx, column=col_idx, sticky="nsew", padx=2, pady=2)
                else:
                    day_date = date(self.current_year, self.current_month, day)
                    is_future = day_date > today
                    is_selected = day_date == self.selected_date

                    btn_text = f"[{day}]" if is_selected else str(day)
                    btn = ttk.Button(
                        self.days_grid,
                        text=btn_text,
                        width=4,
                        state="disabled" if is_future else "normal",
                        command=lambda d=day_date: self._select_date(d),
                    )
                    btn.grid(row=row_idx, column=col_idx, sticky="nsew", padx=2, pady=2)
                    self._day_buttons[day] = btn

    def _select_date(self, selected: date) -> None:
        if selected > date.today():
            return
        self.selected_date = selected
        self.current_year = selected.year
        self.current_month = selected.month
        self._render_calendar()
        self._update_stats()

    def _prev_month(self) -> None:
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self._render_calendar()

    def _next_month(self) -> None:
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self._render_calendar()

    def _update_stats(self) -> None:
        self.selected_date_var.set(f"Date: {self.selected_date.strftime('%Y-%m-%d')}")
        as_of = datetime(self.selected_date.year, self.selected_date.month, self.selected_date.day, 23, 59, 59)
        periods = self.engine.get_period_durations(as_of=as_of, include_running=False)
        self.day_var.set(f"Daily: {format_duration(periods['day'])}")
        self.week_var.set(f"Weekly: {format_duration(periods['week'])}")
        self.month_var.set(f"Monthly: {format_duration(periods['month'])}")
