"""Regex-based structured field extraction over OCR'd text.

Healthcare-specific fields (drug batch number, expiry date, GSTIN) are extracted
alongside standard procurement-document fields (invoice/PO number, vendor name, total,
tax). Each field gets a heuristic confidence combining pattern-match strength with the
document's overall OCR confidence — this is what drives the manual-review queue.
"""
import re

_PATTERNS: dict[str, str] = {
    "invoice_number": r"invoice\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Za0-9\-\/]{3,25})",
    "po_number": r"(?:purchase order|p\.?o\.?)\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Za0-9\-\/]{3,25})",
    "date": r"(?:date|dated)\s*[:\-]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
    "total_amount": r"(?:grand total|total amount|amount due|total)\s*[:\-]?\s*(?:rs\.?|inr|₹|\$)?\s*([\d,]+\.\d{2}|[\d,]+)",
    "tax_amount": r"(?:gst|tax|vat)\s*(?:amount)?\s*[:\-]?\s*(?:rs\.?|inr|₹)?\s*([\d,]+\.\d{2}|[\d,]+)",
    "gstin": r"\bgstin?\s*[:\-]?\s*([0-9A-Z]{15})\b",
    "drug_batch_no": r"batch\s*(?:no\.?|number)?\s*[:\-]?\s*([A-Za0-9\-]{3,20})",
    "drug_expiry_date": r"exp(?:iry)?\s*(?:date)?\s*[:\-]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|[A-Za0-9]{3,9}\s+\d{4})",
    "drug_license_number": r"(?:drug licen[cs]e|dl)\s*(?:no\.?|number)?\s*[:\-]?\s*([A-Za0-9\-\/]{5,25})",
}

# fields whose absence is expected on most documents (only relevant to pharma invoices/
# compliance certs) — used to avoid penalizing overall extraction confidence when missing
_OPTIONAL_FIELDS = {"drug_batch_no", "drug_expiry_date", "drug_license_number"}


def extract_fields(text: str, ocr_confidence: float) -> dict[str, tuple[str, float]]:
    """Returns {field_name: (value, confidence)} for every pattern that matched."""
    results: dict[str, tuple[str, float]] = {}
    for field_name, pattern in _PATTERNS.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip()
        # confidence blends: pattern-match strength (fixed prior) x OCR text confidence
        pattern_prior = 0.9
        confidence = round(pattern_prior * max(ocr_confidence, 0.5), 2)
        results[field_name] = (value, confidence)

    vendor_name = _guess_vendor_name(text)
    if vendor_name:
        results["vendor_name"] = (vendor_name, round(0.6 * max(ocr_confidence, 0.5), 2))

    return results


def _guess_vendor_name(text: str) -> str | None:
    """Vendor name has no consistent label in free-form invoices; fall back to a
    'From:' / 'Supplier:' label match, else the first non-empty OCR line as a weak
    guess (flows into manual review at low confidence if wrong)."""
    match = re.search(r"(?:from|supplier|vendor)\s*[:\-]\s*(.+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip().splitlines()[0][:120]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return None


def missing_required_fields(doc_type: str, extracted: dict[str, tuple[str, float]]) -> list[str]:
    required = {
        "invoice": ["invoice_number", "vendor_name", "total_amount"],
        "purchase_order": ["po_number", "vendor_name"],
        "quotation": ["vendor_name", "total_amount"],
        "compliance_certificate": ["drug_license_number"],
    }.get(doc_type, [])
    return [f for f in required if f not in extracted]
