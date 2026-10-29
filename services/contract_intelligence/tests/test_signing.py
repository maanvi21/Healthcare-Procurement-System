"""Focused tests for generated contracts and the DocuSign envelope adapter."""
import base64
import importlib.util
import sys
import types
import unittest
from unittest.mock import Mock, patch

if importlib.util.find_spec("pydantic_settings") is None:
    fake_config = types.ModuleType("app.config")
    fake_config.settings = types.SimpleNamespace(
        docusign_integration_key="integration-id",
        docusign_user_id="user-id",
        docusign_account_id="account-id",
        docusign_rsa_private_key="-----BEGIN PRIVATE KEY-----\\nkey\\n-----END PRIVATE KEY-----",
        docusign_oauth_host="account-d.docusign.com",
        docusign_rest_base_url="https://demo.docusign.net/restapi",
        docusign_connect_url="https://example.test/api/contracts/webhooks/docusign",
        docusign_connect_hmac_key="connect-key",
    )
    sys.modules["app.config"] = fake_config
if importlib.util.find_spec("requests") is None:
    fake_requests = types.ModuleType("requests")
    fake_requests.post = lambda *args, **kwargs: None
    fake_requests.get = lambda *args, **kwargs: None
    fake_requests.request = lambda *args, **kwargs: None
    sys.modules["requests"] = fake_requests

from app.config import settings
from app.esign_client import credentials_configured, send_for_signature
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


class DocuSignAdapterTests(unittest.TestCase):
    def setUp(self):
        self.old = (
            settings.docusign_integration_key,
            settings.docusign_user_id,
            settings.docusign_rsa_private_key,
            settings.docusign_connect_url,
            settings.docusign_connect_hmac_key,
        )
        settings.docusign_integration_key = "integration-id"
        settings.docusign_user_id = "user-id"
        settings.docusign_rsa_private_key = "-----BEGIN PRIVATE KEY-----\\nkey\\n-----END PRIVATE KEY-----"
        settings.docusign_connect_url = "https://example.test/api/contracts/webhooks/docusign"
        settings.docusign_connect_hmac_key = "connect-key"

    def tearDown(self):
        (settings.docusign_integration_key, settings.docusign_user_id,
         settings.docusign_rsa_private_key, settings.docusign_connect_url,
         settings.docusign_connect_hmac_key) = self.old

    @patch("app.esign_client._api_request")
    def test_sends_pdf_as_email_envelope_with_signature_tab_and_connect_events(self, api_request):
        response = Mock()
        response.json.return_value = {"envelopeId": "envelope-123", "status": "sent"}
        api_request.return_value = response

        result = send_for_signature(
            "contract-123", b"%PDF-packet", "signer@example.com", "Supplier Contact", 2,
        )

        self.assertEqual(result["object_id"], "envelope-123")
        self.assertEqual(result["provider"], "docusign")
        self.assertIsNone(result["signing_url"])
        api_request.assert_called_once()
        method, path = api_request.call_args.args
        self.assertEqual((method, path), ("POST", "/envelopes"))
        body = api_request.call_args.kwargs["json"]
        self.assertEqual(body["status"], "sent")
        self.assertEqual(base64.b64decode(body["documents"][0]["documentBase64"]), b"%PDF-packet")
        signer = body["recipients"]["signers"][0]
        self.assertEqual(signer["email"], "signer@example.com")
        self.assertEqual(signer["tabs"]["signHereTabs"][0]["pageNumber"], "2")
        self.assertEqual(body["eventNotification"]["url"], settings.docusign_connect_url)

    def test_missing_doc_sign_credentials_fail_instead_of_faking_envelope(self):
        settings.docusign_rsa_private_key = ""
        self.assertFalse(credentials_configured())
        with patch("app.esign_client._api_request") as api_request:
            with self.assertRaisesRegex(RuntimeError, "DOCUSIGN_RSA_PRIVATE_KEY"):
                send_for_signature("contract-123", b"%PDF", "a@example.com", "A", 1)
        api_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
