"""Document classification: LLM-first, rule-based fallback.

`classify()` asks Groq to label the document (see `app.llm_extractor`). If no API key is
configured or the model is unreachable/unparseable, it falls back to the keyword-scoring
baseline below — a transparent, auditable classifier (per ARCHITECTURE.md) that needs no
network. Both paths return the same `(DocumentType, confidence)` tuple, so no caller has
to care which one ran.
"""
import logging

from app.llm_extractor import LLMUnavailable, classify_document
from app.models import DocumentType

logger = logging.getLogger(__name__)

# LLM label -> internal enum. The model is prompted with exactly these labels.
_LLM_TYPE_MAP: dict[str, DocumentType] = {
    "INVOICE": DocumentType.invoice,
    "PURCHASE_ORDER": DocumentType.purchase_order,
    "QUOTATION": DocumentType.quotation,
    "VENDOR_REGISTRATION": DocumentType.vendor_registration,
    "COMPLIANCE_CERTIFICATE": DocumentType.compliance_certificate,
    "DELIVERY_NOTE": DocumentType.delivery_note,
    "OTHER": DocumentType.unclassified,
}

_KEYWORDS: dict[DocumentType, list[str]] = {
    DocumentType.invoice: ["invoice", "invoice no", "bill to", "amount due", "tax invoice"],
    DocumentType.purchase_order: ["purchase order", "po number", "ship to", "buyer", "p.o."],
    DocumentType.quotation: ["quotation", "quote", "valid until", "proforma"],
    DocumentType.compliance_certificate: [
        "certificate", "license", "registration", "cdsco", "fda", "gmp", "compliance",
    ],
    DocumentType.vendor_registration: [
        "vendor registration", "supplier registration", "onboarding form", "empanelment",
    ],
    DocumentType.delivery_note: [
        "delivery note", "delivery challan", "goods received", "packing slip", "consignment",
    ],
}


def classify(text: str) -> tuple[DocumentType, float]:
    """Returns (document_type, confidence). Tries the LLM, falls back to keyword rules."""
    if not text.strip():
        return DocumentType.unclassified, 0.0

    try:
        result = classify_document(text)
        doc_type = _LLM_TYPE_MAP.get(str(result.get("document_type", "")).strip().upper())
        if doc_type is None:
            raise LLMUnavailable(f"unknown document_type {result.get('document_type')!r}")
        confidence = float(result.get("confidence") or 0.0)
        return doc_type, round(min(max(confidence, 0.0), 1.0), 2)
    except (LLMUnavailable, TypeError, ValueError) as exc:
        logger.info("LLM classification unavailable, using keyword rules: %s", exc)

    return classify_rule_based(text)


def classify_rule_based(text: str) -> tuple[DocumentType, float]:
    """Keyword-scoring baseline. Deterministic, offline, and always available."""
    lowered = text.lower()
    scores: dict[DocumentType, int] = {}
    for doc_type, keywords in _KEYWORDS.items():
        scores[doc_type] = sum(1 for kw in keywords if kw in lowered)

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    total_hits = sum(scores.values()) or 1

    if best_score == 0:
        return DocumentType.unclassified, 0.0

    confidence = best_score / total_hits if total_hits else 0.0
    # blend with an absolute-hit-count floor so a single strong keyword match on a short
    # document doesn't report artificially low confidence
    confidence = max(confidence, min(1.0, best_score / 3))
    return best_type, round(confidence, 2)
