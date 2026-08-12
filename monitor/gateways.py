import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = "AvtoVAZ-Availability-Monitor/1.0 (+personal notification monitor)"


def fetch_page(url, timeout=20.0):
    # type: (str, float) -> str
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def send_telegram(token, chat_id, text, timeout=20.0):
    # type: (str, str, str, float) -> None
    endpoint = "https://api.telegram.org/bot{}/sendMessage".format(token)
    data = urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception:
        raise RuntimeError("Telegram API request failed") from None

    if result.get("ok") is not True:
        raise RuntimeError("Telegram API rejected the message")
