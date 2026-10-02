"""Task management UI panel."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Optional

from time_clock.engine import TimeClockEngine
from time_clock.events import Event, EventType
from time_clock.models import Task, format_duration, iso_now, parse_iso


class TaskPanel(ttk.LabelFrame):
    """Panel for creating, listing, selecting, and managing tasks."""

    def __init__(self, parent: tk.Widget, engine: TimeClockEngine) -> None:
        super().__init__(parent, text="Tasks", padding=10)
        self.engine = engine
        self._updating_selection = False

        self._build_ui()
        self._register_events()
        self.refresh_task_list()

    def _build_ui(self) -> None:
        # Task Creation Section
        add_frame = ttk.Frame(self)
        add_frame.pack(fill=tk.X, pady=(0, 10))

        self.add_btn = ttk.Button(
            add_frame,
            text="New Task...",
            command=self._on_add_task,
        )
        self.add_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.show_archived_var = tk.BooleanVar(value=False)
        self.show_archived_cb = ttk.Checkbutton(
            add_frame,
            text="Show Archived",
            variable=self.show_archived_var,
            command=self.refresh_task_list,
        )
        self.show_archived_cb.pack(side=tk.RIGHT)

        # Task List / Treeview Section
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("name", "total_time", "unreported_time")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=8
        )
        self.tree.heading("name", text="Task Name")
        self.tree.heading("total_time", text="Total Time")
        self.tree.heading("unreported_time", text="Unreported")
        self.tree.column("name", width=120, anchor=tk.W)
        self.tree.column("total_time", width=80, anchor=tk.E)
        self.tree.column("unreported_time", width=80, anchor=tk.E)

        self.tree.tag_configure("has_unreported", foreground="#005fb8")
        self.tree.tag_configure("all_reported", foreground="#666666")
        self.tree.tag_configure("archived", foreground="#888888")

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Summary Section
        summary_frame = ttk.Frame(self)
        summary_frame.pack(fill=tk.X, pady=(6, 0))

        self.summary_var = tk.StringVar(value="Unreported: 0 projects (00:00:00)")
        self.summary_lbl = ttk.Label(
            summary_frame,
            textvariable=self.summary_var,
            font=("Helvetica", 9, "italic"),
            anchor=tk.W,
        )
        self.summary_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Management Buttons Section
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        rename_btn = ttk.Button(btn_frame, text="Rename", command=self._on_rename_task)
        rename_btn.pack(side=tk.LEFT, padx=(0, 4), expand=True, fill=tk.X)

        self.report_btn = ttk.Button(btn_frame, text="Report...", command=self._on_mark_reported_menu)
        self.report_btn.pack(side=tk.LEFT, padx=(0, 4), expand=True, fill=tk.X)

        self.archive_btn = ttk.Button(btn_frame, text="Archive", command=self._on_archive_toggle_clicked)
        self.archive_btn.pack(side=tk.LEFT, padx=(0, 4), expand=True, fill=tk.X)

        delete_btn = ttk.Button(btn_frame, text="Delete", command=self._on_delete_task)
        delete_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X)

    def _register_events(self) -> None:
        self.engine.event_bus.subscribe(EventType.TASK_CREATED, self._on_task_created_event)
        self.engine.event_bus.subscribe(EventType.TASK_ARCHIVED, self._on_task_archived_event)
        self.engine.event_bus.subscribe(EventType.TASK_UNARCHIVED, self._on_task_unarchived_event)
        self.engine.event_bus.subscribe(EventType.TASK_DELETED, self._on_task_deleted_event)
        self.engine.event_bus.subscribe(EventType.TASK_RENAMED, self._on_task_renamed_event)
        self.engine.event_bus.subscribe(EventType.TASK_SELECTED, self._on_task_selected_event)
        self.engine.event_bus.subscribe(EventType.TASK_REPORTED, self._on_task_reported_event)
        self.engine.event_bus.subscribe(EventType.CLOCK_IN, self._on_clock_in_event)
        self.engine.event_bus.subscribe(EventType.CLOCK_OUT, self._on_clock_out_event)
        self.engine.event_bus.subscribe(EventType.ENTRY_UPDATED, self._on_entry_updated_event)
        self.engine.event_bus.subscribe(EventType.TICK, self._on_tick_event)
        self.engine.event_bus.subscribe(EventType.STATE_LOADED, self._on_state_loaded_event)

    def _on_add_task(self) -> None:
        name = simpledialog.askstring(
            "New Task",
            "Enter task name:",
            parent=self.winfo_toplevel(),
        )
        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                messagebox.showwarning("Warning", "Task name cannot be empty.", parent=self.winfo_toplevel())
                return
            try:
                self.engine.create_task(clean_name)
            except ValueError as e:
                messagebox.showerror("Error", str(e), parent=self.winfo_toplevel())

    def _update_archive_button_state(self) -> None:
        selection = self.tree.selection()
        if selection:
            task = self.engine.get_task(selection[0])
            if task and task.is_archived:
                self.archive_btn.configure(text="Unarchive")
                return
        self.archive_btn.configure(text="Archive")

    def _on_tree_select(self, event: tk.Event) -> None:
        self._update_archive_button_state()
        if self._updating_selection:
            return
        selection = self.tree.selection()
        if not selection:
            return
        task_id = selection[0]
        if self.engine.state.active_task_id != task_id:
            try:
                self.engine.select_task(task_id)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _on_archive_toggle_clicked(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select Task", "Please select a task first.")
            return
        task_id = selection[0]
        task = self.engine.get_task(task_id)
        if not task:
            return
        if task.is_archived:
            self._on_unarchive_task(task)
        else:
            self._on_archive_task(task)

    def _on_archive_task(self, task: Task) -> None:
        confirm = messagebox.askyesno(
            "Confirm Archive",
            f"Are you sure you want to archive task '{task.name}'?",
            parent=self.winfo_toplevel(),
        )
        if confirm:
            try:
                self.engine.archive_task(task.id)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self.winfo_toplevel())

    def _on_unarchive_task(self, task: Task) -> None:
        try:
            self.engine.unarchive_task(task.id)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.winfo_toplevel())

    def _on_rename_task(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select Task", "Please select a task to rename.")
            return
        task_id = selection[0]
        task = self.engine.get_task(task_id)
        if not task:
            return
        new_name = simpledialog.askstring("Rename Task", "Enter new task name:", initialvalue=task.name)
        if new_name and new_name.strip():
            try:
                self.engine.rename_task(task_id, new_name.strip())
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _on_mark_reported_menu(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select Task", "Please select a task first.")
            return
        task_id = selection[0]
        task = self.engine.get_task(task_id)
        if not task:
            return

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Mark as Reported Now", command=lambda: self._mark_reported_now(task_id))
        menu.add_command(label="Custom Timestamp...", command=lambda: self._mark_reported_custom(task_id))
        menu.add_command(label="Clear Reported Status", command=lambda: self._clear_reported_status(task_id))

        try:
            x = self.report_btn.winfo_rootx()
            y = self.report_btn.winfo_rooty() + self.report_btn.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _mark_reported_now(self, task_id: str) -> None:
        try:
            self.engine.mark_task_reported(task_id)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _mark_reported_custom(self, task_id: str) -> None:
        task = self.engine.get_task(task_id)
        if not task:
            return
        initial = task.last_reported_at or iso_now()
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
                self.engine.mark_task_reported(task_id, clean_ts)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _clear_reported_status(self, task_id: str) -> None:
        try:
            self.engine.clear_task_reported(task_id)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete_task(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select Task", "Please select a task to delete.")
            return
        task_id = selection[0]
        task = self.engine.get_task(task_id)
        if not task:
            return
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete task '{task.name}' and all its logged sessions?",
        )
        if confirm:
            try:
                self.engine.delete_task(task_id)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _update_summary(self) -> None:
        """Update aggregate unreported tasks count and total unreported duration."""
        count = self.engine.get_unreported_tasks_count(include_running=True)
        total_unrep = self.engine.get_total_unreported_duration(include_running=True)
        project_text = "project" if count == 1 else "projects"
        self.summary_var.set(f"Unreported: {count} {project_text} ({format_duration(total_unrep)})")

    def refresh_task_list(self) -> None:
        """Reload tasks in the treeview and select the active task."""
        self._updating_selection = True
        try:
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)

            tasks = self.engine.get_tasks(include_archived=self.show_archived_var.get())
            for task in tasks:
                total_str = format_duration(task.total_duration_seconds)
                unrep_dur = self.engine.get_task_unreported_duration(task.id, include_running=True)
                unrep_str = format_duration(unrep_dur)
                display_name = f"{task.name} [Archived]" if task.is_archived else task.name
                if task.is_archived:
                    tag = "archived"
                else:
                    tag = "has_unreported" if unrep_dur > 0.0 else "all_reported"
                self.tree.insert("", tk.END, iid=task.id, values=(display_name, total_str, unrep_str), tags=(tag,))

            active_id = self.engine.state.active_task_id
            if active_id and self.tree.exists(active_id):
                self.tree.selection_set(active_id)
                self.tree.focus(active_id)
        finally:
            self._updating_selection = False
        self._update_archive_button_state()
        self._update_summary()

    def update_task_duration(self, task_id: str, duration_seconds: float) -> None:
        """Update the displayed total and unreported time for a specific task row."""
        if self.tree.exists(task_id):
            task = self.engine.get_task(task_id)
            if task:
                unrep_dur = self.engine.get_task_unreported_duration(task_id, include_running=True)
                self.tree.set(task_id, "total_time", format_duration(duration_seconds))
                self.tree.set(task_id, "unreported_time", format_duration(unrep_dur))
                if task.is_archived:
                    tag = "archived"
                else:
                    tag = "has_unreported" if unrep_dur > 0.0 else "all_reported"
                self.tree.item(task_id, tags=(tag,))
                self._update_summary()

    def _on_task_created_event(self, event: Event) -> None:
        self.refresh_task_list()

    def _on_task_archived_event(self, event: Event) -> None:
        self.refresh_task_list()

    def _on_task_unarchived_event(self, event: Event) -> None:
        self.refresh_task_list()

    def _on_task_deleted_event(self, event: Event) -> None:
        self.refresh_task_list()

    def _on_task_renamed_event(self, event: Event) -> None:
        self.refresh_task_list()

    def _on_task_selected_event(self, event: Event) -> None:
        task = event.data
        if task and self.tree.exists(task.id):
            self._updating_selection = True
            try:
                self.tree.selection_set(task.id)
                self.tree.focus(task.id)
            finally:
                self._updating_selection = False

    def _on_task_reported_event(self, event: Event) -> None:
        self.refresh_task_list()

    def _on_clock_in_event(self, event: Event) -> None:
        data = event.data or {}
        task_id = data.get("task_id")
        if task_id and self.tree.exists(task_id):
            unrep_dur = self.engine.get_task_unreported_duration(task_id, include_running=True)
            self.tree.set(task_id, "unreported_time", format_duration(unrep_dur))
            tag = "has_unreported" if unrep_dur > 0.0 else "all_reported"
            self.tree.item(task_id, tags=(tag,))
            self._update_summary()

    def _on_clock_out_event(self, event: Event) -> None:
        self.refresh_task_list()

    def _on_entry_updated_event(self, event: Event) -> None:
        self.refresh_task_list()

    def _on_tick_event(self, event: Event) -> None:
        data = event.data or {}
        if not data.get("is_running"):
            return
        active_id = data.get("active_task_id")
        if not active_id or not self.tree.exists(active_id):
            return
        total_sec = data.get("total_duration", 0.0)
        unrep_sec = data.get("unreported_duration", 0.0)
        self.tree.set(active_id, "total_time", format_duration(total_sec))
        self.tree.set(active_id, "unreported_time", format_duration(unrep_sec))
        tag = "has_unreported" if unrep_sec > 0.0 else "all_reported"
        self.tree.item(active_id, tags=(tag,))
        self._update_summary()

    def _on_state_loaded_event(self, event: Event) -> None:
        self.refresh_task_list()
