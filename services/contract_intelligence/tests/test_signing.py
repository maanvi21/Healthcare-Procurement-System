"""Focused tests for the PDF packet and OpenSign request adapter."""
import base64
import importlib.util
import sys
import types
import unittest
from unittest.mock import Mock, patch

if importlib.util.find_spec("pydantic_settings") is None:
    # The bundled authoring runtime does not ship service dependencies. Keep the
    # provider-adapter tests runnable there without changing service configuration.
    fake_config = types.ModuleType("app.config")
    fake_config.settings = types.SimpleNamespace(
        opensign_api_key="test-token",
        opensign_base_url="https://sandbox.opensignlabs.com/api/v1.2",
        esign_demo_mode=False,
    )
    sys.modules["app.config"] = fake_config
if importlib.util.find_spec("requests") is None:
    fake_requests = types.ModuleType("requests")
    fake_requests.post = lambda *args, **kwargs: None
    sys.modules["requests"] = fake_requests

from app.config import settings
from app.esign_client import send_for_signature
from app.pdf_render import render_contract_pdf


class PdfPacketTests(unittest.TestCase):
    def test_contract_pdf_contains_terms_and_has_signature_page(self):
        pdf, signature_page = render_contract_pdf(
            "<h1>SUPPLY AGREEMENT</h1><p>Vendor: Northstar Medical</p>",
            "Northstar Medical",
        )
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf), 1000)
        self.assertEqual(signature_page, 2)


class OpenSignAdapterTests(unittest.TestCase):
    def setUp(self):
        self.old = (
            settings.opensign_api_key,
            settings.opensign_base_url,
            settings.esign_demo_mode,
        )
        settings.opensign_api_key = "test-token"
        settings.opensign_base_url = "https://sandbox.opensignlabs.com/api/v1.2"
        settings.esign_demo_mode = False

    def tearDown(self):
        settings.opensign_api_key, settings.opensign_base_url, settings.esign_demo_mode = self.old

    @patch("app.esign_client.requests.post")
    def test_sends_pdf_with_provider_signature_widget_and_email(self, post):
        response = Mock()
        response.json.return_value = {
            "objectId": "envelope-123",
            "signurl": [{"email": "signer@example.com", "url": "https://sign.example.com/envelope-123"}],
        }
        post.return_value = response

        result = send_for_signature(
            "contract-123", b"%PDF-packet", "signer@example.com", "Supplier Contact", 2,
        )

        self.assertEqual(result["object_id"], "envelope-123")
        self.assertEqual(result["provider"], "opensign")
        self.assertEqual(result["signing_url"], "https://sign.example.com/envelope-123")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://sandbox.opensignlabs.com/api/v1.2/createdocument")
        self.assertEqual(kwargs["headers"]["x-api-token"], "test-token")
        body = kwargs["json"]
        self.assertEqual(base64.b64decode(body["file"]), b"%PDF-packet")
        signer = body["signers"][0]
        self.assertEqual(signer["email"], "signer@example.com")
        self.assertEqual(signer["widgets"][0]["page"], 2)
        self.assertTrue(body["send_email"])

    def test_missing_token_does_not_fake_a_real_provider_envelope(self):
        settings.opensign_api_key = ""
        with self.assertRaisesRegex(RuntimeError, "OPENSIGN_API_KEY"):
            send_for_signature("contract-123", b"%PDF", "a@example.com", "A", 1)

    def test_demo_mode_is_explicit_and_labelled(self):
        settings.opensign_api_key = ""
        settings.esign_demo_mode = True
        result = send_for_signature("contract-123", b"%PDF", "a@example.com", "A", 1)
        self.assertEqual(result["provider"], "demo")
        self.assertTrue(result["object_id"].startswith("demo-"))
        self.assertIsNone(result["signing_url"])


if __name__ == "__main__":
    unittest.main()
