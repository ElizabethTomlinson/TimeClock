"""Modal dialog for configuring monthly earnings target and 4-week month setting."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Optional

from time_clock.engine import TimeClockEngine
from time_clock.models import MonthlyGoal


class EarningsGoalDialog(tk.Toplevel):
    """An independent modal dialog for setting monthly target and 28-day billing mode."""

    def __init__(
        self,
        parent: Optional[tk.Widget],
        engine: TimeClockEngine,
        month_key: Optional[str] = None,
        width: int = 440,
        height: int = 280,
    ) -> None:
        master = parent.winfo_toplevel() if parent is not None else None
        super().__init__(master)
        self.parent_widget = master
        self.engine = engine
        self.month_key = month_key or datetime.now().strftime("%Y-%m")
        self._result: Optional[MonthlyGoal] = None

        self.title("Monthly Earnings Goal")
        self.resizable(False, False)

        self.width = width
        self.height = height

        self._build_ui()
        self._center_on_parent()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Return>", lambda event: self._on_ok())
        self.bind("<Escape>", lambda event: self._on_cancel())

        self.lift()
        self.grab_set()
        self.goal_entry.focus_set()
        self.wait_window(self)

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        current_goal = self.engine.get_monthly_goal(self.month_key)

        # Month Header
        try:
            month_dt = datetime.strptime(self.month_key, "%Y-%m")
            month_label_str = month_dt.strftime("%B %Y")
        except Exception:
            month_label_str = self.month_key

        hdr_lbl = ttk.Label(
            container,
            text=f"Target Goal for {month_label_str}",
            font=("Helvetica", 11, "bold"),
            anchor=tk.W,
        )
        hdr_lbl.pack(fill=tk.X, pady=(0, 12))

        # Goal Amount
        amount_lbl = ttk.Label(container, text="Monthly Target Amount ($):", anchor=tk.W)
        amount_lbl.pack(fill=tk.X, pady=(0, 4))

        initial_goal_str = f"{current_goal.goal_amount:.2f}" if current_goal.goal_amount > 0 else ""
        self.goal_var = tk.StringVar(value=initial_goal_str)
        self.goal_entry = ttk.Entry(container, textvariable=self.goal_var)
        self.goal_entry.pack(fill=tk.X, pady=(0, 12))
        if initial_goal_str:
            self.goal_entry.select_range(0, tk.END)

        # 4-Week Option Checkbox
        opt_frame = ttk.Frame(container)
        opt_frame.pack(fill=tk.X, pady=(0, 16))

        self.use_28_var = tk.BooleanVar(value=current_goal.use_28_day_month)
        self.use_28_cb = ttk.Checkbutton(
            opt_frame,
            text="Use 4-week month (28-day target horizon)",
            variable=self.use_28_var,
        )
        self.use_28_cb.pack(anchor=tk.W)

        hint_lbl = ttk.Label(
            opt_frame,
            text="Distributes target over first 28 days while tracking full calendar month.",
            font=("Helvetica", 8, "italic"),
            foreground="#666666",
        )
        hint_lbl.pack(anchor=tk.W, padx=(22, 0), pady=(2, 0))

        # Action Buttons
        btn_box = ttk.Frame(container)
        btn_box.pack(fill=tk.X)

        cancel_btn = ttk.Button(btn_box, text="Cancel", width=10, command=self._on_cancel)
        cancel_btn.pack(side=tk.RIGHT, padx=(6, 0))

        ok_btn = ttk.Button(btn_box, text="Save Goal", width=10, command=self._on_ok)
        ok_btn.pack(side=tk.RIGHT)

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
        raw_amount = self.goal_var.get().strip().lstrip("$")
        if not raw_amount:
            goal_amount = 0.0
        else:
            try:
                goal_amount = float(raw_amount)
                if goal_amount < 0:
                    raise ValueError("Goal amount cannot be negative.")
            except ValueError:
                messagebox.showerror(
                    "Invalid Goal Amount",
                    "Please enter a valid numeric target amount (e.g. 3000.00).",
                    parent=self,
                )
                self.goal_entry.focus_set()
                return

        try:
            goal = self.engine.set_monthly_goal(
                goal_amount=goal_amount,
                use_28_day_month=bool(self.use_28_var.get()),
                month_key=self.month_key,
            )
            self._result = goal
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _on_cancel(self) -> None:
        self._result = None
        self.destroy()

    @property
    def result(self) -> Optional[MonthlyGoal]:
        return self._result
