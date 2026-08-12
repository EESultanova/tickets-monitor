import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from monitor.model import MonitorState, Observation


MOSCOW_TIMEZONE = ZoneInfo("Europe/Moscow")


def observation_changed(previous, current):
    # type: (Optional[Observation], Observation) -> bool
    if previous is None:
        return True
    return (
        previous.status,
        previous.places,
        previous.raw_status,
    ) != (
        current.status,
        current.places,
        current.raw_status,
    )


def heartbeat_slot(now):
    # type: (datetime) -> Optional[str]
    moscow_now = now.astimezone(MOSCOW_TIMEZONE)
    if moscow_now.hour not in (9, 21):
        return None
    return moscow_now.strftime("%Y-%m-%dT%H")


def load_state(path):
    # type: (Path) -> MonitorState
    if not path.exists():
        return MonitorState(None, None, None)
    value = json.loads(path.read_text(encoding="utf-8"))
    return MonitorState.from_dict(value)


def save_state(path, state):
    # type: (Path, MonitorState) -> None
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n"
    path.write_text(serialized, encoding="utf-8")
