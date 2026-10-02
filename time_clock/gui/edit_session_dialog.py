"""Modal dialog for editing clock in/out timestamps and manual session entries."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

from time_clock.engine import TimeClockEngine
from time_clock.events import Event, EventType
from time_clock.models import Task, TimeEntry, format_duration, iso_now, parse_iso


class EditClockInOutDialog(tk.Toplevel):
    """Modal dialog allowing users to adjust active and historical clock in/out timestamps."""

    def __init__(
        self,
        parent: tk.Widget,
        engine: TimeClockEngine,
        initial_task_id: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.selected_task_id = initial_task_id or self.engine.state.active_task_id
        self._entry_map: Dict[str, TimeEntry] = {}
        self._selected_entry_id: Optional[str] = None

        self.title("Edit Task Clock In/Out")
        self.geometry("640x620")
        self.minsize(580, 520)

        self.transient(parent)
        self.grab_set()

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Destroy>", self._on_destroy_event)

        self._build_ui()
        self._register_events()
        self._populate_tasks()
        self._load_task_data()

        # Center on parent window
        self.update_idletasks()
        try:
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
            x = px + max(0, (pw - w) // 2)
            y = py + max(0, (ph - h) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Task Selector Header
        task_frame = ttk.LabelFrame(main_frame, text="Task", padding=8)
        task_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(task_frame, text="Select Task:").pack(side=tk.LEFT, padx=(0, 8))
        self.task_var = tk.StringVar()
        self.task_cb = ttk.Combobox(task_frame, textvariable=self.task_var, state="readonly", width=40)
        self.task_cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.task_cb.bind("<<ComboboxSelected>>", self._on_task_selected)

        # 2. Active Session Section
        self.active_frame = ttk.LabelFrame(main_frame, text="Active Running Session", padding=8)
        self.active_frame.pack(fill=tk.X, pady=(0, 10))

        self.active_status_lbl = ttk.Label(self.active_frame, text="Timer is not running.")
        self.active_status_lbl.pack(anchor=tk.W, pady=(0, 4))

        active_input_frame = ttk.Frame(self.active_frame)
        active_input_frame.pack(fill=tk.X, pady=(2, 2))

        ttk.Label(active_input_frame, text="Start Time:").pack(side=tk.LEFT, padx=(0, 8))
        self.active_start_var = tk.StringVar()
        self.active_start_entry = ttk.Entry(active_input_frame, textvariable=self.active_start_var, width=24)
        self.active_start_entry.pack(side=tk.LEFT, padx=(0, 8))

        self.active_apply_btn = ttk.Button(
            active_input_frame,
            text="Apply Start Time",
            command=self._on_apply_active_start,
        )
        self.active_apply_btn.pack(side=tk.LEFT)

        self.active_hint_lbl = ttk.Label(
            self.active_frame,
            text="Format: YYYY-MM-DD HH:MM:SS or YYYY-MM-DDTHH:MM:SS",
            font=("Helvetica", 8, "italic"),
            foreground="#666666",
        )
        self.active_hint_lbl.pack(anchor=tk.W, pady=(2, 0))

        # 3. Completed Sessions History Section
        history_frame = ttk.LabelFrame(main_frame, text="Completed Sessions", padding=8)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        tree_container = ttk.Frame(history_frame)
        tree_container.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        columns = ("index", "start", "end", "duration")
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=6,
        )
        self.tree.heading("index", text="#")
        self.tree.heading("start", text="Start Time")
        self.tree.heading("end", text="End Time")
        self.tree.heading("duration", text="Duration")

        self.tree.column("index", width=35, anchor=tk.CENTER)
        self.tree.column("start", width=170, anchor=tk.W)
        self.tree.column("end", width=170, anchor=tk.W)
        self.tree.column("duration", width=85, anchor=tk.E)

        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # 4. Session Edit & Add Subform
        edit_box = ttk.LabelFrame(history_frame, text="Edit / Add Session", padding=8)
        edit_box.pack(fill=tk.X)

        fields_row = ttk.Frame(edit_box)
        fields_row.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(fields_row, text="Start:").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_start_var = tk.StringVar()
        self.entry_start_entry = ttk.Entry(fields_row, textvariable=self.entry_start_var, width=20)
        self.entry_start_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(fields_row, text="End:").pack(side=tk.LEFT, padx=(0, 4))
        self.entry_end_var = tk.StringVar()
        self.entry_end_entry = ttk.Entry(fields_row, textvariable=self.entry_end_var, width=20)
        self.entry_end_entry.pack(side=tk.LEFT, padx=(0, 10))

        self.save_entry_btn = ttk.Button(
            fields_row,
            text="Save Changes",
            command=self._on_save_entry,
        )
        self.save_entry_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.add_entry_btn = ttk.Button(
            fields_row,
            text="Add as New",
            command=self._on_add_manual_entry,
        )
        self.add_entry_btn.pack(side=tk.LEFT)

        ttk.Label(
            edit_box,
            text="Tip: Select a row above to edit timestamps, or fill Start & End to insert a missed session.",
            font=("Helvetica", 8, "italic"),
            foreground="#666666",
        ).pack(anchor=tk.W, pady=(2, 0))

        # Bottom Close Button
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(4, 0))

        close_btn = ttk.Button(bottom_frame, text="Close", command=self.destroy, width=12)
        close_btn.pack(side=tk.RIGHT)

    def _register_events(self) -> None:
        self.engine.event_bus.subscribe(EventType.ENTRY_UPDATED, self._on_entry_updated_event)
        self.engine.event_bus.subscribe(EventType.CLOCK_IN, self._on_engine_state_event)
        self.engine.event_bus.subscribe(EventType.CLOCK_OUT, self._on_engine_state_event)

    def _unregister_events(self) -> None:
        try:
            self.engine.event_bus.unsubscribe(EventType.ENTRY_UPDATED, self._on_entry_updated_event)
            self.engine.event_bus.unsubscribe(EventType.CLOCK_IN, self._on_engine_state_event)
            self.engine.event_bus.unsubscribe(EventType.CLOCK_OUT, self._on_engine_state_event)
        except Exception:
            pass

    def _on_destroy_event(self, event: tk.Event) -> None:
        if event.widget == self:
            self._unregister_events()

    def destroy(self) -> None:
        self._unregister_events()
        super().destroy()

    def _populate_tasks(self) -> None:
        tasks = self.engine.get_tasks(include_archived=True)
        self._task_options: List[tuple[str, str]] = []
        combobox_values = []

        for task in tasks:
            archived_tag = " [Archived]" if task.is_archived else ""
            display_text = f"{task.name}{archived_tag}"
            self._task_options.append((task.id, display_text))
            combobox_values.append(display_text)

        self.task_cb["values"] = combobox_values

        # Select initial task
        if self.selected_task_id:
            for idx, (tid, _) in enumerate(self._task_options):
                if tid == self.selected_task_id:
                    self.task_cb.current(idx)
                    break
        elif self._task_options:
            self.task_cb.current(0)
            self.selected_task_id = self._task_options[0][0]

    def _on_task_selected(self, event: Optional[tk.Event] = None) -> None:
        idx = self.task_cb.current()
        if idx >= 0 and idx < len(self._task_options):
            self.selected_task_id = self._task_options[idx][0]
            self._load_task_data()

    def _load_task_data(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        if not self.selected_task_id:
            return

        task = self.engine.get_task(self.selected_task_id)
        if not task:
            return

        try:
            # 1. Active Session State
            is_active_and_running = (
                self.engine.state.is_running
                and self.engine.state.active_task_id == self.selected_task_id
            )

            if is_active_and_running:
                start_str = self.engine.state.current_session_start or ""
                display_start = start_str.split(".")[0].replace("T", " ")
                self.active_status_lbl.configure(
                    text=f"Task is actively clocked in since: {display_start}",
                    foreground="#005fb8",
                )
                self.active_start_var.set(display_start)
                self.active_start_entry.configure(state=tk.NORMAL)
                self.active_apply_btn.configure(state=tk.NORMAL)
            else:
                self.active_status_lbl.configure(
                    text="Task is not currently clocked in.",
                    foreground="#666666",
                )
                self.active_start_var.set("")
                self.active_start_entry.configure(state=tk.DISABLED)
                self.active_apply_btn.configure(state=tk.DISABLED)

            # 2. Historical Entries Table
            for item in self.tree.get_children():
                self.tree.delete(item)

            self._entry_map.clear()
            self._selected_entry_id = None
            self.entry_start_var.set("")
            self.entry_end_var.set("")

            entries = list(task.entries)
            for idx, entry in enumerate(entries, start=1):
                self._entry_map[entry.id] = entry
                start_str = entry.start_time.split(".")[0].replace("T", " ")
                end_str = (entry.end_time or "--").split(".")[0].replace("T", " ")
                dur_str = format_duration(entry.duration_seconds)
                self.tree.insert("", tk.END, iid=entry.id, values=(idx, start_str, end_str, dur_str))
        except Exception:
            pass

    def _on_tree_select(self, event: Optional[tk.Event] = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        entry_id = selection[0]
        entry = self._entry_map.get(entry_id)
        if entry:
            self._selected_entry_id = entry.id
            self.entry_start_var.set(entry.start_time.split(".")[0].replace("T", " "))
            self.entry_end_var.set((entry.end_time or "").split(".")[0].replace("T", " "))

    def _parse_timestamp(self, ts_str: str, label: str) -> str:
        clean = ts_str.strip()
        if not clean:
            raise ValueError(f"{label} cannot be empty.")
        clean_iso = clean.replace(" ", "T")
        try:
            dt = parse_iso(clean_iso)
            return dt.isoformat()
        except Exception:
            raise ValueError(
                f"Invalid {label} format: '{clean}'.\nExpected format: YYYY-MM-DD HH:MM:SS or YYYY-MM-DDTHH:MM:SS"
            )

    def _on_apply_active_start(self) -> None:
        raw_start = self.active_start_var.get()
        try:
            iso_start = self._parse_timestamp(raw_start, "Active Session Start Time")
            self.engine.update_current_session_start(iso_start)
            messagebox.showinfo(
                "Success",
                "Active session start time updated successfully.",
                parent=self,
            )
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _on_save_entry(self) -> None:
        if not self._selected_entry_id:
            messagebox.showinfo(
                "Select Entry",
                "Please select a completed session from the list above to edit.",
                parent=self,
            )
            return

        if not self.selected_task_id:
            return

        try:
            start_iso = self._parse_timestamp(self.entry_start_var.get(), "Start Time")
            end_iso = self._parse_timestamp(self.entry_end_var.get(), "End Time")

            self.engine.update_time_entry(
                task_id=self.selected_task_id,
                entry_id=self._selected_entry_id,
                start_time=start_iso,
                end_time=end_iso,
            )
            messagebox.showinfo(
                "Success",
                "Session entry updated successfully.",
                parent=self,
            )
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _on_add_manual_entry(self) -> None:
        if not self.selected_task_id:
            messagebox.showinfo("Select Task", "Please select a task first.", parent=self)
            return

        try:
            start_iso = self._parse_timestamp(self.entry_start_var.get(), "Start Time")
            end_iso = self._parse_timestamp(self.entry_end_var.get(), "End Time")

            self.engine.add_manual_time_entry(
                task_id=self.selected_task_id,
                start_time=start_iso,
                end_time=end_iso,
            )
            messagebox.showinfo(
                "Success",
                "New session entry added successfully.",
                parent=self,
            )
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _on_entry_updated_event(self, event: Event) -> None:
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._load_task_data()

    def _on_engine_state_event(self, event: Event) -> None:
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._load_task_data()
