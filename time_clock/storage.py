"""Storage persistence handlers for Time Clock (SQLite backend)."""
from __future__ import annotations

import abc
import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, List, Optional, Union

from time_clock.models import AppState, EarningEntry, MonthlyGoal, Task, TimeEntry

logger = logging.getLogger(__name__)


class Storage(abc.ABC):
    """Abstract base storage interface for persisting and retrieving application state."""

    @abc.abstractmethod
    def load(self) -> AppState:
        """Load and deserialize AppState from storage backend."""
        pass

    @abc.abstractmethod
    def save(self, state: AppState) -> None:
        """Persist AppState to storage backend."""
        pass

    def get_earnings(self, task_id: Optional[str] = None) -> List[EarningEntry]:
        """Retrieve earnings records, optionally filtered by task_id."""
        return []

    def add_earning(self, entry: EarningEntry) -> None:
        """Save or insert an earning entry."""
        pass

    def delete_earning(self, earning_id: str) -> None:
        """Delete an earning entry by ID."""
        pass

    def get_monthly_goal(self, month_key: str) -> MonthlyGoal:
        """Retrieve monthly goal configuration for given month (YYYY-MM)."""
        return MonthlyGoal(month_key=month_key)

    def set_monthly_goal(self, goal: MonthlyGoal) -> None:
        """Persist monthly goal configuration."""
        pass

    def close(self) -> None:
        """Close any open connections or file handles."""
        pass

    def export_data(
        self,
        file_path: Union[str, Path],
        format: str = "csv",
        task_id: Optional[str] = None,
    ) -> None:
        """Export current tracking data to specified file format (csv or json)."""
        from time_clock.export import export_to_csv, export_to_json

        state = self.load()
        fmt = format.strip().lower()
        if fmt == "csv":
            export_to_csv(state, file_path, task_id=task_id)
        elif fmt == "json":
            export_to_json(state, file_path)
        else:
            raise ValueError(f"Unsupported export format: {format}")


