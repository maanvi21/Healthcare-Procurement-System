"""Resolves an OCR'd vendor name to a vendor id via vendor_intelligence.

Documents carry a vendor *name*; every downstream service (approvals, contracts, risk)
keys off a vendor *id*. Without this step `documents.vendor_id` stays null forever and
the document→vendor→approval handoff never connects.

This is a synchronous HTTP call on the ingest path, which is a deliberate trade-off: the
lookup is a single indexed query and ingest is already dominated by OCR, so the added
latency is noise. It fails soft — an unreachable vendor service, a timeout, or an
ambiguous match all leave `vendor_id` null and let the document proceed to the review
queue, where a human can attach the right vendor. Ingest must never fail because vendor
lookup did.
"""
import logging

import requests

from app.config import settings

logger = logging.getLogger(__name__)


def resolve_vendor_id(vendor_name: str | None) -> str | None:
    """Returns a vendor id, or None if there is no confident match."""
    if not vendor_name or not vendor_name.strip():
        return None

    url = f"{settings.vendor_service_url.rstrip('/')}/vendors/resolve"
    try:
        response = requests.get(
            url, params={"legal_name": vendor_name}, timeout=settings.vendor_lookup_timeout
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        logger.warning("Vendor lookup failed for %r (%s) — leaving vendor_id unset", vendor_name, exc)
        return None
    except ValueError as exc:
        logger.warning("Vendor lookup returned non-JSON for %r: %s", vendor_name, exc)
        return None

    vendor_id = payload.get("vendor_id")
    if vendor_id:
        logger.info("Resolved vendor %r -> %s (%s match)", vendor_name, vendor_id, payload.get("match"))
    else:
        logger.info("No confident vendor match for %r (%s)", vendor_name, payload.get("reason"))
    return vendor_id
