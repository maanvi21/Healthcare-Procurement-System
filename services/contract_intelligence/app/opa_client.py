"""Client for the pre-signature compliance gate evaluated by OPA
(policies/opa/compliance_rules.rego). Called right before a contract is sent for
e-signature so a high-risk vendor can't reach a signed contract without a recorded
human override."""
import requests

from app.config import settings


def check_signature_allowed(vendor_risk_band: str | None, drug_license_valid: bool, override_approved: bool) -> tuple[bool, list[str]]:
    payload = {
        "input": {
            "vendor_risk_band": vendor_risk_band or "unknown",
            "drug_license_valid": drug_license_valid,
            "override_approved": override_approved,
        }
    }
    try:
        allow_resp = requests.post(f"{settings.opa_url}/v1/data/medisource/compliance/allow_signature", json=payload, timeout=5)
        allow_resp.raise_for_status()
        allowed = bool(allow_resp.json().get("result", False))

        reasons_resp = requests.post(f"{settings.opa_url}/v1/data/medisource/compliance/deny_reasons", json=payload, timeout=5)
        reasons_resp.raise_for_status()
        reasons = list(reasons_resp.json().get("result", []))
        return allowed, reasons
    except requests.RequestException:
        # OPA unreachable — fail open for the demo rather than blocking the whole flow,
        # but this is exactly the kind of gap a production deployment must not accept.
        return True, []
