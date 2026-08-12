import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import List, Optional

from monitor.model import Observation


@dataclass(frozen=True)
class _ScheduleCard:
    text: str
    booking_enabled: bool


class _ScheduleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cards = []  # type: List[_ScheduleCard]
        self._div_depth = 0
        self._text = []  # type: List[str]
        self._booking_enabled = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)  # type: dict
        is_schedule_item = attributes.get("jatoms-schedule") == "item"

        if self._div_depth == 0 and tag == "div" and is_schedule_item:
            self._div_depth = 1
            self._text = []
            self._booking_enabled = False
            return

        if self._div_depth == 0:
            return

        if tag == "div":
            self._div_depth += 1
        elif tag == "button" and "disabled" not in attributes:
            self._booking_enabled = True

    def handle_endtag(self, tag):
        if self._div_depth == 0 or tag != "div":
            return

        self._div_depth -= 1
        if self._div_depth == 0:
            text = " ".join(" ".join(self._text).split())
            self.cards.append(_ScheduleCard(text, self._booking_enabled))

    def handle_data(self, data):
        if self._div_depth > 0 and data.strip():
            self._text.append(data.strip())


def _matching_card(cards, target_date):
    # type: (List[_ScheduleCard], str) -> Optional[_ScheduleCard]
    date_pattern = re.compile(r"(?<!\d){}(?!\d)".format(re.escape(target_date)))
    return next((card for card in cards if date_pattern.search(card.text)), None)


def parse_availability(html, target_date):
    # type: (str, str) -> Observation
    parser = _ScheduleParser()
    parser.feed(html)
    card = _matching_card(parser.cards, target_date)

    if card is None:
        return Observation("date_missing", "Дата не найдена", None)

    if re.search(r"\bМест\s+нет\b", card.text, re.IGNORECASE):
        return Observation("sold_out", "Мест нет", None)

    places_match = re.search(
        r"Осталось\s+(\d+)\s+мест(?:о|а)?", card.text, re.IGNORECASE
    )
    if places_match:
        places = int(places_match.group(1))
        return Observation("available", places_match.group(0), places)

    if card.booking_enabled:
        return Observation("available", "Бронирование доступно", None)

    return Observation("unknown", "Статус не распознан", None)
