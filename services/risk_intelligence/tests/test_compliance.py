import unittest

from app.compliance import GSTIN_COMPLIANCE_FLOOR, apply_gstin_compliance_floor


class GstinCompliancePolicyTests(unittest.TestCase):
    def test_invalid_gstin_adds_a_critical_compliance_floor(self):
        model_scores = {"compliance_risk": 0.1, "fraud_risk": 0.05}
        adjusted = apply_gstin_compliance_floor(model_scores, gstin_valid=False)
        self.assertEqual(adjusted["compliance_risk"], GSTIN_COMPLIANCE_FLOOR)
        self.assertEqual(adjusted["fraud_risk"], 0.05)
        self.assertEqual(model_scores["compliance_risk"], 0.1)

    def test_valid_gstin_keeps_model_scores_unchanged(self):
        model_scores = {"compliance_risk": 0.1, "fraud_risk": 0.05}
        self.assertEqual(apply_gstin_compliance_floor(model_scores, gstin_valid=True), model_scores)


if __name__ == "__main__":
    unittest.main()
