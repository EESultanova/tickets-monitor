import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from monitor.app import Config, run_check
from monitor.model import MonitorState, Observation
from monitor.state import load_state, save_state


FIXTURES = Path(__file__).parent / "fixtures"
MOSCOW = ZoneInfo("Europe/Moscow")


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_path = Path(self.temp_dir.name) / "status.json"
        self.config = Config(
            url="https://example.test/excursion",
            target_date="21.08.2026",
            state_path=self.state_path,
            telegram_token="test-token",
            telegram_chat_id="123",
        )
        self.sent = []

    def send(self, token, chat_id, text):
        self.sent.append((token, chat_id, text))

    def run_monitor(self, html, now=None):
        if now is None:
            now = datetime(2026, 8, 12, 10, 15, tzinfo=MOSCOW)
        return run_check(self.config, lambda _url: html, self.send, now)

    def seed(self, observation, heartbeat=None):
        save_state(
            self.state_path,
            MonitorState(
                observation=observation,
                observed_at="2026-08-12T08:00:00+03:00",
                last_heartbeat_slot=heartbeat,
            ),
        )

    def test_first_run_sends_current_status_and_saves_state(self):
        result = self.run_monitor(fixture("sold_out.html"))

        self.assertEqual(result.messages_sent, 1)
        self.assertTrue(result.state_changed)
        self.assertIn("21.08.2026", self.sent[0][2])
        self.assertIn("мест нет", self.sent[0][2].lower())
        self.assertEqual(load_state(self.state_path).observation.status, "sold_out")

    def test_unchanged_non_heartbeat_run_sends_nothing(self):
        self.seed(Observation("sold_out", "Мест нет", None))

        result = self.run_monitor(fixture("sold_out.html"))

        self.assertEqual(self.sent, [])
        self.assertEqual(result.messages_sent, 0)
        self.assertFalse(result.state_changed)

    def test_available_transition_sends_high_priority_alert(self):
        self.seed(Observation("sold_out", "Мест нет", None))

        result = self.run_monitor(fixture("available.html"))

        self.assertEqual(result.observation.places, 3)
        self.assertIn("ПОЯВИЛИСЬ МЕСТА", self.sent[0][2])
        self.assertIn("Осталось 3 места", self.sent[0][2])
        self.assertIn(self.config.url, self.sent[0][2])

    def test_heartbeat_sends_once_per_hour_slot(self):
        self.seed(Observation("sold_out", "Мест нет", None))
        morning = datetime(2026, 8, 12, 9, 7, tzinfo=MOSCOW)

        first = self.run_monitor(fixture("sold_out.html"), morning)
        second = self.run_monitor(
            fixture("sold_out.html"),
            datetime(2026, 8, 12, 9, 22, tzinfo=MOSCOW),
        )

        self.assertEqual(first.messages_sent, 1)
        self.assertEqual(second.messages_sent, 0)
        self.assertEqual(len(self.sent), 1)
        self.assertIn("Монитор включён", self.sent[0][2])

    def test_fetch_error_is_sent_once_until_recovery(self):
        self.seed(Observation("sold_out", "Мест нет", None))

        def fail(_url):
            raise TimeoutError("site timed out")

        first = run_check(
            self.config,
            fail,
            self.send,
            datetime(2026, 8, 12, 10, 15, tzinfo=MOSCOW),
        )
        second = run_check(
            self.config,
            fail,
            self.send,
            datetime(2026, 8, 12, 10, 30, tzinfo=MOSCOW),
        )

        self.assertEqual(first.observation.status, "fetch_error")
        self.assertEqual(first.messages_sent, 1)
        self.assertEqual(second.messages_sent, 0)
        self.assertIn("требует внимания", self.sent[0][2])

    def test_recovery_from_error_is_announced(self):
        self.seed(Observation("fetch_error", "Ошибка загрузки: TimeoutError", None))

        self.run_monitor(fixture("sold_out.html"))

        self.assertIn("снова работает нормально", self.sent[0][2])

    def test_change_and_heartbeat_are_combined(self):
        self.seed(Observation("sold_out", "Мест нет", None))

        result = self.run_monitor(
            fixture("available.html"),
            datetime(2026, 8, 12, 21, 3, tzinfo=MOSCOW),
        )

        self.assertEqual(result.messages_sent, 1)
        self.assertIn("ПОЯВИЛИСЬ МЕСТА", self.sent[0][2])
        self.assertIn("Монитор включён", self.sent[0][2])

    def test_send_failure_does_not_advance_state(self):
        previous = Observation("sold_out", "Мест нет", None)
        self.seed(previous)

        def fail_send(_token, _chat_id, _text):
            raise RuntimeError("Telegram unavailable")

        with self.assertRaises(RuntimeError):
            run_check(
                self.config,
                lambda _url: fixture("available.html"),
                fail_send,
                datetime(2026, 8, 12, 10, 15, tzinfo=MOSCOW),
            )

        self.assertEqual(load_state(self.state_path).observation, previous)


if __name__ == "__main__":
    unittest.main()