class SQLiteStorage(Storage):
    """Manages persistence of application state in a local SQLite database."""

    def __init__(
        self,
        db_path: Union[str, Path] = "data/time_clock.db",
        migration_json_path: Optional[Union[str, Path]] = "data/time_clock_data.json",
    ) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.migration_json_path = (
            Path(migration_json_path).resolve() if migration_json_path else None
        )
        self._init_db()
        self._check_and_run_migration()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding an active SQLite connection, managing transaction and closing."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize relational database tables and indexes."""
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_reported_at TEXT,
                    is_archived INTEGER NOT NULL DEFAULT 0,
                    is_unpaid INTEGER NOT NULL DEFAULT 0
                );
            """)
            # Check for column migration on existing databases
            cursor = conn.execute("PRAGMA table_info(tasks);")
            columns = {row["name"] for row in cursor.fetchall()}
            if "last_reported_at" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN last_reported_at TEXT;")
            if "is_archived" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;")
            if "is_unpaid" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN is_unpaid INTEGER NOT NULL DEFAULT 0;")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS time_entries (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_seconds REAL NOT NULL DEFAULT 0.0,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    active_task_id TEXT,
                    is_running INTEGER NOT NULL DEFAULT 0,
                    current_session_start TEXT,
                    FOREIGN KEY (active_task_id) REFERENCES tasks(id) ON DELETE SET NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS earnings (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    earned_at TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS monthly_goals (
                    month_key TEXT PRIMARY KEY,
                    goal_amount REAL NOT NULL DEFAULT 0.0,
                    use_28_day_month INTEGER NOT NULL DEFAULT 0
                );
            """)

    def _check_and_run_migration(self) -> None:
        """Migrate legacy JSON data if database is empty and JSON data file exists."""
        if not self.migration_json_path or not self.migration_json_path.exists():
            return

        try:
            with self._connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM tasks;")
                task_count = cursor.fetchone()[0]
                if task_count > 0:
                    return

            with open(self.migration_json_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return
                data = json.loads(content)
                if not isinstance(data, dict):
                    return
                legacy_state = AppState.from_dict(data)

            if legacy_state.tasks or legacy_state.active_task_id or legacy_state.is_running:
                self.save(legacy_state)
                logger.info(
                    "Successfully migrated legacy state from %s to SQLite database %s",
                    self.migration_json_path,
                    self.db_path,
                )
        except Exception as e:
            logger.warning("Failed to migrate legacy JSON data: %s", e)

    def load(self) -> AppState:
        """Load and deserialize AppState from the SQLite database."""
        try:
            with self._connection() as conn:
                tasks_cursor = conn.execute(
                    "SELECT id, name, created_at, last_reported_at, is_archived, is_unpaid FROM tasks ORDER BY created_at ASC;"
                )
                tasks: Dict[str, Task] = {}
                for row in tasks_cursor.fetchall():
                    tasks[row["id"]] = Task(
                        id=row["id"],
                        name=row["name"],
                        created_at=row["created_at"],
                        last_reported_at=row["last_reported_at"],
                        is_archived=bool(row["is_archived"]),
                        is_unpaid=bool(row["is_unpaid"]),
                        entries=[],
                    )

                entries_cursor = conn.execute(
                    "SELECT id, task_id, start_time, end_time, duration_seconds "
                    "FROM time_entries ORDER BY start_time ASC;"
                )
                for row in entries_cursor.fetchall():
                    task_id = row["task_id"]
                    if task_id in tasks:
                        entry = TimeEntry(
                            id=row["id"],
                            start_time=row["start_time"],
                            end_time=row["end_time"],
                            duration_seconds=float(row["duration_seconds"]),
                        )
                        tasks[task_id].entries.append(entry)

                state_cursor = conn.execute(
                    "SELECT active_task_id, is_running, current_session_start "
                    "FROM app_state WHERE key = 'current';"
                )
                state_row = state_cursor.fetchone()
                active_task_id = None
                is_running = False
                current_session_start = None

                if state_row:
                    active_task_id = state_row["active_task_id"]
                    if active_task_id and active_task_id not in tasks:
                        active_task_id = None
                    is_running = bool(state_row["is_running"])
                    current_session_start = state_row["current_session_start"]
                elif tasks:
                    active_task_id = next(iter(tasks.keys()))

                return AppState(
                    tasks=tasks,
                    active_task_id=active_task_id,
                    is_running=is_running,
                    current_session_start=current_session_start,
                )
        except sqlite3.Error as e:
            logger.warning("Database error loading state from %s: %s; returning empty state", self.db_path, e)
            return AppState()

    def save(self, state: AppState) -> None:
        """Persist AppState to the SQLite database within a transaction."""
        with self._connection() as conn:
            # 1. Sync tasks
            existing_tasks_cursor = conn.execute("SELECT id FROM tasks;")
            existing_task_ids = {row["id"] for row in existing_tasks_cursor.fetchall()}
            current_task_ids = set(state.tasks.keys())

            # Delete removed tasks (cascades to their time_entries)
            tasks_to_delete = existing_task_ids - current_task_ids
            if tasks_to_delete:
                placeholders = ",".join("?" * len(tasks_to_delete))
                conn.execute(f"DELETE FROM tasks WHERE id IN ({placeholders});", list(tasks_to_delete))

            # Upsert tasks and sync time entries
            for task in state.tasks.values():
                conn.execute(
                    """
                    INSERT INTO tasks (id, name, created_at, last_reported_at, is_archived, is_unpaid)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        created_at = excluded.created_at,
                        last_reported_at = excluded.last_reported_at,
                        is_archived = excluded.is_archived,
                        is_unpaid = excluded.is_unpaid;
                    """,
                    (task.id, task.name, task.created_at, task.last_reported_at, 1 if task.is_archived else 0, 1 if task.is_unpaid else 0),
                )

                # Sync entries for this task
                current_entry_ids = {entry.id for entry in task.entries}
                existing_entries_cursor = conn.execute(
                    "SELECT id FROM time_entries WHERE task_id = ?;", (task.id,)
                )
                existing_entry_ids = {row["id"] for row in existing_entries_cursor.fetchall()}

                entries_to_delete = existing_entry_ids - current_entry_ids
                if entries_to_delete:
                    placeholders = ",".join("?" * len(entries_to_delete))
                    conn.execute(
                        f"DELETE FROM time_entries WHERE task_id = ? AND id IN ({placeholders});",
                        [task.id, *list(entries_to_delete)],
                    )

                for entry in task.entries:
                    conn.execute(
                        """
                        INSERT INTO time_entries (id, task_id, start_time, end_time, duration_seconds)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            start_time = excluded.start_time,
                            end_time = excluded.end_time,
                            duration_seconds = excluded.duration_seconds;
                        """,
                        (entry.id, task.id, entry.start_time, entry.end_time, entry.duration_seconds),
                    )

            # 2. Upsert app_state
            conn.execute(
                """
                INSERT INTO app_state (key, active_task_id, is_running, current_session_start)
                VALUES ('current', ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    active_task_id = excluded.active_task_id,
                    is_running = excluded.is_running,
                    current_session_start = excluded.current_session_start;
                """,
                (
                    state.active_task_id,
                    1 if state.is_running else 0,
                    state.current_session_start,
                ),
            )

    def get_earnings(self, task_id: Optional[str] = None) -> List[EarningEntry]:
        """Retrieve earnings entries ordered by earned_at descending, optionally filtered by task_id."""
        with self._connection() as conn:
            if task_id:
                cursor = conn.execute(
                    "SELECT id, task_id, amount, earned_at, note FROM earnings WHERE task_id = ? ORDER BY earned_at DESC, id DESC;",
                    (task_id,),
                )
            else:
                cursor = conn.execute(
                    "SELECT id, task_id, amount, earned_at, note FROM earnings ORDER BY earned_at DESC, id DESC;"
                )
            return [
                EarningEntry(
                    id=row["id"],
                    task_id=row["task_id"],
                    amount=float(row["amount"]),
                    earned_at=row["earned_at"],
                    note=row["note"] or "",
                )
                for row in cursor.fetchall()
            ]

    def add_earning(self, entry: EarningEntry) -> None:
        """Insert or replace an earning entry."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO earnings (id, task_id, amount, earned_at, note)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    task_id = excluded.task_id,
                    amount = excluded.amount,
                    earned_at = excluded.earned_at,
                    note = excluded.note;
                """,
                (entry.id, entry.task_id, entry.amount, entry.earned_at, entry.note),
            )

    def delete_earning(self, earning_id: str) -> None:
        """Delete an earning entry by ID."""
        with self._connection() as conn:
            conn.execute("DELETE FROM earnings WHERE id = ?;", (earning_id,))

    def get_monthly_goal(self, month_key: str) -> MonthlyGoal:
        """Retrieve monthly goal for specified month (YYYY-MM)."""
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT month_key, goal_amount, use_28_day_month FROM monthly_goals WHERE month_key = ?;",
                (month_key,),
            )
            row = cursor.fetchone()
            if row:
                return MonthlyGoal(
                    month_key=row["month_key"],
                    goal_amount=float(row["goal_amount"]),
                    use_28_day_month=bool(row["use_28_day_month"]),
                )
            return MonthlyGoal(month_key=month_key, goal_amount=0.0, use_28_day_month=False)

    def set_monthly_goal(self, goal: MonthlyGoal) -> None:
        """Upsert monthly goal configuration."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO monthly_goals (month_key, goal_amount, use_28_day_month)
                VALUES (?, ?, ?)
                ON CONFLICT(month_key) DO UPDATE SET
                    goal_amount = excluded.goal_amount,
                    use_28_day_month = excluded.use_28_day_month;
                """,
                (goal.month_key, goal.goal_amount, 1 if goal.use_28_day_month else 0),
            )

    def close(self) -> None:
        """Close resources."""
        pass
