"""Task management UI panel."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Optional

import customtkinter as ctk

from time_clock.engine import TimeClockEngine
from time_clock.events import Event, EventType
from time_clock.gui import theme
from time_clock.gui.add_earnings_dialog import AddEarningsDialog
from time_clock.gui.edit_session_dialog import EditClockInOutDialog
from time_clock.gui.prompt_dialog import ask_string
from time_clock.gui.task_options_dialog import ask_task_options
from time_clock.models import Task, format_duration


COL_HEADINGS = {
    "paid": "💰",
    "name": "Task Name",
    "total_time": "Total Time",
    "unreported_time": "Unreported",
}


class TaskPanel(ctk.CTkFrame):
    """Modernized card panel for creating, listing, selecting, and managing tasks."""

    def __init__(self, parent: tk.Widget, engine: TimeClockEngine) -> None:
        super().__init__(
            parent,
            corner_radius=theme.RADIUS_CARD,
            fg_color=theme.BG_CARD,
            border_width=1,
            border_color=theme.BORDER_CARD,
        )
        self.engine = engine
        self._updating_selection = False
        self._sort_column: Optional[str] = None
        self._sort_direction: Optional[str] = None

        self._build_ui()
        self._register_events()
        self.refresh_task_list()

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> Any:
        if "text" in kwargs:
            text_val = kwargs.pop("text")
            if hasattr(self, "_header_title_lbl") and self._header_title_lbl:
                self._header_title_lbl.configure(text=text_val)
        if kwargs:
            return super().configure(require_redraw=require_redraw, **kwargs)
        return None

    config = configure

    def cget(self, attribute_name: str) -> Any:
        if attribute_name == "text":
            if hasattr(self, "_header_title_lbl") and self._header_title_lbl:
                return self._header_title_lbl.cget("text")
        return super().cget(attribute_name)

    def __getitem__(self, key: str) -> Any:
        return self.cget(key)

    def _build_ui(self) -> None:
        # Header / Toolbar Section
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill=tk.X, padx=12, pady=(12, 8))

        self._header_title_lbl = ctk.CTkLabel(
            header_frame,
            text="Tasks",
            font=theme.get_font(14, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        self._header_title_lbl.pack(side=tk.LEFT)

        self.add_btn = ctk.CTkButton(
            header_frame,
            text="+ New Task...",
            command=self._on_add_task,
            corner_radius=theme.RADIUS_BUTTON,
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            font=theme.get_font(12, weight="bold"),
            height=28,
        )
        self.add_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.show_archived_var = tk.BooleanVar(value=False)
        self.show_archived_cb = ctk.CTkCheckBox(
            header_frame,
            text="Show Archived",
            variable=self.show_archived_var,
            command=self.refresh_task_list,
            font=theme.get_font(11),
            corner_radius=theme.RADIUS_INPUT,
            height=20,
            checkbox_width=18,
            checkbox_height=18,
        )
        self.show_archived_cb.pack(side=tk.RIGHT)

        # Task List / Treeview Section
        list_frame = ctk.CTkFrame(self, fg_color="transparent")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))

        columns = ("paid", "name", "total_time", "unreported_time")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=8,
        )
        for col, text in COL_HEADINGS.items():
            self.tree.heading(col, text=text, command=lambda c=col: self._on_header_click(c))
        self.tree.column("paid", width=35, minwidth=30, anchor=tk.CENTER, stretch=False)
        self.tree.column("name", width=180, anchor=tk.W)
        self.tree.column("total_time", width=80, anchor=tk.E)
        self.tree.column("unreported_time", width=90, anchor=tk.E)

        self.apply_tree_tags()

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Summary Section
        summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        summary_frame.pack(fill=tk.X, padx=12, pady=(0, 6))

        self.summary_var = tk.StringVar(value="Unreported: 0 projects (00:00:00)")
        self.summary_lbl = ctk.CTkLabel(
            summary_frame,
            textvariable=self.summary_var,
            font=theme.get_font(10),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.summary_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Management Action Buttons Section
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        self.rename_btn = ctk.CTkButton(
            btn_frame,
            text="Rename",
            command=self._on_rename_task,
            corner_radius=theme.RADIUS_BUTTON,
            fg_color=theme.BG_SECONDARY_BTN,
            hover_color=theme.BG_SECONDARY_BTN_HOVER,
            text_color=theme.TEXT_PRIMARY,
            font=theme.get_font(11),
            height=28,
        )
        self.rename_btn.pack(side=tk.LEFT, padx=(0, 4), expand=True, fill=tk.X)

        self.options_btn = ctk.CTkButton(
            btn_frame,
            text="Options...",
            command=self._on_edit_options,
            corner_radius=theme.RADIUS_BUTTON,
            fg_color=theme.BG_SECONDARY_BTN,
            hover_color=theme.BG_SECONDARY_BTN_HOVER,
            text_color=theme.TEXT_PRIMARY,
            font=theme.get_font(11),
            height=28,
        )
        self.options_btn.pack(side=tk.LEFT, padx=(0, 4), expand=True, fill=tk.X)

        self.earnings_btn = ctk.CTkButton(
            btn_frame,
            text="Add Earnings...",
            command=self._on_add_earnings,
            corner_radius=theme.RADIUS_BUTTON,
            fg_color=theme.BG_SECONDARY_BTN,
            hover_color=theme.BG_SECONDARY_BTN_HOVER,
            text_color=theme.TEXT_PRIMARY,
            font=theme.get_font(11),
            height=28,
        )
        self.earnings_btn.pack(side=tk.LEFT, padx=(0, 4), expand=True, fill=tk.X)

        self.report_btn = ctk.CTkButton(
            btn_frame,
            text="Report...",
            command=self._on_report_clicked,
            corner_radius=theme.RADIUS_BUTTON,
            fg_color=theme.BG_SECONDARY_BTN,
            hover_color=theme.BG_SECONDARY_BTN_HOVER,
            text_color=theme.TEXT_PRIMARY,
            font=theme.get_font(11),
            height=28,
        )
        self.report_btn.pack(side=tk.LEFT, padx=(0, 4), expand=True, fill=tk.X)

        self.archive_btn = ctk.CTkButton(
            btn_frame,
            text="Archive",
            command=self._on_archive_toggle_clicked,
            corner_radius=theme.RADIUS_BUTTON,
            fg_color=theme.BG_SECONDARY_BTN,
            hover_color=theme.BG_SECONDARY_BTN_HOVER,
            text_color=theme.TEXT_PRIMARY,
            font=theme.get_font(11),
            height=28,
        )
        self.archive_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)

    def _register_events(self) -> None:
        self.engine.event_bus.subscribe(EventType.TASK_CREATED, self._on_task_created_event)
        self.engine.event_bus.subscribe(EventType.TASK_ARCHIVED, self._on_task_archived_event)
        self.engine.event_bus.subscribe(EventType.TASK_UNARCHIVED, self._on_task_unarchived_event)
        self.engine.event_bus.subscribe(EventType.TASK_DELETED, self._on_task_deleted_event)
        self.engine.event_bus.subscribe(EventType.TASK_RENAMED, self._on_task_renamed_event)
        self.engine.event_bus.subscribe(EventType.TASK_UPDATED, self._on_task_renamed_event)
        self.engine.event_bus.subscribe(EventType.TASK_SELECTED, self._on_task_selected_event)
        self.engine.event_bus.subscribe(EventType.TASK_REPORTED, self._on_task_reported_event)
        self.engine.event_bus.subscribe(EventType.EARNING_ADDED, self._on_earning_event)
        self.engine.event_bus.subscribe(EventType.EARNING_DELETED, self._on_earning_event)
        self.engine.event_bus.subscribe(EventType.TASKS_CONSOLIDATED, self._on_tasks_consolidated_event)
        self.engine.event_bus.subscribe(EventType.CLOCK_IN, self._on_clock_in_event)
        self.engine.event_bus.subscribe(EventType.CLOCK_OUT, self._on_clock_out_event)
        self.engine.event_bus.subscribe(EventType.ENTRY_UPDATED, self._on_entry_updated_event)
        self.engine.event_bus.subscribe(EventType.TICK, self._on_tick_event)
        self.engine.event_bus.subscribe(EventType.STATE_LOADED, self._on_state_loaded_event)

    def _on_add_task(self) -> None:
        res = ask_task_options(
            title="New Task",
            initial_name="",
            initial_is_unpaid=False,
            parent=self.winfo_toplevel(),
        )
        if res is not None:
            name, is_unpaid = res
            clean_name = name.strip()
            if not clean_name:
                messagebox.showwarning("Warning", "Task name cannot be empty.", parent=self.winfo_toplevel())
                return
            try:
                self.engine.create_task(clean_name, is_unpaid=is_unpaid)
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

    def _update_report_button_state(self) -> None:
        selection = self.tree.selection()
        if selection:
            task = self.engine.get_task(selection[0])
            if task and not task.is_unpaid:
                self.report_btn.configure(state=tk.NORMAL)
                return
        self.report_btn.configure(state=tk.DISABLED)

    def _on_tree_select(self, event: tk.Event) -> None:
        self._update_archive_button_state()
        self._update_report_button_state()
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

    def _on_add_earnings(self) -> None:
        selection = self.tree.selection()
        target_id = selection[0] if selection else self.engine.state.active_task_id
        AddEarningsDialog(
            parent=self.winfo_toplevel(),
            engine=self.engine,
            initial_task_id=target_id,
        )

    def _on_earning_event(self, event: Event) -> None:
        self.refresh_task_list()

    def _on_rename_task(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select Task", "Please select a task to rename.", parent=self.winfo_toplevel())
            return
        task_id = selection[0]
        task = self.engine.get_task(task_id)
        if not task:
            return
        new_name = ask_string(
            "Rename Task",
            "Enter new task name:",
            initialvalue=task.name,
            parent=self.winfo_toplevel(),
        )
        if new_name and new_name.strip():
            try:
                self.engine.rename_task(task_id, new_name.strip())
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self.winfo_toplevel())

    def _on_edit_options(self, task_id: Optional[str] = None) -> None:
        target_id = task_id
        if not target_id:
            selection = self.tree.selection()
            if selection:
                target_id = selection[0]
            elif self.engine.state.active_task_id:
                target_id = self.engine.state.active_task_id

        EditClockInOutDialog(
            parent=self.winfo_toplevel(),
            engine=self.engine,
            initial_task_id=target_id,
        )

    def _on_report_clicked(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select Task", "Please select a task first.", parent=self.winfo_toplevel())
            return
        task_id = selection[0]
        task = self.engine.get_task(task_id)
        if not task:
            return
        if task.is_unpaid:
            messagebox.showinfo("Unpaid Task", "Unpaid tasks do not track reported time.", parent=self.winfo_toplevel())
            return

        AddEarningsDialog(
            parent=self.winfo_toplevel(),
            engine=self.engine,
            initial_task_id=task_id,
            mark_reported=True,
        )

    def _on_delete_task(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select Task", "Please select a task to delete.", parent=self.winfo_toplevel())
            return
        task_id = selection[0]
        task = self.engine.get_task(task_id)
        if not task:
            return
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete task '{task.name}' and all its logged sessions?",
            parent=self.winfo_toplevel(),
        )
        if confirm:
            try:
                self.engine.delete_task(task_id)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self.winfo_toplevel())

    def _on_header_click(self, col: str) -> None:
        """Handle clicking a column header to toggle 3-state sorting."""
        if self._sort_column != col:
            self._sort_column = col
            self._sort_direction = "primary"
        else:
            if self._sort_direction == "primary":
                self._sort_direction = "reverse"
            else:
                self._sort_column = None
                self._sort_direction = None
        self._update_heading_labels()
        self.refresh_task_list()

    def _update_heading_labels(self) -> None:
        """Update Treeview column heading text to display active sort arrow indicator."""
        for col, base_text in COL_HEADINGS.items():
            if self._sort_column == col and self._sort_direction:
                if col == "name":
                    arrow = " ▲" if self._sort_direction == "primary" else " ▼"
                else:
                    arrow = " ▼" if self._sort_direction == "primary" else " ▲"
                self.tree.heading(col, text=f"{base_text}{arrow}")
            else:
                self.tree.heading(col, text=base_text)

    def _sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Sort tasks according to current sort column and direction."""
        if not self._sort_column or not self._sort_direction:
            return tasks

        if self._sort_column == "name":
            # Primary: A -> Z (ascending), Reverse: Z -> A (descending)
            # Ignore emojis and non-alphanumeric characters for alphabetical sorting
            reverse = self._sort_direction == "reverse"
            return sorted(
                tasks,
                key=lambda t: (
                    "".join(c for c in t.name if c.isalnum()).lower(),
                    t.name.lower(),
                ),
                reverse=reverse,
            )
        elif self._sort_column == "total_time":
            # Primary: Highest to lowest (descending), Reverse: Lowest to highest (ascending)
            reverse = self._sort_direction == "primary"
            return sorted(tasks, key=lambda t: t.total_duration_seconds, reverse=reverse)
        elif self._sort_column == "unreported_time":
            # Primary: Highest to lowest (descending), Reverse: Lowest to highest (ascending)
            reverse = self._sort_direction == "primary"
            return sorted(
                tasks,
                key=lambda t: self.engine.get_task_unreported_duration(t.id, include_running=True),
                reverse=reverse,
            )
        elif self._sort_column == "paid":
            # Primary: Paid (True) first, Reverse: Unpaid (False) first
            reverse = self._sort_direction == "primary"
            return sorted(tasks, key=lambda t: not t.is_unpaid, reverse=reverse)
        return tasks

    def apply_tree_tags(self) -> None:
        """Apply theme-resolved foreground colors to Treeview tag styles."""
        self.tree.tag_configure("has_unreported", foreground=theme.resolve_color(theme.TAG_UNREPORTED))
        self.tree.tag_configure("all_reported", foreground=theme.resolve_color(theme.TEXT_PRIMARY))
        self.tree.tag_configure("unpaid", foreground=theme.resolve_color(theme.TAG_UNPAID))
        self.tree.tag_configure("archived", foreground=theme.resolve_color(theme.TAG_ARCHIVED))

    def _update_summary(self) -> None:
        """Update aggregate unreported tasks count and total unreported duration."""
        count = self.engine.get_unreported_tasks_count(include_running=True)
        total_unrep = self.engine.get_total_unreported_duration(include_running=True)
        project_text = "project" if count == 1 else "projects"
        self.summary_var.set(f"Unreported: {count} {project_text} ({format_duration(total_unrep)})")

    def refresh_task_list(self) -> None:
        """Reload tasks in the treeview and select the active task."""
        current_selection = self.tree.selection()
        selected_id = current_selection[0] if current_selection else None

        self._updating_selection = True
        try:
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)

            tasks = self.engine.get_tasks(include_archived=self.show_archived_var.get())
            sorted_tasks = self._sort_tasks(tasks)
            for task in sorted_tasks:
                paid_icon = "💰" if not task.is_unpaid else ""
                total_str = format_duration(task.total_duration_seconds)
                unrep_dur = self.engine.get_task_unreported_duration(task.id, include_running=True)
                unrep_str = format_duration(unrep_dur)
                archived_badge = " [Archived]" if task.is_archived else ""
                unpaid_badge = " [Unpaid]" if task.is_unpaid else ""
                display_name = f"{task.name}{archived_badge}{unpaid_badge}"
                if task.is_archived:
                    tag = "archived"
                elif task.is_unpaid:
                    tag = "unpaid"
                else:
                    tag = "has_unreported" if unrep_dur > 0.0 else "all_reported"
                self.tree.insert("", tk.END, iid=task.id, values=(paid_icon, display_name, total_str, unrep_str), tags=(tag,))

            target_id = selected_id if (selected_id and self.tree.exists(selected_id)) else self.engine.state.active_task_id
            if target_id and self.tree.exists(target_id):
                self.tree.selection_set(target_id)
                self.tree.focus(target_id)
        finally:
            self._updating_selection = False
        self._update_archive_button_state()
        self._update_report_button_state()
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
                elif task.is_unpaid:
                    tag = "unpaid"
                else:
                    tag = "has_unreported" if unrep_dur > 0.0 else "all_reported"
                self.tree.item(task_id, tags=(tag,))
                self._update_summary()

    def _on_task_created_event(self, event: Event) -> None:
        self.refresh_task_list()

    def _on_tasks_consolidated_event(self, event: Event) -> None:
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
            self._update_archive_button_state()
            self._update_report_button_state()

    def _on_task_reported_event(self, event: Event) -> None:
        self.refresh_task_list()

    def _on_clock_in_event(self, event: Event) -> None:
        data = event.data or {}
        task_id = data.get("task_id")
        if task_id and self.tree.exists(task_id):
            task = self.engine.get_task(task_id)
            unrep_dur = self.engine.get_task_unreported_duration(task_id, include_running=True)
            self.tree.set(task_id, "unreported_time", format_duration(unrep_dur))
            if task and task.is_archived:
                tag = "archived"
            elif task and task.is_unpaid:
                tag = "unpaid"
            else:
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
        task = self.engine.get_task(active_id)
        total_sec = data.get("total_duration", 0.0)
        unrep_sec = data.get("unreported_duration", 0.0)
        self.tree.set(active_id, "total_time", format_duration(total_sec))
        self.tree.set(active_id, "unreported_time", format_duration(unrep_sec))
        if task and task.is_archived:
            tag = "archived"
        elif task and task.is_unpaid:
            tag = "unpaid"
        else:
            tag = "has_unreported" if unrep_sec > 0.0 else "all_reported"
        self.tree.item(active_id, tags=(tag,))
        self._update_summary()

    def _on_state_loaded_event(self, event: Event) -> None:
        self.refresh_task_list()
