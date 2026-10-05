"""Modal dialog for creating tasks and editing task options (name and paid/unpaid status)."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional, Tuple


class TaskOptionsDialog(tk.Toplevel):
    """An independent modal dialog for task configuration that centers over the parent window."""

    def __init__(
        self,
        title: str = "Task Options",
        initial_name: str = "",
        initial_is_unpaid: bool = False,
        parent: Optional[tk.Widget] = None,
        width: int = 620,
        height: int = 280,
    ) -> None:
        master = parent.winfo_toplevel() if parent is not None else None
        super().__init__(master)
        self.parent_widget = master

        self.title(title)
        self.resizable(False, False)
        self._result: Optional[Tuple[str, bool]] = None

        self.width = width
        self.height = height

        self._build_ui(initial_name, initial_is_unpaid)
        self._center_on_parent()

        # Window lifecycle and modal grab
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Return>", lambda event: self._on_ok())
        self.bind("<Escape>", lambda event: self._on_cancel())

        self.lift()
        self.grab_set()
        self.name_entry.focus_set()
        self.wait_window(self)

    def _build_ui(self, initial_name: str, initial_is_unpaid: bool) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        # Task Name
        name_lbl = ttk.Label(container, text="Task Name:", anchor=tk.W)
        name_lbl.pack(fill=tk.X, pady=(0, 4))

        self.name_var = tk.StringVar(value=initial_name)
        self.name_entry = ttk.Entry(container, textvariable=self.name_var)
        self.name_entry.pack(fill=tk.X, pady=(0, 12))
        if initial_name:
            self.name_entry.select_range(0, tk.END)

        # Task Type (Paid / Unpaid)
        type_frame = ttk.LabelFrame(container, text="Task Type", padding=(10, 6))
        type_frame.pack(fill=tk.X, pady=(0, 16))

        self.is_unpaid_var = tk.BooleanVar(value=initial_is_unpaid)
        paid_rb = ttk.Radiobutton(
            type_frame,
            text="Paid (Reportable)",
            value=False,
            variable=self.is_unpaid_var,
        )
        paid_rb.pack(anchor=tk.W, pady=(2, 2))

        unpaid_rb = ttk.Radiobutton(
            type_frame,
            text="Unpaid (Non-reportable)",
            value=True,
            variable=self.is_unpaid_var,
        )
        unpaid_rb.pack(anchor=tk.W, pady=(2, 2))

        # Buttons
        btn_box = ttk.Frame(container)
        btn_box.pack(fill=tk.X, pady=(4, 0))

        cancel_btn = ttk.Button(btn_box, text="Cancel", width=10, command=self._on_cancel)
        cancel_btn.pack(side=tk.RIGHT, padx=(6, 0))

        ok_btn = ttk.Button(btn_box, text="OK", width=10, command=self._on_ok)
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
        clean_name = self.name_var.get().strip()
        if not clean_name:
            messagebox.showwarning("Warning", "Task name cannot be empty.", parent=self)
            self.name_entry.focus_set()
            return
        self._result = (clean_name, bool(self.is_unpaid_var.get()))
        self.destroy()

    def _on_cancel(self) -> None:
        self._result = None
        self.destroy()

    @property
    def result(self) -> Optional[Tuple[str, bool]]:
        return self._result


def ask_task_options(
    title: str = "Task Options",
    initial_name: str = "",
    initial_is_unpaid: bool = False,
    parent: Optional[tk.Widget] = None,
) -> Optional[Tuple[str, bool]]:
    """Prompt user for task name and paid/unpaid status in a modal dialog."""
    dialog = TaskOptionsDialog(
        title=title,
        initial_name=initial_name,
        initial_is_unpaid=initial_is_unpaid,
        parent=parent,
    )
    return dialog.result
