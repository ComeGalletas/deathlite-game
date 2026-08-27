"""Milestone 1: event bus dispatch, unsubscribe, and handler-error isolation."""
import logging
import unittest

from game.events import EventBus


class EventBusTests(unittest.TestCase):
    def test_publish_calls_all_subscribers_with_payload(self):
        bus = EventBus()
        seen = []
        bus.subscribe("ping", lambda **kw: seen.append(kw))
        bus.subscribe("ping", lambda **kw: seen.append("second"))
        bus.publish("ping", value=7)
        self.assertEqual(seen, [{"value": 7}, "second"])

    def test_unsubscribe_stops_delivery(self):
        bus = EventBus()
        calls = []
        handler = lambda **kw: calls.append(1)
        bus.subscribe("x", handler)
        bus.unsubscribe("x", handler)
        bus.publish("x")
        self.assertEqual(calls, [])

    def test_clear_removes_everything(self):
        bus = EventBus()
        bus.subscribe("x", lambda **kw: None)
        bus.clear()
        bus.publish("x")  # must not raise

    def test_one_bad_handler_does_not_block_others(self):
        bus = EventBus()
        calls = []

        def boom(**kw):
            raise RuntimeError("handler failure")

        bus.subscribe("e", boom)
        bus.subscribe("e", lambda **kw: calls.append("ok"))
        logging.disable(logging.CRITICAL)  # silence the expected log.exception
        try:
            bus.publish("e")
        finally:
            logging.disable(logging.NOTSET)
        self.assertEqual(calls, ["ok"])


if __name__ == "__main__":
    unittest.main()
