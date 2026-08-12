import unittest

from run_monitor import TARGET_DATE, config_from_environment


class EntrypointTests(unittest.TestCase):
    def test_config_comes_from_environment_without_changing_target(self):
        config = config_from_environment(
            {"TELEGRAM_BOT_TOKEN": "token-value", "TELEGRAM_CHAT_ID": "chat-value"}
        )

        self.assertEqual(
            config.url,
            "https://xn----7sbaa5baman5bedhc2a0n.xn--p1ai/"
            "samara/sbornye-ekskursii/44884-avtovaz-put-uspekha-2026",
        )
        self.assertEqual(config.target_date, TARGET_DATE)
        self.assertEqual(config.telegram_token, "token-value")
        self.assertEqual(config.telegram_chat_id, "chat-value")

    def test_missing_secret_has_safe_configuration_error(self):
        with self.assertRaises(ValueError) as caught:
            config_from_environment({})

        message = str(caught.exception)
        self.assertIn("TELEGRAM_BOT_TOKEN", message)
        self.assertIn("TELEGRAM_CHAT_ID", message)
        self.assertNotIn("api.telegram.org", message)


if __name__ == "__main__":
    unittest.main()
