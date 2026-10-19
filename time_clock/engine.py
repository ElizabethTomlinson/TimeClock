"""Core TimeClock business engine and state coordinator."""
from __future__ import annotations

import calendar
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from time_clock.events import EventBus, EventType
from time_clock.models import (
    AppState,
    EarningEntry,
    EarningsPeriodStats,
    MonthlyGoal,
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

    def create_task(self, name: str, is_unpaid: bool = False) -> Task:
        """Create a new task with a unique name and add it to the state."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Task name cannot be empty.")

        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = Task(id=task_id, name=clean_name, created_at=iso_now(), is_unpaid=is_unpaid)
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
        return self.update_task_options(task_id, name=new_name)

    def update_task_options(
        self,
        task_id: str,
        name: Optional[str] = None,
        is_unpaid: Optional[bool] = None,
    ) -> Task:
        """Update task name and/or paid/unpaid status."""
        if task_id not in self.state.tasks:
            raise KeyError(f"Task with id '{task_id}' not found.")

        task = self.state.tasks[task_id]
        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise ValueError("Task name cannot be empty.")
            task.name = clean_name

        if is_unpaid is not None:
            task.is_unpaid = bool(is_unpaid)

        self._save_state()
        self.event_bus.emit(EventType.TASK_UPDATED, task)
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

    def mark_task_reported_with_earning(
        self,
        task_id: str,
        amount: float,
        earned_at: Optional[str] = None,
        note: str = "",
        reported_at: Optional[str] = None,
    ) -> Tuple[Task, EarningEntry]:
        """Record earnings for a task and mark its logged time as reported."""
        if task_id not in self.state.tasks:
            raise KeyError(f"Task with id '{task_id}' not found.")
        task = self.state.tasks[task_id]
        if task.is_unpaid:
            raise ValueError("Cannot mark unreported time for an unpaid task.")

        earning_entry = self.add_earning(
            task_id=task_id,
            amount=amount,
            earned_at=earned_at,
            note=note,
        )
        cutoff = reported_at or iso_now()
        task = self.mark_task_reported(task_id=task_id, reported_at=cutoff)
        return task, earning_entry

    def get_task_unreported_duration(self, task_id: str, include_running: bool = True) -> float:
        """Calculate total unreported duration in seconds for a task, optionally including active session."""
        if task_id not in self.state.tasks:
            return 0.0

        task = self.state.tasks[task_id]
        if task.is_unpaid:
            return 0.0

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

    def update_current_session_start(self, new_start_time: str) -> None:
        """Update the start timestamp of the currently running session."""
        if not self.state.is_running or not self.state.current_session_start:
            raise ValueError("Cannot update session start time: timer is not running.")
        parsed_dt = parse_iso(new_start_time.replace(" ", "T"))
        if parsed_dt > datetime.now():
            raise ValueError("Session start time cannot be in the future.")
        self.state.current_session_start = parsed_dt.isoformat()
        self._save_state()
        self.event_bus.emit(
            EventType.ENTRY_UPDATED,
            {
                "type": "active_session",
                "start_time": self.state.current_session_start,
                "task": self.get_active_task(),
            },
        )

    def update_time_entry(
        self,
        task_id: str,
        entry_id: str,
        start_time: str,
        end_time: Optional[str] = None,
    ) -> TimeEntry:
        """Update an existing completed time entry's start/end timestamps and recalculate duration."""
        if task_id not in self.state.tasks:
            raise KeyError(f"Task with id '{task_id}' not found.")
        task = self.state.tasks[task_id]
        entry = next((e for e in task.entries if e.id == entry_id), None)
        if not entry:
            raise KeyError(f"TimeEntry with id '{entry_id}' not found in task '{task_id}'.")

        start_dt = parse_iso(start_time.replace(" ", "T"))
        iso_start = start_dt.isoformat()
        iso_end = None
        duration = 0.0

        if end_time:
            end_dt = parse_iso(end_time.replace(" ", "T"))
            if end_dt < start_dt:
                raise ValueError("End time cannot be earlier than start time.")
            iso_end = end_dt.isoformat()
            duration = max(0.0, (end_dt - start_dt).total_seconds())

        entry.start_time = iso_start
        entry.end_time = iso_end
        entry.duration_seconds = duration

        self._save_state()
        self.event_bus.emit(
            EventType.ENTRY_UPDATED,
            {"task_id": task_id, "entry": entry, "task": task},
        )
        return entry

    def add_manual_time_entry(
        self, task_id: str, start_time: str, end_time: str
    ) -> TimeEntry:
        """Manually create and insert a completed time entry for a task."""
        if task_id not in self.state.tasks:
            raise KeyError(f"Task with id '{task_id}' not found.")
        start_dt = parse_iso(start_time.replace(" ", "T"))
        end_dt = parse_iso(end_time.replace(" ", "T"))
        if end_dt < start_dt:
            raise ValueError("End time cannot be earlier than start time.")
        entry = TimeEntry(
            id=f"entry_{uuid.uuid4().hex[:8]}",
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            duration_seconds=max(0.0, (end_dt - start_dt).total_seconds()),
        )
        self.state.tasks[task_id].entries.append(entry)
        self._save_state()
        self.event_bus.emit(
            EventType.ENTRY_UPDATED,
            {"task_id": task_id, "entry": entry, "task": self.state.tasks[task_id]},
        )
        return entry

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

    def add_earning(
        self,
        task_id: str,
        amount: float,
        earned_at: Optional[str] = None,
        note: str = "",
    ) -> EarningEntry:
        """Record earnings for a task."""
        if task_id not in self.state.tasks:
            raise KeyError(f"Task with id '{task_id}' not found.")
        if float(amount) <= 0:
            raise ValueError("Earnings amount must be greater than zero.")

        if earned_at is None:
            earned_at_str = iso_now()
        else:
            clean_date = earned_at.strip().replace(" ", "T")
            parsed_dt = parse_iso(clean_date)
            earned_at_str = parsed_dt.isoformat()

        earning_id = f"earning_{uuid.uuid4().hex[:8]}"
        entry = EarningEntry(
            id=earning_id,
            task_id=task_id,
            amount=float(amount),
            earned_at=earned_at_str,
            note=note.strip(),
        )
        self.storage.add_earning(entry)
        self.event_bus.emit(
            EventType.EARNING_ADDED,
            {"earning": entry, "task": self.get_task(task_id)},
        )
        return entry

    def delete_earning(self, earning_id: str) -> None:
        """Delete an earnings entry."""
        self.storage.delete_earning(earning_id)
        self.event_bus.emit(EventType.EARNING_DELETED, {"earning_id": earning_id})

    def get_earnings(self, task_id: Optional[str] = None) -> List[EarningEntry]:
        """Retrieve earnings list, optionally filtered by task_id."""
        return self.storage.get_earnings(task_id=task_id)

    def get_monthly_goal(self, month_key: Optional[str] = None) -> MonthlyGoal:
        """Get monthly goal configuration for given month (defaults to current month YYYY-MM)."""
        key = month_key or datetime.now().strftime("%Y-%m")
        return self.storage.get_monthly_goal(key)

    def set_monthly_goal(
        self,
        goal_amount: float,
        use_28_day_month: bool = False,
        month_key: Optional[str] = None,
    ) -> MonthlyGoal:
        """Set monthly goal configuration."""
        if float(goal_amount) < 0:
            raise ValueError("Monthly goal amount cannot be negative.")
        key = month_key or datetime.now().strftime("%Y-%m")
        goal = MonthlyGoal(
            month_key=key,
            goal_amount=float(goal_amount),
            use_28_day_month=bool(use_28_day_month),
        )
        self.storage.set_monthly_goal(goal)
        self.event_bus.emit(EventType.GOAL_UPDATED, goal)
        return goal

    def get_earnings_stats(self, as_of: Optional[datetime] = None) -> EarningsPeriodStats:
        """Compute aggregated earnings and goal progress statistics."""
        now_dt = as_of if as_of is not None else datetime.now()
        month_key = now_dt.strftime("%Y-%m")
        goal = self.get_monthly_goal(month_key)

        bounds = get_period_bounds(now_dt)
        day_start = bounds["day"]
        day_end = day_start + timedelta(days=1)
        week_start = bounds["week"]
        week_end = week_start + timedelta(days=7)
        month_start = bounds["month"]
        _, num_days_in_month = calendar.monthrange(now_dt.year, now_dt.month)
        month_end = month_start + timedelta(days=num_days_in_month)

        day_total = 0.0
        week_total = 0.0
        month_total = 0.0

        all_earnings = self.get_earnings()
        for e in all_earnings:
            try:
                e_dt = parse_iso(e.earned_at.replace(" ", "T"))
                if day_start <= e_dt < day_end:
                    day_total += e.amount
                if week_start <= e_dt < week_end:
                    week_total += e.amount
                if month_start <= e_dt < month_end:
                    month_total += e.amount
            except Exception:
                pass

        goal_amount = goal.goal_amount
        use_28_day_month = goal.use_28_day_month

        target_days = 28 if use_28_day_month else num_days_in_month
        current_day = now_dt.day

        if use_28_day_month:
            if current_day <= 28:
                remaining_days = max(1, 28 - current_day + 1)
            else:
                remaining_days = 1
        else:
            if current_day <= num_days_in_month:
                remaining_days = max(1, num_days_in_month - current_day + 1)
            else:
                remaining_days = 1

        if goal_amount > 0:
            remaining_goal = max(0.0, goal_amount - month_total)
            needed_per_day = remaining_goal / remaining_days if remaining_goal > 0 else 0.0
            daily_target = goal_amount / float(target_days)
            weekly_target = daily_target * 7.0
            month_progress_pct = (month_total / goal_amount) * 100.0
            day_progress_pct = (day_total / daily_target) * 100.0 if daily_target > 0 else 0.0
            week_progress_pct = (week_total / weekly_target) * 100.0 if weekly_target > 0 else 0.0

            day_of_week = now_dt.weekday() + 1
            week_pace_pct = (day_of_week / 7.0) * 100.0
            week_expected_total = weekly_target * (day_of_week / 7.0)

            effective_month_day = min(current_day, target_days)
            month_pace_pct = (effective_month_day / float(target_days)) * 100.0
            month_expected_total = daily_target * effective_month_day
        else:
            needed_per_day = 0.0
            day_progress_pct = 0.0
            week_progress_pct = 0.0
            month_progress_pct = 0.0
            week_pace_pct = 0.0
            month_pace_pct = 0.0
            week_expected_total = 0.0
            month_expected_total = 0.0

        return EarningsPeriodStats(
            day_total=day_total,
            week_total=week_total,
            month_total=month_total,
            goal_amount=goal_amount,
            needed_per_day=needed_per_day,
            use_28_day_month=use_28_day_month,
            day_progress_pct=day_progress_pct,
            week_progress_pct=week_progress_pct,
            month_progress_pct=month_progress_pct,
            week_pace_pct=week_pace_pct,
            month_pace_pct=month_pace_pct,
            week_expected_total=week_expected_total,
            month_expected_total=month_expected_total,
        )

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

    def consolidate_tasks_by_name(self) -> Dict[str, int]:
        """
        Consolidate all tasks sharing the same name into a single task.

        Returns:
            dict: {"groups_consolidated": int, "tasks_merged": int, "tasks_removed": int}
        """
        groups: Dict[str, List[Task]] = {}
        for task in self.state.tasks.values():
            key = task.name.strip()
            groups.setdefault(key, []).append(task)

        duplicate_groups = [g for g in groups.values() if len(g) > 1]
        if not duplicate_groups:
            return {"groups_consolidated": 0, "tasks_merged": 0, "tasks_removed": 0}

        groups_consolidated = 0
        tasks_merged = 0
        tasks_removed = 0

        for group in duplicate_groups:
            # Sort by created_at (earliest first), using id as tie-breaker
            sorted_group = sorted(group, key=lambda t: (t.created_at or "", t.id))
            primary_task = sorted_group[0]
            secondary_tasks = sorted_group[1:]
            old_task_ids = [t.id for t in secondary_tasks]

            # 1. Merge time entries and sort chronologically by start_time
            all_entries: List[TimeEntry] = []
            for t in group:
                all_entries.extend(t.entries)
            all_entries.sort(key=lambda e: e.start_time or "")
            primary_task.entries = all_entries

            # 2. Consolidate metadata
            created_timestamps = [t.created_at for t in group if t.created_at]
            if created_timestamps:
                primary_task.created_at = min(created_timestamps)

            reported_timestamps = [t.last_reported_at for t in group if t.last_reported_at]
            primary_task.last_reported_at = max(reported_timestamps) if reported_timestamps else None

            # Unpaid only if all duplicates are unpaid
            primary_task.is_unpaid = all(t.is_unpaid for t in group)

            # Archived only if all duplicates are archived
            primary_task.is_archived = all(t.is_archived for t in group)

            # 3. Reassign storage data (earnings and time entries)
            self.storage.reassign_task_data(old_task_ids, primary_task.id)

            # 4. If active_task_id was one of the secondary tasks, point to primary_task
            if self.state.active_task_id in old_task_ids:
                self.state.active_task_id = primary_task.id

            # 5. Remove secondary tasks from state
            for t in secondary_tasks:
                if t.id in self.state.tasks:
                    del self.state.tasks[t.id]

            groups_consolidated += 1
            tasks_merged += len(group)
            tasks_removed += len(secondary_tasks)

        self._save_state()
        summary = {
            "groups_consolidated": groups_consolidated,
            "tasks_merged": tasks_merged,
            "tasks_removed": tasks_removed,
        }
        self.event_bus.emit(EventType.TASKS_CONSOLIDATED, summary)
        return summary
