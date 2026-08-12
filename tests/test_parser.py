import unittest
from pathlib import Path

from monitor.model import Observation
from monitor.parser import parse_availability


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class ParseAvailabilityTests(unittest.TestCase):
    def test_sold_out_for_exact_date(self):
        result = parse_availability(load_fixture("sold_out.html"), "21.08.2026")

        self.assertEqual(result, Observation("sold_out", "Мест нет", None))

    def test_available_with_places(self):
        result = parse_availability(load_fixture("available.html"), "21.08.2026")

        self.assertEqual(result, Observation("available", "Осталось 3 места", 3))

    def test_missing_date(self):
        result = parse_availability(load_fixture("available.html"), "22.08.2026")

        self.assertEqual(result, Observation("date_missing", "Дата не найдена", None))

    def test_unknown_status(self):
        html = '<div jatoms-schedule="item"><strong>21.08.2026</strong></div>'

        result = parse_availability(html, "21.08.2026")

        self.assertEqual(result, Observation("unknown", "Статус не распознан", None))

    def test_enabled_booking_button_means_available(self):
        html = (
            '<div jatoms-schedule="item">'
            '<strong>21.08.2026</strong><button>Забронировать</button>'
            "</div>"
        )

        result = parse_availability(html, "21.08.2026")

        self.assertEqual(
            result, Observation("available", "Бронирование доступно", None)
        )


if __name__ == "__main__":
    unittest.main()
