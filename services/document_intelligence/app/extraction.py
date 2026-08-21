"""Structured field extraction over OCR'd text: LLM primary, regex backfill.

`extract_fields()` runs the Groq extractor (`app.llm_extractor`) and then fills any field
the model left null from the regex baseline below, so the two engines compose rather than
compete. With no API key configured the regex path runs alone and the service behaves
exactly as it did before the LLM was wired in.

Healthcare-specific fields (drug batch number, expiry date, GSTIN, drug licence number)
are extracted alongside standard procurement-document fields (invoice/PO number, vendor
name, total, tax). Each field carries a confidence — that is what drives the manual-review
queue.
"""
import json
import logging
import re

from app.llm_extractor import LLMUnavailable, extract_fields as llm_extract_fields

logger = logging.getLogger(__name__)

# LLM response key -> canonical internal field name, so LLM and regex results land in the
# same namespace and `missing_required_fields()` works identically for both engines.
_LLM_FIELD_MAP: dict[str, str] = {
    "vendor_name": "vendor_name",
    "vendor_address": "vendor_address",
    "invoice_number": "invoice_number",
    "invoice_date": "date",
    "total_amount": "total_amount",
    "tax_amount": "tax_amount",
    "line_items": "line_items",
    "drug_batch_number": "drug_batch_no",
    "expiry_date": "drug_expiry_date",
    "payment_terms": "payment_terms",
}

# Amount/currency tail shared by the money patterns: an optional currency marker, then
# the figure. Kept in one place so every money field parses "Rs.41300", "₹ 1,84,500.00"
# and "41300" identically.
_MONEY = r"(?:rs\.?|inr|₹|\$)?\s*([\d,]+\.\d{2}|[\d,]+)"

_PATTERNS: dict[str, str] = {
    "invoice_number": r"invoice\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Za-z0-9\-\/]{3,25})",
    "po_number": r"(?:purchase order|p\.?o\.?)\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Za-z0-9\-\/]{3,25})",
    "date": r"(?:date|dated)\s*[:\-]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
    "gstin": r"\bgstin?\s*(?:no\.?|number)?\s*[:\-]?\s*([0-9A-Z]{15})\b",
    "drug_batch_no": r"batch\s*(?:no\.?|number)?\s*[:\-]?\s*([A-Za-z0-9\-]{3,20})",
    "drug_expiry_date": r"exp(?:iry)?\s*(?:date)?\s*[:\-]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|[A-Za-z0-9]{3,9}\s+\d{4})",
    "drug_license_number": r"(?:drug licen[cs]e|dl)\s*(?:no\.?|number)?\s*[:\-]?\s*([A-Za-z0-9\-\/]{5,25})",
}

# Money fields need ordered alternatives rather than one alternation, because
# `re.search` returns the leftmost match and an itemised invoice reads
# "... Total: Rs.25000 ... Total Amount: Rs.41300" — a bare `total` alternation matches
# the first *line item* and silently reports a fraction of the real invoice value. Each
# list is tried in order and the first pattern that matches anywhere wins.
_ORDERED_PATTERNS: dict[str, list[str]] = {
    "total_amount": [
        # unambiguous grand-total labels, in decreasing specificity
        rf"(?:grand\s+total|total\s+amount|amount\s+due|net\s+payable|balance\s+due)\s*[:\-]?\s*{_MONEY}",
        # bare "total" only as a last resort, and anchored to a line whose label *ends*
        # there — so "Total:" matches but "Total Qty" does not
        rf"(?:^|\n)\s*total\s*[:\-]\s*{_MONEY}",
    ],
    "tax_amount": [
        # a colon must separate the label from the figure, so "Tax (18% GST): Rs.6300"
        # yields 6300 rather than the 18 from the rate in the label
        rf"(?:gst|tax|vat)[^\n:]{{0,24}}[:\-]\s*{_MONEY}",
    ],
}

# fields whose absence is expected on most documents (only relevant to pharma invoices/
# compliance certs) — used to avoid penalizing overall extraction confidence when missing
_OPTIONAL_FIELDS = {"drug_batch_no", "drug_expiry_date", "drug_license_number"}


