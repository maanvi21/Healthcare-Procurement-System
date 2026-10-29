"""Provider adapter state tests; no provider credentials or network calls required."""
import importlib.util
import os
import re
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
    def test_placeholder_provider_settings_are_simulated_not_failed(self):
        with patch.dict(os.environ, {
            "SENDGRID_API_KEY": "your-sendgrid-api-key-here",
            "SENDGRID_FROM_EMAIL": "your-email@example.com",
        }, clear=True):
            delivered = send_notification(
                NotificationChannel.email, "staff@example.com", "Subject", "Body",
            )
        self.assertFalse(delivered)

    def test_missing_email_provider_is_log_only_not_delivered(self):
        with patch.dict(os.environ, {"SENDGRID_API_KEY": "", "SENDGRID_FROM_EMAIL": ""}):
            delivered = send_notification(
                NotificationChannel.email, "staff@example.com", "Subject", "Body",
            )
        self.assertFalse(delivered)

    def test_non_email_channels_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Only email notifications are supported"):
            send_notification(NotificationChannel.slack, "procurement", None, "Body")

    def test_provider_status_exposes_email_only(self):
        from app.channels import get_provider_status

        self.assertEqual(set(get_provider_status()), {"email"})

    def test_email_event_templates_cover_all_consumed_topics(self):
        from app.topics import TOPICS
        from app.templates import DEFAULT_TEMPLATES

        templates_by_event = {template["event_type"]: template for template in DEFAULT_TEMPLATES}
        self.assertEqual(set(TOPICS), set(templates_by_event))
        self.assertTrue(all(template["channel"] == NotificationChannel.email for template in DEFAULT_TEMPLATES))

    def test_business_topic_pattern_includes_new_notification_events(self):
        from app.topics import TOPIC_PATTERN

        self.assertRegex("documents.uploaded", TOPIC_PATTERN)
        self.assertRegex("vendor.accepted", TOPIC_PATTERN)
        self.assertRegex("risk.alerted", TOPIC_PATTERN)
        self.assertNotRegex("kafka.internal", TOPIC_PATTERN)

    def test_api_schemas_reject_non_email_channels(self):
        from pydantic import ValidationError
        from app.schemas import SendRequest

        with self.assertRaises(ValidationError):
            SendRequest(channel="slack", recipient="team", body="Alert")


if __name__ == "__main__":
    unittest.main()
