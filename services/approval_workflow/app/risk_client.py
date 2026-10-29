"""Look up a vendor's current risk band from risk_intelligence.

Closes the loop ARCHITECTURE.md describes: OPA's approval_rules.rego tests
`vendor_risk_band == "high"` *first*, ahead of every spend threshold, so a high-risk
supplier gets the long three-approver chain regardless of order value. That rule could
never fire on the automated path, because the document consumer passed
`vendor_risk_band=None` and OPA therefore received "unknown" on every request raised
from a document — exactly the failure the risk service's own docstring warns about
("an unearned 'low' would shorten a real approval chain"). Only a human typing the band
into the UI ever exercised it.

Failure is deliberately soft and explicit. If risk_intelligence is unreachable, or has
never assessed this vendor, the band is unknown — and unknown must not be silently
treated as low, because that is the same under-routing bug in a different disguise. The
caller receives None and OPA falls through to its value-based chain, which is the safe
default; the lookup failure is logged so it is visible rather than assumed.
"""
import logging

import requests

from app.config import settings

logger = logging.getLogger("approval_workflow.risk_client")

_VALID_BANDS = {"low", "medium", "high"}


def get_vendor_risk_band(vendor_id: str | None) -> str | None:
    """Returns "low" | "medium" | "high", or None when it cannot be established."""
    if not vendor_id:
        return None

    url = f"{settings.risk_intelligence_url}/risk/assessments/{vendor_id}/latest"
    try:
        response = requests.get(url, timeout=settings.risk_lookup_timeout_seconds)
    except requests.RequestException as exc:
        logger.warning("Risk lookup for vendor %s failed (%s) — routing without a band", vendor_id, exc)
        return None

    if response.status_code == 404:
        # Never assessed. Common for a brand-new vendor; not an error.
        logger.info("Vendor %s has no risk assessment yet — routing without a band", vendor_id)
        return None
    if response.status_code != 200:
        logger.warning(
            "Risk lookup for vendor %s returned HTTP %s — routing without a band",
            vendor_id, response.status_code,
        )
        return None

    try:
        payload = response.json()
    except ValueError:
        logger.warning("Risk lookup for vendor %s returned unparseable JSON", vendor_id)
        return None

    band = payload.get("risk_band")
    if band not in _VALID_BANDS:
        logger.warning("Risk lookup for vendor %s returned unexpected band %r", vendor_id, band)
        return None

    model_status = payload.get("model_status")
    if model_status not in {"validated", "synthetic_project"}:
        logger.warning(
            "Vendor %s risk band %s comes from an unvalidated model — routing without a band",
            vendor_id, band,
        )
        return None
    if model_status == "synthetic_project":
        logger.info("Vendor %s routing uses the project's synthetic baseline score", vendor_id)

    # A cold-start assessment is computed from little or no history. It is still the best
    # evidence available and is passed through, but it is worth being able to see in the
    # log which routings were backed by real observations and which were not.
    if payload.get("is_cold_start"):
        logger.info("Vendor %s risk band %s is cold-start (%s observations)",
                    vendor_id, band, payload.get("observation_count"))
    return band
