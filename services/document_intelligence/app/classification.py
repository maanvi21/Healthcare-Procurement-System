"""Rule-based document classifier baseline.

Scores OCR text against keyword sets per document type. This is intentionally a
transparent, auditable baseline (per ARCHITECTURE.md) rather than a trained model —
it is the pluggable seam where an ML/LLM classifier can later replace `classify()`
without changing any caller.
"""
from app.models import DocumentType

_KEYWORDS: dict[DocumentType, list[str]] = {
    DocumentType.invoice: ["invoice", "invoice no", "bill to", "amount due", "tax invoice"],
    DocumentType.purchase_order: ["purchase order", "po number", "ship to", "buyer", "p.o."],
    DocumentType.quotation: ["quotation", "quote", "valid until", "proforma"],
    DocumentType.compliance_certificate: [
        "certificate", "license", "registration", "cdsco", "fda", "gmp", "compliance",
    ],
}


def classify(text: str) -> tuple[DocumentType, float]:
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
