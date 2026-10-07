"""Unit tests for configuration management and database path resolution."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from time_clock.config import (
    DEFAULT_DB_PATH,
    AppConfig,
    get_default_config_path,
    load_config,
    save_config,
)


class TestConfig(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.original_env_config = os.environ.get("TIME_CLOCK_CONFIG")
        self.original_env_db = os.environ.get("TIME_CLOCK_DB")
        if "TIME_CLOCK_CONFIG" in os.environ:
            del os.environ["TIME_CLOCK_CONFIG"]
        if "TIME_CLOCK_DB" in os.environ:
            del os.environ["TIME_CLOCK_DB"]

    def tearDown(self) -> None:
        if self.original_env_config is not None:
            os.environ["TIME_CLOCK_CONFIG"] = self.original_env_config
        elif "TIME_CLOCK_CONFIG" in os.environ:
            del os.environ["TIME_CLOCK_CONFIG"]

        if self.original_env_db is not None:
            os.environ["TIME_CLOCK_DB"] = self.original_env_db
        elif "TIME_CLOCK_DB" in os.environ:
            del os.environ["TIME_CLOCK_DB"]

        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_config_generation(self) -> None:
        custom_config_path = self.test_dir / "time_clock" / "config.json"
        self.assertFalse(custom_config_path.exists())

        config = load_config(config_path=custom_config_path, auto_create=True)
        self.assertTrue(custom_config_path.exists())
        self.assertEqual(config.db_path, DEFAULT_DB_PATH.expanduser().resolve())

        with open(custom_config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("db_path", data)
        self.assertEqual(data["db_path"], "~/Library/Application Support/TimeClock/time_clock.db")

    def test_load_custom_config(self) -> None:
        custom_config_path = self.test_dir / "custom_config.json"
        target_db = self.test_dir / "data" / "custom_time_clock.db"
        with open(custom_config_path, "w", encoding="utf-8") as f:
            json.dump({"db_path": str(target_db)}, f)

        config = load_config(config_path=custom_config_path)
        self.assertEqual(config.db_path, target_db.resolve())

    def test_tilde_path_expansion(self) -> None:
        app_config = AppConfig.from_dict({"db_path": "~/Documents/my_clock.db"})
        expected = (Path.home() / "Documents" / "my_clock.db").resolve()
        self.assertEqual(app_config.db_path, expected)

    def test_invalid_json_fallback(self) -> None:
        corrupted_path = self.test_dir / "corrupted.json"
        with open(corrupted_path, "w", encoding="utf-8") as f:
            f.write("{invalid json content")

        config = load_config(config_path=corrupted_path, auto_create=False)
        self.assertEqual(config.db_path, DEFAULT_DB_PATH.expanduser().resolve())

    def test_non_dict_json_fallback(self) -> None:
        array_path = self.test_dir / "array.json"
        with open(array_path, "w", encoding="utf-8") as f:
            f.write('["db_path", "other"]')

        config = load_config(config_path=array_path, auto_create=False)
        self.assertEqual(config.db_path, DEFAULT_DB_PATH.expanduser().resolve())

    def test_environment_variable_override_config_path(self) -> None:
        env_config_path = self.test_dir / "env_config.json"
        target_db = self.test_dir / "env_time_clock.db"
        with open(env_config_path, "w", encoding="utf-8") as f:
            json.dump({"db_path": str(target_db)}, f)

        os.environ["TIME_CLOCK_CONFIG"] = str(env_config_path)
        self.assertEqual(get_default_config_path(), env_config_path.resolve())

        config = load_config()
        self.assertEqual(config.db_path, target_db.resolve())

    def test_environment_variable_override_db_path(self) -> None:
        custom_config_path = self.test_dir / "config.json"
        with open(custom_config_path, "w", encoding="utf-8") as f:
            json.dump({"db_path": "~/some_db.db"}, f)

        override_db = self.test_dir / "direct_override.db"
        os.environ["TIME_CLOCK_DB"] = str(override_db)

        config = load_config(config_path=custom_config_path)
        self.assertEqual(config.db_path, override_db.resolve())

    def test_save_config_roundtrip(self) -> None:
        config_path = self.test_dir / "save_test.json"
        target_db = self.test_dir / "save_test.db"
        config = AppConfig(db_path=target_db)
        save_config(config, config_path=config_path)

        self.assertTrue(config_path.exists())
        loaded = load_config(config_path=config_path, auto_create=False)
        self.assertEqual(loaded.db_path, target_db.resolve())


if __name__ == "__main__":
    unittest.main()
