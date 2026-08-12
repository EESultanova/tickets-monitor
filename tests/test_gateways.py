import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

from monitor.gateways import fetch_page, send_telegram


class FakeHeaders:
    def __init__(self, charset=None):
        self.charset = charset

    def get_content_charset(self):
        return self.charset


class FakeResponse:
    def __init__(self, body, charset=None):
        self.body = body
        self.headers = FakeHeaders(charset)

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        return False

    def read(self):
        return self.body


class GatewayTests(unittest.TestCase):
    @patch("monitor.gateways.urlopen")
    def test_fetch_page_sets_user_agent_and_decodes_response(self, urlopen):
        urlopen.return_value = FakeResponse("Мест нет".encode("utf-8"), "utf-8")

        result = fetch_page("https://example.test/tour")

        request = urlopen.call_args.args[0]
        self.assertEqual(result, "Мест нет")
        self.assertIn("Availability-Monitor", request.get_header("User-agent"))

    @patch("monitor.gateways.urlopen")
    def test_send_telegram_posts_expected_form(self, urlopen):
        urlopen.return_value = FakeResponse(json.dumps({"ok": True}).encode("utf-8"))

        send_telegram("secret-token", "123", "Проверка")

        request = urlopen.call_args.args[0]
        form = parse_qs(request.data.decode("utf-8"))
        self.assertEqual(form["chat_id"], ["123"])
        self.assertEqual(form["text"], ["Проверка"])
        self.assertEqual(form["disable_web_page_preview"], ["true"])

    @patch("monitor.gateways.urlopen")
    def test_telegram_network_error_does_not_expose_token(self, urlopen):
        urlopen.side_effect = OSError(
            "https://api.telegram.org/bottest-secret/sendMessage failed"
        )

        with self.assertRaises(RuntimeError) as caught:
            send_telegram("test-secret", "123", "Проверка")

        self.assertNotIn("test-secret", str(caught.exception))

    @patch("monitor.gateways.urlopen")
    def test_telegram_api_rejection_is_an_error(self, urlopen):
        body = {"ok": False, "description": "chat not found"}
        urlopen.return_value = FakeResponse(json.dumps(body).encode("utf-8"))

        with self.assertRaisesRegex(RuntimeError, "rejected"):
            send_telegram("test-secret", "123", "Проверка")


if __name__ == "__main__":
    unittest.main()
