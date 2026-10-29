import unittest
from unittest.mock import Mock, patch

from app.risk_client import get_vendor_risk_band


class RiskClientProvenanceTests(unittest.TestCase):
    @patch("app.risk_client.requests.get")
    def test_unvalidated_score_is_never_used_for_approval_routing(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {"risk_band": "low", "model_status": "unvalidated"}
        get.return_value = response

        self.assertIsNone(get_vendor_risk_band("vendor-1"))

    @patch("app.risk_client.requests.get")
    def test_validated_score_is_available_to_approval_routing(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {"risk_band": "high", "model_status": "validated"}
        get.return_value = response

        self.assertEqual(get_vendor_risk_band("vendor-1"), "high")

    @patch("app.risk_client.requests.get")
    def test_project_synthetic_baseline_keeps_learning_workflow_functional(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {"risk_band": "medium", "model_status": "synthetic_project"}
        get.return_value = response

        self.assertEqual(get_vendor_risk_band("vendor-1"), "medium")

    def test_missing_vendor_has_no_risk_band(self):
        self.assertIsNone(get_vendor_risk_band(None))


if __name__ == "__main__":
    unittest.main()
