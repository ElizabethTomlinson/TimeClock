"""Core TimeClock business engine and state coordinator."""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from time_clock.events import EventBus, EventType
from time_clock.models import (
    AppState,
    PeriodDurations,
    Task,
    TimeEntry,
    calculate_interval_overlap,
    format_duration,
    get_period_bounds,
    iso_now,
    parse_iso,
)
from time_clock.storage import SQLiteStorage, Storage


class TimeClockEngine:
    """Coordinates business logic, state changes, timers, persistence, and event dispatches."""

    def __init__(
        self,
        storage: Optional[Storage] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.storage = storage or SQLiteStorage(Path("data/time_clock.db"))
        self.event_bus = event_bus or EventBus()
        self.state: AppState = self.storage.load()
        self.event_bus.emit(EventType.STATE_LOADED, self.state)

    def _save_state(self) -> None:
        """Persist state and emit STATE_SAVED event."""
        self.storage.save(self.state)
        self.event_bus.emit(EventType.STATE_SAVED, self.state)

    def create_task(self, name: str) -> Task:
        """Create a new task with a unique name and add it to the state."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Task name cannot be empty.")

        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = Task(id=task_id, name=clean_name, created_at=iso_now())
        self.state.tasks[task_id] = task

        if self.state.active_task_id is None:
            self.state.active_task_id = task_id

        self._save_state()
        self.event_bus.emit(EventType.TASK_CREATED, task)
        return task

    def select_task(self, task_id: str) -> Task:
        """Select an active task. If currently clocked in on a different task, clock out first."""
        if task_id not in self.state.tasks:
            raise KeyError(f"Task with id '{task_id}' not found.")

        if self.state.active_task_id != task_id:
            if self.state.is_running:
                self.clock_out()
            self.state.active_task_id = task_id
            self._save_state()

        task = self.state.tasks[task_id]
        self.event_bus.emit(EventType.TASK_SELECTED, task)
        return task

    def delete_task(self, task_id: str) -> None:
        """Delete a task. If it is currently running, clock out first."""
        if task_id not in self.state.tasks:
            raise KeyError(f"Task with id '{task_id}' not found.")

        if self.state.is_running and self.state.active_task_id == task_id:
            self.clock_out()

        del self.state.tasks[task_id]

        if self.state.active_task_id == task_id:
            remaining_tasks = [t for t in self.state.tasks.values() if not t.is_archived]
            self.state.active_task_id = remaining_tasks[0].id if remaining_tasks else None

        self._save_state()
        self.event_bus.emit(EventType.TASK_DELETED, {"task_id": task_id})

    def archive_task(self, task_id: str) -> Task:
        """Archive a task. If it is currently running, clock out first."""
        if task_id not in self.state.tasks:
            raise KeyError(f"Task with id '{task_id}' not found.")

        if self.state.is_running and self.state.active_task_id == task_id:
            self.clock_out()

        task = self.state.tasks[task_id]
        task.is_archived = True

        if self.state.active_task_id == task_id:
            remaining_tasks = [t for t in self.state.tasks.values() if not t.is_archived]
            self.state.active_task_id = remaining_tasks[0].id if remaining_tasks else None

        self._save_state()
        self.event_bus.emit(EventType.TASK_ARCHIVED, task)
        return task

    def unarchive_task(self, task_id: str) -> Task:
        """Unarchive a task and restore it to the active task list."""
        if task_id not in self.state.tasks:
            raise KeyError(f"Task with id '{task_id}' not found.")

        task = self.state.tasks[task_id]
        task.is_archived = False

        if self.state.active_task_id is None:
            self.state.active_task_id = task_id

        self._save_state()
        self.event_bus.emit(EventType.TASK_UNARCHIVED, task)
        return task

    def rename_task(self, task_id: str, new_name: str) -> Task:
        """Rename an existing task."""
        if task_id not in self.state.tasks:
            raise KeyError(f"Task with id '{task_id}' not found.")

        clean_name = new_name.strip()
        if not clean_name:
            raise ValueError("Task name cannot be empty.")

        task = self.state.tasks[task_id]
        task.name = clean_name
        self._save_state()
        self.event_bus.emit(EventType.TASK_RENAMED, task)
        return task

    def mark_task_reported(self, task_id: str, reported_at: Optional[str] = None) -> Task:
        """Mark task logged time as reported up to the given timestamp (or current time)."""
        if task_id not in self.state.tasks:
            raise KeyError(f"Task with id '{task_id}' not found.")

        task = self.state.tasks[task_id]
        task.last_reported_at = reported_at or iso_now()
        self._save_state()
        self.event_bus.emit(EventType.TASK_REPORTED, task)
        return task

    def clear_task_reported(self, task_id: str) -> Task:
        """Clear the last reported cutoff for a task."""
        if task_id not in self.state.tasks:
            raise KeyError(f"Task with id '{task_id}' not found.")

        task = self.state.tasks[task_id]
        task.last_reported_at = None
        self._save_state()
        self.event_bus.emit(EventType.TASK_REPORTED, task)
        return task

    def get_task_unreported_duration(self, task_id: str, include_running: bool = True) -> float:
        """Calculate total unreported duration in seconds for a task, optionally including active session."""
        if task_id not in self.state.tasks:
            return 0.0

        task = self.state.tasks[task_id]
        unreported = task.calculate_unreported_duration()

        if (
            include_running
            and self.state.is_running
            and self.state.active_task_id == task_id
            and self.state.current_session_start
        ):
            try:
                session_start_dt = parse_iso(self.state.current_session_start)
                now_dt = datetime.now()
                if task.last_reported_at:
                    cutoff_dt = parse_iso(task.last_reported_at)
                    if now_dt > cutoff_dt:
                        effective_start = max(session_start_dt, cutoff_dt)
                        unreported += max(0.0, (now_dt - effective_start).total_seconds())
                else:
                    unreported += max(0.0, (now_dt - session_start_dt).total_seconds())
            except Exception:
                pass

        return unreported

    def has_unreported_time(self, task_id: str, include_running: bool = True) -> bool:
        """Check if a task currently has pending unreported duration > 0."""
        return self.get_task_unreported_duration(task_id, include_running=include_running) > 0.0

    def get_unreported_tasks(self, include_running: bool = True) -> List[Task]:
        """Return all tasks that currently have pending unreported duration > 0."""
        return [
            task
            for task in self.get_tasks()
            if self.get_task_unreported_duration(task.id, include_running=include_running) > 0.0
        ]

    def get_unreported_tasks_count(self, include_running: bool = True) -> int:
        """Return count of tasks with pending unreported duration > 0."""
        return len(self.get_unreported_tasks(include_running=include_running))

    def get_total_unreported_duration(self, include_running: bool = True) -> float:
        """Return the sum of unreported duration across all tasks."""
        return sum(
            self.get_task_unreported_duration(task.id, include_running=include_running)
            for task in self.get_tasks()
        )

    def get_period_durations(
        self,
        as_of: Optional[datetime] = None,
        include_running: bool = True,
    ) -> Dict[str, float]:
        """Calculate total accumulated duration in seconds for day, week, and month across all tasks."""
        now_dt = as_of if as_of is not None else datetime.now()
        bounds = get_period_bounds(now_dt)
        day_start = bounds["day"]
        week_start = bounds["week"]
        month_start = bounds["month"]

        day_sec = 0.0
        week_sec = 0.0
        month_sec = 0.0

        for task in self.state.tasks.values():
            for entry in task.entries:
                if not entry.end_time:
                    continue
                try:
                    start_dt = parse_iso(entry.start_time)
                    end_dt = parse_iso(entry.end_time)
                    day_sec += calculate_interval_overlap(start_dt, end_dt, day_start, now_dt)
                    week_sec += calculate_interval_overlap(start_dt, end_dt, week_start, now_dt)
                    month_sec += calculate_interval_overlap(start_dt, end_dt, month_start, now_dt)
                except Exception:
                    pass

        if (
            include_running
            and self.state.is_running
            and self.state.current_session_start
        ):
            try:
                start_dt = parse_iso(self.state.current_session_start)
                end_dt = now_dt
                if end_dt > start_dt:
                    day_sec += calculate_interval_overlap(start_dt, end_dt, day_start, now_dt)
                    week_sec += calculate_interval_overlap(start_dt, end_dt, week_start, now_dt)
                    month_sec += calculate_interval_overlap(start_dt, end_dt, month_start, now_dt)
            except Exception:
                pass

        return {
            "day": day_sec,
            "week": week_sec,
            "month": month_sec,
        }

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve task by id."""
        return self.state.tasks.get(task_id)

    def get_active_task(self) -> Optional[Task]:
        """Retrieve currently active task, if any."""
        if self.state.active_task_id:
            return self.state.tasks.get(self.state.active_task_id)
        return None

    def get_tasks(self, include_archived: bool = False) -> List[Task]:
        """Retrieve tasks, optionally including archived tasks."""
        return [t for t in self.state.tasks.values() if include_archived or not t.is_archived]

    def get_archived_tasks(self) -> List[Task]:
        """Retrieve only archived tasks."""
        return [t for t in self.state.tasks.values() if t.is_archived]

    def get_task_history(self, task_id: str) -> List[TimeEntry]:
        """Retrieve historical session entries for a task."""
        task = self.get_task(task_id)
        if task:
            return list(task.entries)
        return []

    def clock_in(self) -> str:
        """Start tracking time for the active task."""
        if not self.state.active_task_id or self.state.active_task_id not in self.state.tasks:
            raise ValueError("No active task selected to clock in.")

        if self.state.is_running:
            raise ValueError("Already clocked in.")

        start_time = iso_now()
        self.state.is_running = True
        self.state.current_session_start = start_time

        self._save_state()
        self.event_bus.emit(
            EventType.CLOCK_IN,
            {
                "task_id": self.state.active_task_id,
                "start_time": start_time,
                "task": self.get_active_task(),
            },
        )
        return start_time

    def clock_out(self) -> Optional[TimeEntry]:
        """Stop tracking time for the active task and record the session."""
        if not self.state.is_running or not self.state.current_session_start:
            raise ValueError("Not currently clocked in.")

        active_task = self.get_active_task()
        if not active_task:
            self.state.is_running = False
            self.state.current_session_start = None
            self._save_state()
            return None

        end_time = iso_now()
        start_dt = parse_iso(self.state.current_session_start)
        end_dt = parse_iso(end_time)
        duration_seconds = max(0.0, (end_dt - start_dt).total_seconds())

        entry = TimeEntry(
            id=f"entry_{uuid.uuid4().hex[:8]}",
            start_time=self.state.current_session_start,
            end_time=end_time,
            duration_seconds=duration_seconds,
        )
        active_task.entries.append(entry)

        self.state.is_running = False
        self.state.current_session_start = None

        self._save_state()
        self.event_bus.emit(
            EventType.CLOCK_OUT,
            {
                "task_id": active_task.id,
                "entry": entry,
                "task": active_task,
            },
        )
        return entry

    def get_current_session_duration(self) -> float:
        """Return the number of seconds elapsed in the active session."""
        if not self.state.is_running or not self.state.current_session_start:
            return 0.0

        try:
            start_dt = parse_iso(self.state.current_session_start)
            now_dt = datetime.now()
            return max(0.0, (now_dt - start_dt).total_seconds())
        except Exception:
            return 0.0

    def tick(self) -> Dict[str, Any]:
        """Periodic tick handler calculating live duration and dispatching TICK event."""
        session_duration = self.get_current_session_duration()
        active_task = self.get_active_task()
        task_total = active_task.total_duration_seconds if active_task else 0.0
        if self.state.is_running:
            task_total += session_duration

        unreported_duration = (
            self.get_task_unreported_duration(active_task.id, include_running=True)
            if active_task
            else 0.0
        )
        last_reported_at = active_task.last_reported_at if active_task else None

        period_durations = self.get_period_durations(include_running=True)

        payload = {
            "is_running": self.state.is_running,
            "session_duration": session_duration,
            "session_duration_formatted": format_duration(session_duration),
            "total_duration": task_total,
            "total_duration_formatted": format_duration(task_total),
            "unreported_duration": unreported_duration,
            "unreported_duration_formatted": format_duration(unreported_duration),
            "last_reported_at": last_reported_at,
            "active_task_id": self.state.active_task_id,
            "active_task_name": active_task.name if active_task else None,
            "current_session_start": self.state.current_session_start,
            "day_duration": period_durations["day"],
            "day_duration_formatted": format_duration(period_durations["day"]),
            "week_duration": period_durations["week"],
            "week_duration_formatted": format_duration(period_durations["week"]),
            "month_duration": period_durations["month"],
            "month_duration_formatted": format_duration(period_durations["month"]),
        }
        self.event_bus.emit(EventType.TICK, payload)
        return payload

    def export_data(
        self,
        file_path: Union[str, Path],
        format: str = "csv",
        task_id: Optional[str] = None,
    ) -> None:
        """Export current tracking data to CSV or JSON format."""
        from time_clock.export import export_to_csv, export_to_json

        fmt = format.strip().lower()
        if fmt == "csv":
            export_to_csv(self.state, file_path, task_id=task_id)
        elif fmt == "json":
            export_to_json(self.state, file_path, task_id=task_id)
        else:
            raise ValueError(f"Unsupported export format: '{format}'. Expected 'csv' or 'json'.")
