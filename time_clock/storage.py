"""Storage persistence handlers for Time Clock (SQLite backend)."""
from __future__ import annotations

import abc
import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, Optional, Union

from time_clock.models import AppState, Task, TimeEntry

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
                    is_archived INTEGER NOT NULL DEFAULT 0
                );
            """)
            # Check for column migration on existing databases
            cursor = conn.execute("PRAGMA table_info(tasks);")
            columns = {row["name"] for row in cursor.fetchall()}
            if "last_reported_at" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN last_reported_at TEXT;")
            if "is_archived" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;")

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
                    "SELECT id, name, created_at, last_reported_at, is_archived FROM tasks ORDER BY created_at ASC;"
                )
                tasks: Dict[str, Task] = {}
                for row in tasks_cursor.fetchall():
                    tasks[row["id"]] = Task(
                        id=row["id"],
                        name=row["name"],
                        created_at=row["created_at"],
                        last_reported_at=row["last_reported_at"],
                        is_archived=bool(row["is_archived"]),
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
                    INSERT INTO tasks (id, name, created_at, last_reported_at, is_archived)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        created_at = excluded.created_at,
                        last_reported_at = excluded.last_reported_at,
                        is_archived = excluded.is_archived;
                    """,
                    (task.id, task.name, task.created_at, task.last_reported_at, 1 if task.is_archived else 0),
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

    def close(self) -> None:
        """Close resources."""
        pass
