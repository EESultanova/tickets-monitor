import os
from datetime import datetime
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo

from monitor.app import Config, run_check
from monitor.gateways import fetch_page, send_telegram


TARGET_URL = (
    "https://xn----7sbaa5baman5bedhc2a0n.xn--p1ai/"
    "samara/sbornye-ekskursii/44884-avtovaz-put-uspekha-2026"
)
TARGET_DATE = "21.08.2026"


def config_from_environment(environment):
    # type: (Mapping[str, str]) -> Config
    missing = [
        name
        for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
        if not environment.get(name)
    ]
    if missing:
        raise ValueError("Не заданы переменные: {}".format(", ".join(missing)))

    return Config(
        url=TARGET_URL,
        target_date=TARGET_DATE,
        state_path=Path("state/status.json"),
        telegram_token=environment["TELEGRAM_BOT_TOKEN"],
        telegram_chat_id=environment["TELEGRAM_CHAT_ID"],
    )


def main():
    try:
        config = config_from_environment(os.environ)
    except ValueError as error:
        raise SystemExit(str(error)) from None

    result = run_check(
        config,
        fetch_page,
        send_telegram,
        datetime.now(ZoneInfo("Europe/Moscow")),
    )
    print(
        "status={} messages_sent={} state_changed={}".format(
            result.observation.status,
            result.messages_sent,
            str(result.state_changed).lower(),
        )
    )


if __name__ == "__main__":
    main()
