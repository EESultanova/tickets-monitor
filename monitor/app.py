from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from monitor.model import MonitorState, Observation
from monitor.parser import parse_availability
from monitor.state import (
    MOSCOW_TIMEZONE,
    heartbeat_slot,
    load_state,
    observation_changed,
    save_state,
)


ERROR_STATUSES = {"unknown", "date_missing", "fetch_error"}


@dataclass(frozen=True)
class Config:
    url: str
    target_date: str
    state_path: Path
    telegram_token: str
    telegram_chat_id: str


@dataclass(frozen=True)
class RunResult:
    observation: Observation
    messages_sent: int
    state_changed: bool


def _observe(config, fetch):
    # type: (Config, Callable[[str], str]) -> Observation
    try:
        html = fetch(config.url)
        return parse_availability(html, config.target_date)
    except Exception as error:
        return Observation(
            "fetch_error",
            "Ошибка загрузки: {}".format(type(error).__name__),
            None,
        )


def _status_heading(previous, current):
    # type: (Observation, Observation) -> str
    recovered = previous is not None and previous.status in ERROR_STATUSES
    if current.status == "available":
        heading = "🚨 ПОЯВИЛИСЬ МЕСТА"
    elif current.status == "sold_out":
        heading = "ℹ️ Статус изменился: мест нет"
    else:
        heading = "⚠️ Монитор требует внимания"

    if recovered and current.status not in ERROR_STATUSES:
        heading = "✅ Монитор снова работает нормально\n" + heading
    return heading


def _build_message(config, previous, current, now, include_change, include_heartbeat):
    # type: (Config, Observation, Observation, datetime, bool, bool) -> str
    lines = []
    if include_change:
        lines.append(_status_heading(previous, current))
    if include_heartbeat:
        lines.append("💚 Монитор включён и ожидает смены статуса")

    lines.extend(
        [
            "",
            "Экскурсия: «АВТОВАЗ — путь успеха!»",
            "Дата: {}".format(config.target_date),
            "Текущий статус: {}".format(current.raw_status),
            "Проверено: {} (Москва)".format(
                now.astimezone(MOSCOW_TIMEZONE).strftime("%d.%m.%Y %H:%M")
            ),
            "",
            config.url,
        ]
    )
    return "\n".join(lines)


def run_check(config, fetch, send, now):
    # type: (Config, Callable[[str], str], Callable[[str, str, str], None], datetime) -> RunResult
    previous_state = load_state(config.state_path)
    current = _observe(config, fetch)
    changed = observation_changed(previous_state.observation, current)
    slot = heartbeat_slot(now)
    heartbeat_due = slot is not None and slot != previous_state.last_heartbeat_slot

    if not changed and not heartbeat_due:
        return RunResult(current, 0, False)

    message = _build_message(
        config,
        previous_state.observation,
        current,
        now,
        include_change=changed,
        include_heartbeat=heartbeat_due,
    )
    send(config.telegram_token, config.telegram_chat_id, message)

    next_state = MonitorState(
        observation=current,
        observed_at=(
            now.astimezone(MOSCOW_TIMEZONE).isoformat()
            if changed
            else previous_state.observed_at
        ),
        last_heartbeat_slot=slot if heartbeat_due else previous_state.last_heartbeat_slot,
    )
    save_state(config.state_path, next_state)
    return RunResult(current, 1, True)
