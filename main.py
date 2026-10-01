"""Time Clock Application entry point."""
from pathlib import Path

from time_clock.engine import TimeClockEngine
from time_clock.events import EventBus
from time_clock.gui.app import TimeClockApp
from time_clock.storage import SQLiteStorage


def main() -> None:
    """Initialize and run the Time Clock desktop application with SQLite backend."""
    db_file = Path("data/time_clock.db")
    storage = SQLiteStorage(db_file)
    event_bus = EventBus()
    engine = TimeClockEngine(storage=storage, event_bus=event_bus)

    app = TimeClockApp(engine=engine, storage=storage, event_bus=event_bus)
    app.run()


if __name__ == "__main__":
    main()
