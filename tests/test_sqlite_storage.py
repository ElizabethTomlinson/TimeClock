"""Unit tests for SQLiteStorage backend and legacy JSON migration."""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from time_clock.models import AppState, Task, TimeEntry
from time_clock.storage import SQLiteStorage


class TestSQLiteStorage(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.db_path = self.test_dir / "subdir" / "time_clock.db"
        self.json_path = self.test_dir / "legacy_data.json"
        self.storage = SQLiteStorage(
            db_path=self.db_path,
            migration_json_path=self.json_path,
        )

    def tearDown(self):
        self.storage.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_init_db_creates_tables(self):
        self.assertTrue(self.db_path.exists())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            )
            tables = {row[0] for row in cursor.fetchall()}
            self.assertIn("tasks", tables)
            self.assertIn("time_entries", tables)
            self.assertIn("app_state", tables)

    def test_load_empty_database(self):
        state = self.storage.load()
        self.assertIsInstance(state, AppState)
        self.assertEqual(len(state.tasks), 0)
        self.assertIsNone(state.active_task_id)
        self.assertFalse(state.is_running)
        self.assertIsNone(state.current_session_start)

    def test_save_and_load_round_trip(self):
        task1 = Task(
            id="t1",
            name="Backend Architecture",
            created_at="2026-09-30T09:00:00",
            entries=[
                TimeEntry(
                    id="e1",
                    start_time="2026-09-30T09:00:00",
                    end_time="2026-09-30T10:00:00",
                    duration_seconds=3600.0,
                ),
                TimeEntry(
                    id="e2",
                    start_time="2026-09-30T10:30:00",
                    end_time="2026-09-30T11:00:00",
                    duration_seconds=1800.0,
                ),
            ],
        )
        task2 = Task(
            id="t2",
            name="Documentation",
            created_at="2026-09-30T11:00:00",
            entries=[],
        )

        state = AppState(
            tasks={"t1": task1, "t2": task2},
            active_task_id="t1",
            is_running=True,
            current_session_start="2026-09-30T11:30:00",
        )

        self.storage.save(state)

        # Reload state from database
        loaded = self.storage.load()
        self.assertEqual(len(loaded.tasks), 2)
        self.assertEqual(loaded.active_task_id, "t1")
        self.assertTrue(loaded.is_running)
        self.assertEqual(loaded.current_session_start, "2026-09-30T11:30:00")

        self.assertEqual(loaded.tasks["t1"].name, "Backend Architecture")
        self.assertEqual(len(loaded.tasks["t1"].entries), 2)
        self.assertEqual(loaded.tasks["t1"].entries[0].id, "e1")
        self.assertEqual(loaded.tasks["t1"].entries[0].duration_seconds, 3600.0)
        self.assertEqual(loaded.tasks["t1"].entries[1].id, "e2")
        self.assertEqual(loaded.tasks["t1"].entries[1].duration_seconds, 1800.0)
        self.assertEqual(loaded.tasks["t1"].total_duration_seconds, 5400.0)

        self.assertEqual(loaded.tasks["t2"].name, "Documentation")
        self.assertEqual(len(loaded.tasks["t2"].entries), 0)

    def test_cascade_delete_tasks_and_entries(self):
        state = AppState(
            tasks={
                "t1": Task(
                    id="t1",
                    name="Task To Keep",
                    created_at="2026-09-30T09:00:00",
                    entries=[
                        TimeEntry(
                            id="e1",
                            start_time="2026-09-30T09:00:00",
                            end_time="2026-09-30T10:00:00",
                            duration_seconds=3600.0,
                        )
                    ],
                ),
                "t2": Task(
                    id="t2",
                    name="Task To Delete",
                    created_at="2026-09-30T10:00:00",
                    entries=[
                        TimeEntry(
                            id="e2",
                            start_time="2026-09-30T10:00:00",
                            end_time="2026-09-30T10:45:00",
                            duration_seconds=2700.0,
                        )
                    ],
                ),
            },
            active_task_id="t1",
        )
        self.storage.save(state)

        # Verify initial entries count in database
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM time_entries;").fetchone()[0]
            self.assertEqual(count, 2)

        # Delete t2 from state and save
        del state.tasks["t2"]
        self.storage.save(state)

        loaded = self.storage.load()
        self.assertEqual(len(loaded.tasks), 1)
        self.assertNotIn("t2", loaded.tasks)

        # Verify time_entries for t2 are cascade-deleted
        with sqlite3.connect(self.db_path) as conn:
            entry_count = conn.execute(
                "SELECT COUNT(*) FROM time_entries WHERE task_id = 't2';"
            ).fetchone()[0]
            self.assertEqual(entry_count, 0)
            total_entries = conn.execute("SELECT COUNT(*) FROM time_entries;").fetchone()[0]
            self.assertEqual(total_entries, 1)

    def test_legacy_json_migration_on_init(self):
        # Create a pre-populated legacy JSON file
        legacy_state = AppState(
            tasks={
                "legacy_t1": Task(
                    id="legacy_t1",
                    name="Migrated Task",
                    created_at="2026-09-30T08:00:00",
                    entries=[
                        TimeEntry(
                            id="legacy_e1",
                            start_time="2026-09-30T08:00:00",
                            end_time="2026-09-30T09:00:00",
                            duration_seconds=3600.0,
                        )
                    ],
                )
            },
            active_task_id="legacy_t1",
            is_running=False,
        )
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(legacy_state.to_dict(), f)

        # Instantiate SQLiteStorage pointing to a fresh DB and legacy JSON
        new_db_path = self.test_dir / "migrated.db"
        migrated_storage = SQLiteStorage(
            db_path=new_db_path,
            migration_json_path=self.json_path,
        )

        loaded = migrated_storage.load()
        self.assertEqual(len(loaded.tasks), 1)
        self.assertIn("legacy_t1", loaded.tasks)
        self.assertEqual(loaded.tasks["legacy_t1"].name, "Migrated Task")
        self.assertEqual(len(loaded.tasks["legacy_t1"].entries), 1)
        self.assertEqual(loaded.tasks["legacy_t1"].entries[0].id, "legacy_e1")
        self.assertEqual(loaded.active_task_id, "legacy_t1")

    def test_migration_skipped_when_db_has_data(self):
        # Existing DB has tasks
        initial_state = AppState(
            tasks={
                "db_t1": Task(
                    id="db_t1",
                    name="Existing DB Task",
                    created_at="2026-09-30T08:00:00",
                )
            },
            active_task_id="db_t1",
        )
        self.storage.save(initial_state)

        # JSON file with different task
        json_file = self.test_dir / "other_legacy.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(
                AppState(
                    tasks={
                        "json_t1": Task(
                            id="json_t1",
                            name="Should Not Migrate",
                            created_at="2026-09-30T08:00:00",
                        )
                    }
                ).to_dict(),
                f,
            )

        # Re-initialize storage with the non-empty DB
        reopened_storage = SQLiteStorage(
            db_path=self.db_path,
            migration_json_path=json_file,
        )
        loaded = reopened_storage.load()
        self.assertEqual(len(loaded.tasks), 1)
        self.assertIn("db_t1", loaded.tasks)
        self.assertNotIn("json_t1", loaded.tasks)

    def test_sqlite_save_and_load_last_reported_at(self):
        task = Task(
            id="t_reported",
            name="Reported Task",
            created_at="2026-10-01T08:00:00",
            last_reported_at="2026-10-01T12:00:00",
            entries=[
                TimeEntry(
                    id="e1",
                    start_time="2026-10-01T08:00:00",
                    end_time="2026-10-01T12:00:00",
                    duration_seconds=14400.0,
                )
            ],
        )
        state = AppState(tasks={"t_reported": task}, active_task_id="t_reported")
        self.storage.save(state)

        loaded = self.storage.load()
        self.assertEqual(loaded.tasks["t_reported"].last_reported_at, "2026-10-01T12:00:00")

    def test_sqlite_migration_adds_last_reported_at_column(self):
        # Create an old schema database without last_reported_at column
        legacy_db = self.test_dir / "old_schema.db"
        with sqlite3.connect(legacy_db) as conn:
            conn.execute("""
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE time_entries (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_seconds REAL NOT NULL DEFAULT 0.0,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );
            """)
            conn.execute("""
                CREATE TABLE app_state (
                    key TEXT PRIMARY KEY,
                    active_task_id TEXT,
                    is_running INTEGER NOT NULL DEFAULT 0,
                    current_session_start TEXT,
                    FOREIGN KEY (active_task_id) REFERENCES tasks(id) ON DELETE SET NULL
                );
            """)
            conn.execute("INSERT INTO tasks (id, name, created_at) VALUES ('t_old', 'Old Task', '2026-09-01T00:00:00');")
            conn.commit()

        # Open with SQLiteStorage which triggers column migration
        storage = SQLiteStorage(db_path=legacy_db)
        loaded = storage.load()
        self.assertIn("t_old", loaded.tasks)
        self.assertEqual(loaded.tasks["t_old"].name, "Old Task")
        self.assertIsNone(loaded.tasks["t_old"].last_reported_at)

        # Update last_reported_at and save
        loaded.tasks["t_old"].last_reported_at = "2026-09-01T10:00:00"
        storage.save(loaded)

        reloaded = storage.load()
        self.assertEqual(reloaded.tasks["t_old"].last_reported_at, "2026-09-01T10:00:00")
        storage.close()


if __name__ == "__main__":
    unittest.main()
