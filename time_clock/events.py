"""Event bus definitions and event types for the Time Clock application."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List


class EventType(str, Enum):
    """Supported event types in the application."""
    TASK_CREATED = "TASK_CREATED"
    TASK_DELETED = "TASK_DELETED"
    TASK_SELECTED = "TASK_SELECTED"
    TASK_RENAMED = "TASK_RENAMED"
    TASK_UPDATED = "TASK_UPDATED"
    TASK_REPORTED = "TASK_REPORTED"
    TASK_ARCHIVED = "TASK_ARCHIVED"
    TASK_UNARCHIVED = "TASK_UNARCHIVED"
    CLOCK_IN = "CLOCK_IN"
    CLOCK_OUT = "CLOCK_OUT"
    TICK = "TICK"
    ENTRY_UPDATED = "ENTRY_UPDATED"
    EARNING_ADDED = "EARNING_ADDED"
    EARNING_DELETED = "EARNING_DELETED"
    GOAL_UPDATED = "GOAL_UPDATED"
    STATE_LOADED = "STATE_LOADED"
    STATE_SAVED = "STATE_SAVED"


@dataclass
class Event:
    """Represents an event dispatched on the EventBus."""
    type: EventType | str
    data: Any = None
    timestamp: float = field(default_factory=time.time)


class EventBus:
    """Publish-Subscribe Event Bus for decoupled communication."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = {}

    def _normalize_type(self, event_type: EventType | str) -> str:
        if isinstance(event_type, Enum):
            return event_type.value
        return str(event_type)

    def subscribe(self, event_type: EventType | str, handler: Callable[[Event], None]) -> None:
        """Subscribe a handler callback to a specific event type."""
        key = self._normalize_type(event_type)
        if key not in self._subscribers:
            self._subscribers[key] = []
        if handler not in self._subscribers[key]:
            self._subscribers[key].append(handler)

    def unsubscribe(self, event_type: EventType | str, handler: Callable[[Event], None]) -> None:
        """Unsubscribe a handler callback from a specific event type."""
        key = self._normalize_type(event_type)
        if key in self._subscribers and handler in self._subscribers[key]:
            self._subscribers[key].remove(handler)
            if not self._subscribers[key]:
                del self._subscribers[key]

    def publish(self, event: Event) -> None:
        """Synchronously dispatch an event to all registered subscribers."""
        key = self._normalize_type(event.type)
        handlers = list(self._subscribers.get(key, []))
        for handler in handlers:
            handler(event)

    def emit(self, event_type: EventType | str, data: Any = None) -> Event:
        """Convenience method to construct and publish an event."""
        event = Event(type=event_type, data=data)
        self.publish(event)
        return event

    def clear(self) -> None:
        """Remove all subscriptions."""
        self._subscribers.clear()
