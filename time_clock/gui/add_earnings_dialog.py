"""Modal dialog for logging earnings amounts associated with tasks and interactive date picker."""
from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Dict, Optional

from time_clock.engine import TimeClockEngine
from time_clock.models import EarningEntry, parse_iso


class CalendarPickerDialog(tk.Toplevel):
    """Interactive modal calendar popup for picking a specific date."""

    def __init__(
        self,
        parent: Optional[tk.Widget],
        initial_date: Optional[date] = None,
        width: int = 340,
        height: int = 320,
    ) -> None:
        master = parent.winfo_toplevel() if parent is not None else None
        super().__init__(master)
        self.parent_widget = master
        self._result: Optional[date] = None

        self.title("Select Date")
        self.resizable(False, False)

        self.width = width
        self.height = height

        self.selected_date: date = initial_date or date.today()
        self.current_year: int = self.selected_date.year
        self.current_month: int = self.selected_date.month

        self._build_ui()
        self._center_on_parent()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda event: self._on_cancel())

        self.lift()
        self.grab_set()
        self.wait_window(self)

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Month Navigation Header
        nav_frame = ttk.Frame(main_frame)
        nav_frame.pack(fill=tk.X, pady=(0, 6))

        prev_btn = ttk.Button(nav_frame, text="<", width=3, command=self._prev_month)
        prev_btn.pack(side=tk.LEFT)

        self.month_year_var = tk.StringVar()
        month_lbl = ttk.Label(
            nav_frame,
            textvariable=self.month_year_var,
            font=("Helvetica", 10, "bold"),
            anchor=tk.CENTER,
        )
        month_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        next_btn = ttk.Button(nav_frame, text=">", width=3, command=self._next_month)
        next_btn.pack(side=tk.RIGHT)

        # Days Header
        days_header = ttk.Frame(main_frame)
        days_header.pack(fill=tk.X, pady=(0, 4))
        for col_idx, day_name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            lbl = ttk.Label(days_header, text=day_name, anchor=tk.CENTER, font=("Helvetica", 9, "bold"), width=4)
            lbl.grid(row=0, column=col_idx, sticky="nsew", padx=1)
            days_header.columnconfigure(col_idx, weight=1)

        # Days Grid
        self.days_grid = ttk.Frame(main_frame)
        self.days_grid.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        for c in range(7):
            self.days_grid.columnconfigure(c, weight=1)

        # Bottom Action Buttons
        btn_box = ttk.Frame(main_frame)
        btn_box.pack(fill=tk.X)

        today_btn = ttk.Button(btn_box, text="Today", command=self._on_today, width=8)
        today_btn.pack(side=tk.LEFT)

        cancel_btn = ttk.Button(btn_box, text="Cancel", command=self._on_cancel, width=8)
        cancel_btn.pack(side=tk.RIGHT)

        self._render_calendar()

    def _render_calendar(self) -> None:
        for widget in self.days_grid.winfo_children():
            widget.destroy()

        self.month_year_var.set(f"{calendar.month_name[self.current_month]} {self.current_year}")
        cal = calendar.monthcalendar(self.current_year, self.current_month)

        for row_idx, week in enumerate(cal):
            self.days_grid.rowconfigure(row_idx, weight=1)
            for col_idx, day in enumerate(week):
                if day == 0:
                    lbl = ttk.Label(self.days_grid, text="", width=4)
                    lbl.grid(row=row_idx, column=col_idx, sticky="nsew", padx=1, pady=1)
                else:
                    day_date = date(self.current_year, self.current_month, day)
                    is_selected = day_date == self.selected_date
                    btn_text = f"[{day}]" if is_selected else str(day)
                    btn = ttk.Button(
                        self.days_grid,
                        text=btn_text,
                        width=4,
                        command=lambda d=day_date: self._select_date(d),
                    )
                    btn.grid(row=row_idx, column=col_idx, sticky="nsew", padx=1, pady=1)

    def _select_date(self, selected: date) -> None:
        self._result = selected
        self.destroy()

    def _on_today(self) -> None:
        self._result = date.today()
        self.destroy()

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

    def _center_on_parent(self) -> None:
        self.update_idletasks()
        w = self.width
        h = self.height
        try:
            if self.parent_widget is not None and self.parent_widget.winfo_ismapped():
                self.parent_widget.update_idletasks()
                pw = self.parent_widget.winfo_width()
                ph = self.parent_widget.winfo_height()
                px = self.parent_widget.winfo_rootx()
                py = self.parent_widget.winfo_rooty()
                x = px + max(0, (pw - w) // 2)
                y = py + max(0, (ph - h) // 2)
            else:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                x = max(0, (sw - w) // 2)
                y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry(f"{w}x{h}")

    def _on_cancel(self) -> None:
        self._result = None
        self.destroy()

    @property
    def result(self) -> Optional[date]:
        return self._result


class AddEarningsDialog(tk.Toplevel):
    """An independent modal dialog for adding task earnings with date selection."""

    def __init__(
        self,
        parent: Optional[tk.Widget],
        engine: TimeClockEngine,
        initial_task_id: Optional[str] = None,
        width: int = 440,
        height: int = 360,
    ) -> None:
        master = parent.winfo_toplevel() if parent is not None else None
        super().__init__(master)
        self.parent_widget = master
        self.engine = engine
        self._result: Optional[EarningEntry] = None

        self.title("Add Earnings")
        self.resizable(False, False)

        self.width = width
        self.height = height

        self.task_map: Dict[str, str] = {}  # display_str -> task_id
        self._updating_date_vars = False
        self._build_ui(initial_task_id)
        self._center_on_parent()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Return>", lambda event: self._on_ok())
        self.bind("<Escape>", lambda event: self._on_cancel())

        self.lift()
        self.grab_set()
        self.amount_entry.focus_set()
        self.wait_window(self)

    def _build_ui(self, initial_task_id: Optional[str]) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        # Task Selection Dropdown with default task fallback
        task_lbl = ttk.Label(container, text="Task:", anchor=tk.W)
        task_lbl.pack(fill=tk.X, pady=(0, 4))

        tasks = self.engine.get_tasks(include_archived=True)
        if not tasks:
            # Create a default task when none is available
            default_task = self.engine.create_task("General")
            tasks = [default_task]

        self.task_map.clear()
        task_display_list = []
        selected_display = ""

        target_id = initial_task_id or self.engine.state.active_task_id

        for t in tasks:
            archived_tag = " [Archived]" if t.is_archived else ""
            unpaid_tag = " [Unpaid]" if t.is_unpaid else ""
            disp = f"{t.name}{archived_tag}{unpaid_tag}"
            self.task_map[disp] = t.id
            task_display_list.append(disp)
            if target_id == t.id:
                selected_display = disp

        if not selected_display and task_display_list:
            selected_display = task_display_list[0]

        self.task_var = tk.StringVar(value=selected_display)
        self.task_combo = ttk.Combobox(
            container,
            textvariable=self.task_var,
            values=task_display_list,
            state="readonly" if task_display_list else "disabled",
        )
        self.task_combo.pack(fill=tk.X, pady=(0, 12))

        # Earnings Amount
        amount_lbl = ttk.Label(container, text="Earnings Amount ($):", anchor=tk.W)
        amount_lbl.pack(fill=tk.X, pady=(0, 4))

        self.amount_var = tk.StringVar()
        self.amount_entry = ttk.Entry(container, textvariable=self.amount_var)
        self.amount_entry.pack(fill=tk.X, pady=(0, 12))

        # Date Picker Section (replacing freeform text parsing)
        date_lbl = ttk.Label(container, text="Date Earned:", anchor=tk.W)
        date_lbl.pack(fill=tk.X, pady=(0, 4))

        picker_frame = ttk.Frame(container)
        picker_frame.pack(fill=tk.X, pady=(0, 12))

        today = date.today()
        current_year = today.year
        year_values = [str(y) for y in range(current_year - 5, current_year + 6)]

        self.year_var = tk.StringVar(value=str(today.year))
        self.year_combo = ttk.Combobox(
            picker_frame,
            textvariable=self.year_var,
            values=year_values,
            width=6,
            state="readonly",
        )
        self.year_combo.pack(side=tk.LEFT, padx=(0, 4))
        self.year_combo.bind("<<ComboboxSelected>>", self._on_date_component_changed)

        month_values = [f"{m:02d}" for m in range(1, 13)]
        self.month_var = tk.StringVar(value=f"{today.month:02d}")
        self.month_combo = ttk.Combobox(
            picker_frame,
            textvariable=self.month_var,
            values=month_values,
            width=4,
            state="readonly",
        )
        self.month_combo.pack(side=tk.LEFT, padx=(0, 4))
        self.month_combo.bind("<<ComboboxSelected>>", self._on_date_component_changed)

        self.day_var = tk.StringVar(value=f"{today.day:02d}")
        self.day_combo = ttk.Combobox(
            picker_frame,
            textvariable=self.day_var,
            width=4,
            state="readonly",
        )
        self.day_combo.pack(side=tk.LEFT, padx=(0, 8))
        self._update_day_choices()
        self.day_combo.bind("<<ComboboxSelected>>", self._on_date_component_changed)

        cal_btn = ttk.Button(
            picker_frame,
            text="📅 Pick Date...",
            command=self._on_open_calendar,
        )
        cal_btn.pack(side=tk.LEFT)

        # Date String Model (synchronized with picker)
        self.date_var = tk.StringVar(value=today.strftime("%Y-%m-%d"))
        self.date_var.trace_add("write", self._on_date_var_written)

        # Optional Note
        note_lbl = ttk.Label(container, text="Note (Optional):", anchor=tk.W)
        note_lbl.pack(fill=tk.X, pady=(0, 4))

        self.note_var = tk.StringVar()
        self.note_entry = ttk.Entry(container, textvariable=self.note_var)
        self.note_entry.pack(fill=tk.X, pady=(0, 16))

        # Action Buttons
        btn_box = ttk.Frame(container)
        btn_box.pack(fill=tk.X)

        cancel_btn = ttk.Button(btn_box, text="Cancel", width=10, command=self._on_cancel)
        cancel_btn.pack(side=tk.RIGHT, padx=(6, 0))

        ok_btn = ttk.Button(btn_box, text="Save", width=10, command=self._on_ok)
        ok_btn.pack(side=tk.RIGHT)

    def _update_day_choices(self) -> None:
        try:
            year = int(self.year_var.get())
            month = int(self.month_var.get())
            _, num_days = calendar.monthrange(year, month)
        except Exception:
            num_days = 31

        day_values = [f"{d:02d}" for d in range(1, num_days + 1)]
        self.day_combo["values"] = day_values

        try:
            cur_day = int(self.day_var.get())
            if cur_day > num_days:
                self.day_var.set(f"{num_days:02d}")
            elif cur_day < 1:
                self.day_var.set("01")
        except Exception:
            self.day_var.set("01")

    def _on_date_component_changed(self, event: Optional[tk.Event] = None) -> None:
        if self._updating_date_vars:
            return
        self._updating_date_vars = True
        try:
            self._update_day_choices()
            year = int(self.year_var.get())
            month = int(self.month_var.get())
            day = int(self.day_var.get())
            self.date_var.set(f"{year:04d}-{month:02d}-{day:02d}")
        finally:
            self._updating_date_vars = False

    def _on_date_var_written(self, *args) -> None:
        if self._updating_date_vars:
            return
        self._updating_date_vars = True
        try:
            raw = self.date_var.get().strip().replace(" ", "T")
            parsed = parse_iso(raw)
            self.year_var.set(str(parsed.year))
            self.month_var.set(f"{parsed.month:02d}")
            self._update_day_choices()
            self.day_var.set(f"{parsed.day:02d}")
        except Exception:
            pass
        finally:
            self._updating_date_vars = False

    def _on_open_calendar(self) -> None:
        try:
            current_selected = date(
                int(self.year_var.get()),
                int(self.month_var.get()),
                int(self.day_var.get()),
            )
        except Exception:
            current_selected = date.today()

        cal_dialog = CalendarPickerDialog(self, initial_date=current_selected)
        if cal_dialog.result is not None:
            res_date = cal_dialog.result
            self.year_var.set(str(res_date.year))
            self.month_var.set(f"{res_date.month:02d}")
            self._update_day_choices()
            self.day_var.set(f"{res_date.day:02d}")
            self._on_date_component_changed()

    def _center_on_parent(self) -> None:
        self.update_idletasks()
        req_w = self.winfo_reqwidth()
        req_h = self.winfo_reqheight()
        w = max(self.width, req_w)
        h = max(self.height, req_h)
        try:
            if self.parent_widget is not None and self.parent_widget.winfo_ismapped():
                self.parent_widget.update_idletasks()
                pw = self.parent_widget.winfo_width()
                ph = self.parent_widget.winfo_height()
                px = self.parent_widget.winfo_rootx()
                py = self.parent_widget.winfo_rooty()
                x = px + (pw - w) // 2
                y = py + (ph - h) // 2
            else:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                x = max(0, (sw - w) // 2)
                y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry(f"{w}x{h}")

    def _on_ok(self) -> None:
        selected_display = self.task_var.get()
        task_id = self.task_map.get(selected_display)
        if not task_id:
            messagebox.showwarning("Warning", "Please select a valid task.", parent=self)
            return

        # Validate Amount
        raw_amount = self.amount_var.get().strip().lstrip("$")
        try:
            amount = float(raw_amount)
            if amount <= 0:
                raise ValueError("Amount must be positive.")
        except ValueError:
            messagebox.showerror(
                "Invalid Amount",
                "Please enter a valid positive earnings amount (e.g., 150.00).",
                parent=self,
            )
            self.amount_entry.focus_set()
            return

        # Validate Date from DatePicker
        raw_date = self.date_var.get().strip().replace(" ", "T")
        try:
            parsed_dt = parse_iso(raw_date)
            iso_date_str = parsed_dt.isoformat()
        except Exception:
            messagebox.showerror(
                "Invalid Date",
                "Please select a valid date.",
                parent=self,
            )
            return

        note = self.note_var.get().strip()

        try:
            entry = self.engine.add_earning(
                task_id=task_id,
                amount=amount,
                earned_at=iso_date_str,
                note=note,
            )
            self._result = entry
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _on_cancel(self) -> None:
        self._result = None
        self.destroy()

    @property
    def result(self) -> Optional[EarningEntry]:
        return self._result
