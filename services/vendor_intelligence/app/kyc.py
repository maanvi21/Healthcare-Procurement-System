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


# --------------------------------------------------------------- contact & address
# A vendor with no reachable contact cannot be sent a purchase order, a contract for
# e-signature, or an escalation notice — notification_agent resolves a recipient from
# contact_email/contact_phone and silently falls back to a shared default inbox when both
# are missing, so an unreachable vendor looks fine until someone wonders why a supplier
# never responded. Contact details are therefore validated at onboarding, not assumed.

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
# Indian mobile/landline in E.164 or local form: optional +91, then 6-9 leading digit.
_PHONE_PATTERN = re.compile(r"^(\+91[-\s]?)?[6-9]\d{9}$")
_PIN_PATTERN = re.compile(r"^[1-9]\d{5}$")

# Free-provider domains are a weak but real signal for a *business* supplier: a hospital's
# registered pharma distributor billing lakhs should not be reachable only at a personal
# gmail address. Not a hard reject on its own — it routes to human review.
_FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "rediffmail.com"}


def check_contact(contact_email: str | None, contact_phone: str | None) -> tuple[bool, str | None]:
    """At least one reachable channel, and anything supplied must be well-formed."""
    if not contact_email and not contact_phone:
        return False, "No contact email or phone provided — vendor is unreachable"
    if contact_email and not _EMAIL_PATTERN.match(contact_email.strip()):
        return False, "Contact email format invalid"
    if contact_phone:
        normalised = contact_phone.strip().replace(" ", "").replace("-", "")
        if not _PHONE_PATTERN.match(normalised):
            return False, "Contact phone must be a valid Indian number (+91 followed by 10 digits starting 6-9)"
    return True, None


def check_business_email(contact_email: str | None) -> tuple[bool, str | None]:
    if not contact_email or "@" not in contact_email:
        return True, None  # absence/format already handled by check_contact
    domain = contact_email.strip().rsplit("@", 1)[1].lower()
    if domain in _FREE_EMAIL_DOMAINS:
        return False, f"Contact email uses a personal provider ({domain}) rather than a business domain"
    return True, None


def check_address(
    address_line1: str | None, city: str | None, state: str | None,
    postal_code: str | None, country: str | None,
) -> tuple[bool, str | None]:
    """A registered business address is required — it appears on the contract, and the
    drug-licence issuing state must match the address state for the licence to be valid
    for that premises."""
    missing = [
        label for label, value in [
            ("address line 1", address_line1), ("city", city),
            ("state", state), ("postal code", postal_code),
        ] if not (value or "").strip()
    ]
    if missing:
        return False, f"Incomplete registered address — missing {', '.join(missing)}"
    if (country or "India").strip().lower() in ("india", "in") and not _PIN_PATTERN.match(postal_code.strip()):
        return False, "Postal code must be a valid 6-digit Indian PIN code"
    return True, None


def run_onboarding_checks(
    legal_name: str, vendor_type: VendorType, gst_number: str | None,
    drug_license_number: str | None, drug_license_expiry: date | None,
    fda_cdsco_registration_id: str | None,
    contact_email: str | None = None, contact_phone: str | None = None,
    address_line1: str | None = None, city: str | None = None,
    state: str | None = None, postal_code: str | None = None,
    country: str | None = None,
) -> tuple[str, list[str]]:
    """Returns (decision, reasons) where decision is 'approved' | 'rejected' | 'pending_review'.

    Contact/address parameters default to None so existing callers that predate these
    checks keep working; a vendor created without them lands in pending_review with an
    explicit reason rather than being silently approved as reachable.
    """
    reasons: list[str] = []

    watchlist_ok, watchlist_reason = check_watchlist(legal_name)
    if not watchlist_ok:
        return "rejected", [watchlist_reason]

    gstin_ok, gstin_reason = check_gstin(gst_number)
    license_ok, license_reason = check_drug_license(drug_license_number, drug_license_expiry, vendor_type)
    cdsco_ok, cdsco_reason = check_fda_cdsco(fda_cdsco_registration_id, vendor_type)
    contact_ok, contact_reason = check_contact(contact_email, contact_phone)
    business_email_ok, business_email_reason = check_business_email(contact_email)
    address_ok, address_reason = check_address(address_line1, city, state, postal_code, country)

    for ok, reason in [
        (gstin_ok, gstin_reason), (license_ok, license_reason), (cdsco_ok, cdsco_reason),
        (contact_ok, contact_reason), (business_email_ok, business_email_reason),
        (address_ok, address_reason),
    ]:
        if not ok:
            reasons.append(reason)

    if not reasons:
        return "approved", []
    # missing/invalid regulatory info -> human review rather than an automatic hard reject
    return "pending_review", reasons
