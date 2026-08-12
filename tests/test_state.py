import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from monitor.model import MonitorState, Observation
from monitor.state import (
    heartbeat_slot,
    load_state,
    observation_changed,
    save_state,
)


class StateTests(unittest.TestCase):
    def test_first_observation_is_a_change(self):
        current = Observation("sold_out", "Мест нет", None)

        self.assertTrue(observation_changed(None, current))

    def test_identical_observation_is_not_a_change(self):
        item = Observation("sold_out", "Мест нет", None)

        self.assertFalse(observation_changed(item, item))

    def test_place_count_change_is_a_change(self):
        before = Observation("available", "Осталось 3 места", 3)
        after = Observation("available", "Осталось 2 места", 2)

        self.assertTrue(observation_changed(before, after))

    def test_raw_status_change_is_a_change(self):
        before = Observation("unknown", "Статус не распознан", None)
        after = Observation("unknown", "Изменённая разметка", None)

        self.assertTrue(observation_changed(before, after))

    def test_moscow_heartbeat_slots(self):
        morning = datetime(2026, 8, 12, 9, 17, tzinfo=ZoneInfo("Europe/Moscow"))
        evening = datetime(2026, 8, 12, 21, 2, tzinfo=ZoneInfo("Europe/Moscow"))

        self.assertEqual(heartbeat_slot(morning), "2026-08-12T09")
        self.assertEqual(heartbeat_slot(evening), "2026-08-12T21")

    def test_heartbeat_converts_from_utc(self):
        utc_time = datetime(2026, 8, 12, 6, 7, tzinfo=timezone.utc)

        self.assertEqual(heartbeat_slot(utc_time), "2026-08-12T09")

    def test_no_heartbeat_outside_target_hours(self):
        now = datetime(2026, 8, 12, 10, 0, tzinfo=ZoneInfo("Europe/Moscow"))

        self.assertIsNone(heartbeat_slot(now))

    def test_state_round_trip(self):
        state = MonitorState(
            observation=Observation("available", "Осталось 3 места", 3),
            observed_at="2026-08-12T09:00:00+03:00",
            last_heartbeat_slot="2026-08-12T09",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / "status.json"

            save_state(path, state)

            self.assertEqual(load_state(path), state)

    def test_missing_state_file_returns_empty_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "status.json"

            self.assertEqual(load_state(path), MonitorState(None, None, None))


if __name__ == "__main__":
    unittest.main()
