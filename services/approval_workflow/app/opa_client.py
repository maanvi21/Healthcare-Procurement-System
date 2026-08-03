"""Client for the approval-routing policy evaluated by Open Policy Agent
(policies/opa/approval_rules.rego). Keeps approval logic as data/code the policy
authors can change without redeploying this service."""
import requests

from app.config import settings

_FALLBACK_STEPS = [{"approver_role": "department_manager", "sla_hours": 24}]


def get_approval_steps(department: str, category: str, total_value: float, vendor_risk_band: str | None) -> list[dict]:
    payload = {
        "input": {
            "department": department,
            "category": category,
            "total_value": total_value,
            "vendor_risk_band": vendor_risk_band or "unknown",
        }
    }
    try:
        response = requests.post(
            f"{settings.opa_url}/v1/data/medisource/approval/steps", json=payload, timeout=5,
        )
        response.raise_for_status()
        result = response.json().get("result")
        if result:
            return result
    except requests.RequestException:
        pass
    return _FALLBACK_STEPS
