"""Unit tests for CSV and JSON data export functionality."""
import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from time_clock.engine import TimeClockEngine
from time_clock.export import CSV_FIELDNAMES, export_to_csv, export_to_json
from time_clock.models import AppState, Task, TimeEntry
from time_clock.storage import SQLiteStorage


class TestExport(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.state = AppState(
            tasks={
                "t1": Task(
                    id="t1",
                    name="Feature: Export Data, Reporting",
                    created_at="2026-09-30T10:00:00",
                    last_reported_at="2026-09-30T11:00:00",
                    entries=[
                        TimeEntry(
                            id="e1",
                            start_time="2026-09-30T10:00:00",
                            end_time="2026-09-30T11:00:00",
                            duration_seconds=3600.0,
                        ),
                        TimeEntry(
                            id="e2",
                            start_time="2026-09-30T11:30:00",
                            end_time="2026-09-30T12:00:00",
                            duration_seconds=1800.0,
                        ),
                    ],
                ),
                "t2": Task(
                    id="t2",
                    name="Bug Fixing",
                    created_at="2026-09-30T12:00:00",
                    entries=[],
                ),
            },
            active_task_id="t1",
            is_running=False,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_export_to_csv_full(self):
        target_path = self.test_dir / "exports" / "all_data.csv"
        export_to_csv(self.state, target_path)

        self.assertTrue(target_path.exists())
        with open(target_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        self.assertEqual(len(reader), 3)  # 2 entries for t1 + 1 blank row for t2
        self.assertEqual(reader[0]["task_id"], "t1")
        self.assertEqual(reader[0]["task_name"], "Feature: Export Data, Reporting")
        self.assertEqual(reader[0]["last_reported_at"], "2026-09-30T11:00:00")
        self.assertEqual(reader[0]["is_archived"], "false")
        self.assertEqual(reader[0]["entry_id"], "e1")
        self.assertEqual(float(reader[0]["duration_seconds"]), 3600.0)

        self.assertEqual(reader[1]["task_id"], "t1")
        self.assertEqual(reader[1]["last_reported_at"], "2026-09-30T11:00:00")
        self.assertEqual(reader[1]["is_archived"], "false")
        self.assertEqual(reader[1]["entry_id"], "e2")
        self.assertEqual(float(reader[1]["duration_seconds"]), 1800.0)

        self.assertEqual(reader[2]["task_id"], "t2")
        self.assertEqual(reader[2]["last_reported_at"], "")
        self.assertEqual(reader[2]["is_archived"], "false")
        self.assertEqual(reader[2]["entry_id"], "")
        self.assertEqual(float(reader[2]["duration_seconds"]), 0.0)

    def test_export_to_csv_filtered_by_task(self):
        target_path = self.test_dir / "t1_data.csv"
        export_to_csv(self.state, target_path, task_id="t1")

        with open(target_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        self.assertEqual(len(reader), 2)
        for row in reader:
            self.assertEqual(row["task_id"], "t1")

    def test_export_to_csv_empty_state(self):
        empty_state = AppState()
        target_path = self.test_dir / "empty.csv"
        export_to_csv(empty_state, target_path)

        with open(target_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        self.assertEqual(len(reader), 0)
        with open(target_path, "r", encoding="utf-8") as f:
            header_line = f.readline().strip()
        self.assertEqual(header_line, ",".join(CSV_FIELDNAMES))

    def test_export_includes_is_archived_flag(self):
        archived_state = AppState(
            tasks={
                "t_arch": Task(
                    id="t_arch",
                    name="Archived Milestone",
                    created_at="2026-08-01T10:00:00",
                    is_archived=True,
                    entries=[
                        TimeEntry(
                            id="e_arch_1",
                            start_time="2026-08-01T10:00:00",
                            end_time="2026-08-01T11:00:00",
                            duration_seconds=3600.0,
                        )
                    ],
                )
            }
        )
        csv_path = self.test_dir / "archived.csv"
        export_to_csv(archived_state, csv_path)
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        self.assertEqual(len(reader), 1)
        self.assertEqual(reader[0]["is_archived"], "true")

        json_path = self.test_dir / "archived.json"
        export_to_json(archived_state, json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertTrue(data["tasks"]["t_arch"]["is_archived"])

    def test_export_to_json_full(self):
        target_path = self.test_dir / "exports" / "all_data.json"
        export_to_json(self.state, target_path)

        self.assertTrue(target_path.exists())
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("tasks", data)
        self.assertEqual(len(data["tasks"]), 2)
        self.assertIn("t1", data["tasks"])
        self.assertEqual(data["tasks"]["t1"]["name"], "Feature: Export Data, Reporting")
        self.assertEqual(data["tasks"]["t1"]["last_reported_at"], "2026-09-30T11:00:00")
        self.assertEqual(len(data["tasks"]["t1"]["entries"]), 2)
        self.assertEqual(data["active_task_id"], "t1")

    def test_export_to_json_filtered_by_task(self):
        target_path = self.test_dir / "t2_data.json"
        export_to_json(self.state, target_path, task_id="t2")

        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(len(data["tasks"]), 1)
        self.assertIn("t2", data["tasks"])

    def test_engine_export_data_method(self):
        storage = SQLiteStorage(self.test_dir / "engine_test.db")
        storage.save(self.state)
        engine = TimeClockEngine(storage=storage)

        csv_path = self.test_dir / "engine_export.csv"
        engine.export_data(csv_path, format="csv")
        self.assertTrue(csv_path.exists())

        json_path = self.test_dir / "engine_export.json"
        engine.export_data(json_path, format="json")
        self.assertTrue(json_path.exists())

        with self.assertRaises(ValueError):
            engine.export_data(self.test_dir / "bad.xml", format="xml")

    def test_storage_export_data_method(self):
        storage = SQLiteStorage(self.test_dir / "storage_export.db")
        storage.save(self.state)

        csv_path = self.test_dir / "storage_export.csv"
        storage.export_data(csv_path, format="csv")
        self.assertTrue(csv_path.exists())

        json_path = self.test_dir / "storage_export.json"
        storage.export_data(json_path, format="json")
        self.assertTrue(json_path.exists())


if __name__ == "__main__":
    unittest.main()
