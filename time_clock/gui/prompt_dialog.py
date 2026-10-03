"""Reusable modal input dialogs that center on screen and operate independently."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional


class InputDialog(tk.Toplevel):
    """An independent modal input dialog that centers over the parent window."""

    def __init__(
        self,
        title: str,
        prompt: str,
        initialvalue: str = "",
        parent: Optional[tk.Widget] = None,
        width: int = 380,
        height: int = 150,
    ) -> None:
        # Pass master if available so resources are shared, but do not set transient
        master = parent.winfo_toplevel() if parent is not None else None
        super().__init__(master)
        self.parent_widget = master

        self.title(title)
        self.resizable(False, False)
        self._result: Optional[str] = None

        self.width = width
        self.height = height

        self._build_ui(prompt, initialvalue)
        self._center_on_parent()

        # Window lifecycle and modal grab
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Return>", lambda event: self._on_ok())
        self.bind("<Escape>", lambda event: self._on_cancel())

        self.lift()
        self.grab_set()
        self.entry.focus_set()
        self.wait_window(self)

    def _build_ui(self, prompt: str, initialvalue: str) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        prompt_lbl = ttk.Label(container, text=prompt, anchor=tk.W)
        prompt_lbl.pack(fill=tk.X, pady=(0, 8))

        self.entry_var = tk.StringVar(value=initialvalue)
        self.entry = ttk.Entry(container, textvariable=self.entry_var)
        self.entry.pack(fill=tk.X, pady=(0, 14))
        if initialvalue:
            self.entry.select_range(0, tk.END)

        btn_box = ttk.Frame(container)
        btn_box.pack(fill=tk.X)

        cancel_btn = ttk.Button(btn_box, text="Cancel", command=self._on_cancel)
        cancel_btn.pack(side=tk.RIGHT, padx=(6, 0))

        ok_btn = ttk.Button(btn_box, text="OK", command=self._on_ok)
        ok_btn.pack(side=tk.RIGHT)

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
        self._result = self.entry_var.get()
        self.destroy()

    def _on_cancel(self) -> None:
        self._result = None
        self.destroy()

    @property
    def result(self) -> Optional[str]:
        return self._result


def ask_string(
    title: str,
    prompt: str,
    initialvalue: str = "",
    parent: Optional[tk.Widget] = None,
) -> Optional[str]:
    """Prompt user for a single string input in a centered independent window."""
    dialog = InputDialog(
        title=title,
        prompt=prompt,
        initialvalue=initialvalue,
        parent=parent,
    )
    return dialog.result
