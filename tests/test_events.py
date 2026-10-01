"""Unit tests for EventBus and Event handling."""
import unittest

from time_clock.events import Event, EventBus, EventType


class TestEventBus(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    def test_subscribe_and_publish(self):
        received = []

        def handler(event: Event):
            received.append(event)

        self.bus.subscribe(EventType.TASK_CREATED, handler)
        event = self.bus.emit(EventType.TASK_CREATED, {"task_id": "t1"})

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].type, EventType.TASK_CREATED)
        self.assertEqual(received[0].data, {"task_id": "t1"})

    def test_multiple_subscribers(self):
        results = []

        def h1(e):
            results.append("h1")

        def h2(e):
            results.append("h2")

        self.bus.subscribe(EventType.CLOCK_IN, h1)
        self.bus.subscribe(EventType.CLOCK_IN, h2)
        self.bus.emit(EventType.CLOCK_IN, "data")

        self.assertEqual(results, ["h1", "h2"])

    def test_unsubscribe(self):
        received = []

        def handler(event: Event):
            received.append(event)

        self.bus.subscribe(EventType.CLOCK_OUT, handler)
        self.bus.emit(EventType.CLOCK_OUT, "1")
        self.assertEqual(len(received), 1)

        self.bus.unsubscribe(EventType.CLOCK_OUT, handler)
        self.bus.emit(EventType.CLOCK_OUT, "2")
        self.assertEqual(len(received), 1)

    def test_string_and_enum_event_type_compatibility(self):
        received = []

        def handler(event: Event):
            received.append(event)

        self.bus.subscribe("TASK_SELECTED", handler)
        self.bus.emit(EventType.TASK_SELECTED, "task_123")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data, "task_123")

    def test_clear_subscribers(self):
        received = []

        def handler(event: Event):
            received.append(event)

        self.bus.subscribe(EventType.TICK, handler)
        self.bus.clear()
        self.bus.emit(EventType.TICK, 1.0)
        self.assertEqual(len(received), 0)


if __name__ == "__main__":
    unittest.main()
