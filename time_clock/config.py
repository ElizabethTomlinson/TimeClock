"""Configuration management for Time Clock application."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("~/.config/time_clock/config.json")
FALLBACK_CONFIG_PATH = Path("~/Library/Application Support/TimeClock/config.json")
DEFAULT_DB_PATH = Path("~/Library/Application Support/TimeClock/time_clock.db")


@dataclass
class AppConfig:
    """Application runtime configuration."""

    db_path: Path

    def __post_init__(self) -> None:
        if isinstance(self.db_path, str):
            self.db_path = Path(self.db_path)
        self.db_path = self.db_path.expanduser().resolve()

    def to_dict(self) -> Dict[str, str]:
        """Serialize configuration to a dictionary."""
        return {"db_path": str(self.db_path)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppConfig:
        """Construct AppConfig from a dictionary."""
        raw_db = data.get(
            "db_path",
            "~/Library/Application Support/TimeClock/time_clock.db",
        )
        return cls(db_path=Path(str(raw_db)).expanduser().resolve())


def get_default_config_path() -> Path:
    """Determine the default configuration file location."""
    env_config = os.environ.get("TIME_CLOCK_CONFIG")
    if env_config:
        return Path(env_config).expanduser().resolve()

    primary_path = DEFAULT_CONFIG_PATH.expanduser().resolve()
    if primary_path.exists():
        return primary_path

    fallback_path = FALLBACK_CONFIG_PATH.expanduser().resolve()
    if fallback_path.exists():
        return fallback_path

    return primary_path


def load_config(
    config_path: Optional[Union[str, Path]] = None,
    auto_create: bool = True,
) -> AppConfig:
    """Load application configuration from file or create default configuration if missing."""
    target_path = (
        Path(config_path).expanduser().resolve()
        if config_path is not None
        else get_default_config_path()
    )

    config: Optional[AppConfig] = None

    if target_path.exists():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                config = AppConfig.from_dict(data)
            else:
                logger.warning(
                    "Config file at %s does not contain a JSON object. Using defaults.",
                    target_path,
                )
        except Exception as e:
            logger.warning(
                "Failed to parse config file at %s: %s. Falling back to defaults.",
                target_path,
                e,
            )

    if config is None:
        default_db = DEFAULT_DB_PATH.expanduser().resolve()
        config = AppConfig(db_path=default_db)
        if auto_create:
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {"db_path": "~/Library/Application Support/TimeClock/time_clock.db"},
                        f,
                        indent=2,
                    )
                    f.write("\n")
                logger.info("Created default configuration at %s", target_path)
            except Exception as e:
                logger.warning(
                    "Could not write default configuration to %s: %s",
                    target_path,
                    e,
                )

    # Check for direct database override via environment variable
    env_db = os.environ.get("TIME_CLOCK_DB")
    if env_db:
        config.db_path = Path(env_db).expanduser().resolve()

    return config


def save_config(
    config: AppConfig,
    config_path: Optional[Union[str, Path]] = None,
) -> None:
    """Save configuration to JSON file."""
    target_path = (
        Path(config_path).expanduser().resolve()
        if config_path is not None
        else get_default_config_path()
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2)
        f.write("\n")