def extract_fields(
    text: str, ocr_confidence: float, doc_type: str = "", classification_confidence: float = 0.0
) -> tuple[dict[str, tuple[str, float]], str]:
    """Returns ({field_name: (value, confidence)}, engine_name).

    The LLM result takes precedence; regex results backfill anything it left null. If the
    LLM is unavailable the regex result is returned on its own.
    """
    regex_fields = extract_fields_regex(text, ocr_confidence)

    try:
        raw = llm_extract_fields(text, doc_type or "document")
    except LLMUnavailable as exc:
        logger.info("LLM extraction unavailable, using regex baseline: %s", exc)
        return regex_fields, "rules"

    # LLM field confidence blends OCR legibility with how sure the classifier was about
    # what kind of document this is — a misclassified doc yields untrustworthy fields.
    llm_confidence = round(max(0.5, ocr_confidence) * max(0.5, classification_confidence or 0.5), 2)

    merged: dict[str, tuple[str, float]] = {}
    for llm_key, field_name in _LLM_FIELD_MAP.items():
        value = raw.get(llm_key)
        if value is None or value == "" or value == []:
            continue
        if isinstance(value, (list, dict)):
            value = json.dumps(value, default=str)
        merged[field_name] = (str(value).strip()[:2000], llm_confidence)

    for field_name, result in regex_fields.items():
        merged.setdefault(field_name, result)

    return merged, "llm"


def extract_fields_regex(text: str, ocr_confidence: float) -> dict[str, tuple[str, float]]:
    """Returns {field_name: (value, confidence)} for every pattern that matched."""
    results: dict[str, tuple[str, float]] = {}
    # confidence blends: pattern-match strength (fixed prior) x OCR text confidence
    confidence = round(0.9 * max(ocr_confidence, 0.5), 2)

    for field_name, pattern in _PATTERNS.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            results[field_name] = (match.group(1).strip(), confidence)

    for field_name, patterns in _ORDERED_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                results[field_name] = (match.group(1).strip(), confidence)
                break

    vendor_name, is_labelled = _guess_vendor_name(text)
    if vendor_name:
        # a labelled "Vendor: X" is worth far more than a guess at the first line; the
        # low confidence on a guess is what pushes the document into the review queue
        prior = 0.9 if is_labelled else 0.4
        results["vendor_name"] = (vendor_name, round(prior * max(ocr_confidence, 0.5), 2))

    return results


# document-type headers and section titles that are never a vendor name — the first
# non-empty line of an invoice is very often one of these
_NOT_A_VENDOR = {
    "invoice", "tax invoice", "proforma invoice", "purchase order", "quotation", "quote",
    "delivery note", "delivery challan", "credit note", "receipt", "bill", "statement",
    "certificate", "items", "item details", "bank details", "description",
}


def _guess_vendor_name(text: str) -> tuple[str | None, bool]:
    """Returns (vendor_name, was_labelled).

    Prefers an explicit label — note the optional `name`/`details` word, because real
    documents say "Vendor Name:" far more often than "Vendor:", and requiring the colon
    to touch the label made this miss the labelled name and fall through to the header.

    Falling back to the first non-empty line is still useful (many invoices lead with the
    supplier's letterhead) but it is a guess, so obvious document-type headers are skipped
    and the caller scores it low enough to force manual review.
    """
    match = re.search(
        r"(?:vendor|supplier|sold by|billed by|from)(?:\s+(?:name|details))?\s*[:\-]\s*(.+)",
        text, flags=re.IGNORECASE,
    )
    if match:
        candidate = match.group(1).strip().splitlines()[0].strip()
        if candidate:
            return candidate[:120], True

    for line in text.splitlines():
        stripped = line.strip(" \t:-")
        if not stripped or len(stripped) < 3:
            continue
        if stripped.lower() in _NOT_A_VENDOR:
            continue
        return stripped[:120], False
    return None, False


def missing_required_fields(doc_type: str, extracted: dict[str, tuple[str, float]]) -> list[str]:
    required = {
        "invoice": ["invoice_number", "vendor_name", "total_amount"],
        "purchase_order": ["po_number", "vendor_name"],
        "quotation": ["vendor_name", "total_amount"],
        "compliance_certificate": ["drug_license_number"],
        "vendor_registration": ["vendor_name"],
        "delivery_note": ["vendor_name"],
    }.get(doc_type, [])
    return [f for f in required if f not in extracted]
