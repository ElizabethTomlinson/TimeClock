"""Data export functionality supporting CSV and JSON formats."""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from time_clock.models import AppState, Task

logger = logging.getLogger(__name__)

CSV_FIELDNAMES = [
    "task_id",
    "task_name",
    "task_created_at",
    "last_reported_at",
    "is_archived",
    "is_unpaid",
    "entry_id",
    "start_time",
    "end_time",
    "duration_seconds",
]


def export_to_csv(
    state: AppState,
    target_path: Union[str, Path],
    task_id: Optional[str] = None,
) -> None:
    """Export tasks and session logs to a CSV file.

    If task_id is provided, only that task's history is exported.
    """
    path = Path(target_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    tasks_to_export: List[Task] = []
    if task_id:
        if task_id in state.tasks:
            tasks_to_export.append(state.tasks[task_id])
    else:
        tasks_to_export = list(state.tasks.values())

    rows: List[Dict[str, Any]] = []
    for task in tasks_to_export:
        if not task.entries:
            rows.append({
                "task_id": task.id,
                "task_name": task.name,
                "task_created_at": task.created_at,
                "last_reported_at": task.last_reported_at or "",
                "is_archived": "true" if task.is_archived else "false",
                "is_unpaid": "true" if task.is_unpaid else "false",
                "entry_id": "",
                "start_time": "",
                "end_time": "",
                "duration_seconds": 0.0,
            })
        else:
            for entry in task.entries:
                rows.append({
                    "task_id": task.id,
                    "task_name": task.name,
                    "task_created_at": task.created_at,
                    "last_reported_at": task.last_reported_at or "",
                    "is_archived": "true" if task.is_archived else "false",
                    "is_unpaid": "true" if task.is_unpaid else "false",
                    "entry_id": entry.id,
                    "start_time": entry.start_time,
                    "end_time": entry.end_time or "",
                    "duration_seconds": entry.duration_seconds,
                })

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Exported %d records to CSV at %s", len(rows), path)


def export_to_json(
    state: AppState,
    target_path: Union[str, Path],
    task_id: Optional[str] = None,
) -> None:
    """Export tasks and session logs to a formatted JSON file.

    If task_id is provided, only that task is included.
    """
    path = Path(target_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    if task_id:
        filtered_tasks = (
            {task_id: state.tasks[task_id].to_dict()} if task_id in state.tasks else {}
        )
        data = {
            "tasks": filtered_tasks,
            "active_task_id": state.active_task_id if state.active_task_id == task_id else None,
            "is_running": state.is_running if state.active_task_id == task_id else False,
            "current_session_start": (
                state.current_session_start if state.active_task_id == task_id else None
            ),
        }
    else:
        data = state.to_dict()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("Exported state to JSON at %s", path)
