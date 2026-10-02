"""Data models for tasks, time entries, and application state."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def iso_now() -> str:
    """Return current local time as an ISO-8601 formatted string."""
    return datetime.now().isoformat()


def parse_iso(iso_str: str) -> datetime:
    """Parse an ISO-8601 formatted timestamp string."""
    return datetime.fromisoformat(iso_str)


def format_duration(seconds: float) -> str:
    """Format duration in seconds to HH:MM:SS string."""
    total_seconds = int(max(0, round(seconds)))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def get_period_bounds(as_of: Optional[datetime] = None) -> Dict[str, datetime]:
    """Calculate start boundary datetimes for current day, week (Monday), and month."""
    dt = as_of if as_of is not None else datetime.now()
    day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=dt.weekday())
    month_start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return {
        "day": day_start,
        "week": week_start,
        "month": month_start,
    }


def calculate_interval_overlap(
    start_dt: datetime,
    end_dt: datetime,
    window_start: datetime,
    window_end: datetime,
) -> float:
    """Calculate overlap duration in seconds between an interval [start_dt, end_dt] and a window [window_start, window_end]."""
    overlap_start = max(start_dt, window_start)
    overlap_end = min(end_dt, window_end)
    if overlap_end > overlap_start:
        return (overlap_end - overlap_start).total_seconds()
    return 0.0


@dataclass
class PeriodDurations:
    """Container for day, week, and month aggregate durations in seconds."""
    day: float = 0.0
    week: float = 0.0
    month: float = 0.0

    def formatted_dict(self) -> Dict[str, str]:
        return {
            "day": format_duration(self.day),
            "week": format_duration(self.week),
            "month": format_duration(self.month),
        }

    def to_dict(self) -> Dict[str, float]:
        return {
            "day": self.day,
            "week": self.week,
            "month": self.month,
        }


@dataclass
class TimeEntry:
    """Represents a single clocked-in time session."""
    id: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimeEntry:
        return cls(
            id=data.get("id", ""),
            start_time=data.get("start_time", ""),
            end_time=data.get("end_time"),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
        )


@dataclass
class Task:
    """Represents a work task containing multiple time entries."""
    id: str
    name: str
    created_at: str
    last_reported_at: Optional[str] = None
    is_archived: bool = False
    entries: List[TimeEntry] = field(default_factory=list)

    @property
    def total_duration_seconds(self) -> float:
        """Calculate total cumulative seconds spent on this task across finished entries."""
        return sum(entry.duration_seconds for entry in self.entries)

    def calculate_unreported_duration(self, as_of: Optional[str] = None) -> float:
        """Calculate seconds logged since the cutoff timestamp (or self.last_reported_at)."""
        cutoff_str = as_of if as_of is not None else self.last_reported_at
        if not cutoff_str:
            return self.total_duration_seconds
        cutoff_dt = parse_iso(cutoff_str)
        unreported = 0.0
        for entry in self.entries:
            if not entry.end_time:
                continue
            start_dt = parse_iso(entry.start_time)
            end_dt = parse_iso(entry.end_time)
            if end_dt <= cutoff_dt:
                continue
            effective_start = max(start_dt, cutoff_dt)
            unreported += max(0.0, (end_dt - effective_start).total_seconds())
        return unreported

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "last_reported_at": self.last_reported_at,
            "is_archived": self.is_archived,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        entries_data = data.get("entries", [])
        entries = [TimeEntry.from_dict(entry) for entry in entries_data]
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            created_at=data.get("created_at", ""),
            last_reported_at=data.get("last_reported_at"),
            is_archived=bool(data.get("is_archived", False)),
            entries=entries,
        )


@dataclass
class AppState:
    """Root application state storing tasks and active tracking status."""
    tasks: Dict[str, Task] = field(default_factory=dict)
    active_task_id: Optional[str] = None
    is_running: bool = False
    current_session_start: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks": {task_id: task.to_dict() for task_id, task in self.tasks.items()},
            "active_task_id": self.active_task_id,
            "is_running": self.is_running,
            "current_session_start": self.current_session_start,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppState:
        raw_tasks = data.get("tasks", {})
        tasks = {task_id: Task.from_dict(t_dict) for task_id, t_dict in raw_tasks.items()}
        return cls(
            tasks=tasks,
            active_task_id=data.get("active_task_id"),
            is_running=bool(data.get("is_running", False)),
            current_session_start=data.get("current_session_start"),
        )
