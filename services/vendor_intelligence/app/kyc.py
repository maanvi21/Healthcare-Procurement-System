"""Healthcare-vendor KYC checks, run at onboarding time.

Replaces generic KYC (as in the source procurement plan) with checks specific to
medical suppliers: drug-license validity/expiry, an FDA/CDSCO-style registration ID
format check, GSTIN format, and a sanctions/watchlist screening stub (a real deployment
would call an external watchlist API here — kept as a deterministic stub so the
onboarding decision path is fully testable without an external dependency).
"""
import re
from datetime import date

from app.models import VendorType

_GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
# CDSCO is itself five characters, so a 2-4 letter prefix could never match a real
# registration ID — every pharma distributor and equipment supplier was rejected as
# "format invalid" and stuck in pending_review forever, including the seed data.
_CDSCO_PATTERN = re.compile(r"^[A-Z]{2,6}-?\d{4,10}$")

# demo watchlist — in production this would be an external sanctions/debarment API call
_WATCHLIST = {"blacklisted medsupply co", "unverified pharma traders"}


def check_gstin(gstin: str | None) -> tuple[bool, str | None]:
    if not gstin:
        return False, "GSTIN not provided"
    if not _GSTIN_PATTERN.match(gstin.upper()):
        return False, "GSTIN format invalid"
    return True, None


def check_drug_license(license_number: str | None, expiry: date | None, vendor_type: VendorType) -> tuple[bool, str | None]:
    if vendor_type not in (VendorType.pharma_distributor,):
        return True, None  # not applicable to equipment/consumables/AMC vendors
    if not license_number:
        return False, "Drug license number not provided for a pharma distributor"
    if not expiry:
        return False, "Drug license expiry date not provided"
    if expiry < date.today():
        return False, f"Drug license expired on {expiry.isoformat()}"
    return True, None


def check_fda_cdsco(registration_id: str | None, vendor_type: VendorType) -> tuple[bool, str | None]:
    if vendor_type not in (VendorType.pharma_distributor, VendorType.equipment_supplier):
        return True, None
    if not registration_id:
        return False, "FDA/CDSCO registration ID not provided"
    if not _CDSCO_PATTERN.match(registration_id.upper()):
        return False, "FDA/CDSCO registration ID format invalid"
    return True, None


def check_watchlist(legal_name: str) -> tuple[bool, str | None]:
    if legal_name.strip().lower() in _WATCHLIST:
        return False, "Vendor appears on the sanctions/debarment watchlist"
    return True, None


def run_onboarding_checks(
    legal_name: str, vendor_type: VendorType, gst_number: str | None,
    drug_license_number: str | None, drug_license_expiry: date | None,
    fda_cdsco_registration_id: str | None,
) -> tuple[str, list[str]]:
    """Returns (decision, reasons) where decision is 'approved' | 'rejected' | 'pending_review'."""
    reasons: list[str] = []

    watchlist_ok, watchlist_reason = check_watchlist(legal_name)
    if not watchlist_ok:
        return "rejected", [watchlist_reason]

    gstin_ok, gstin_reason = check_gstin(gst_number)
    license_ok, license_reason = check_drug_license(drug_license_number, drug_license_expiry, vendor_type)
    cdsco_ok, cdsco_reason = check_fda_cdsco(fda_cdsco_registration_id, vendor_type)

    for ok, reason in [(gstin_ok, gstin_reason), (license_ok, license_reason), (cdsco_ok, cdsco_reason)]:
        if not ok:
            reasons.append(reason)

    if not reasons:
        return "approved", []
    # missing/invalid regulatory info -> human review rather than an automatic hard reject
    return "pending_review", reasons
