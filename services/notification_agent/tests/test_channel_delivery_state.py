"""Provider adapter state tests; no provider credentials or network calls required."""
import importlib.util
import os
import sys
import types
import unittest
from enum import Enum
from unittest.mock import patch

if importlib.util.find_spec("sqlalchemy") is None:
    fake_models = types.ModuleType("app.models")
    class NotificationChannel(str, Enum):
        email = "email"
        sms = "sms"
        teams = "teams"
        slack = "slack"
    fake_models.NotificationChannel = NotificationChannel
    sys.modules["app.models"] = fake_models

from app.channels import send_notification
from app.models import NotificationChannel


class ChannelDeliveryStateTests(unittest.TestCase):
    def test_missing_email_provider_is_log_only_not_delivered(self):
        with patch.dict(os.environ, {"SENDGRID_API_KEY": "", "SENDGRID_FROM_EMAIL": ""}):
            delivered = send_notification(
                NotificationChannel.email, "staff@example.com", "Subject", "Body",
            )
        self.assertFalse(delivered)

    def test_missing_chat_provider_is_log_only_not_delivered(self):
        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": ""}):
            delivered = send_notification(
                NotificationChannel.slack, "procurement", None, "Body",
            )
        self.assertFalse(delivered)


if __name__ == "__main__":
    unittest.main()
