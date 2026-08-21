"""Groq-backed LLM classification, field extraction and fraud detection.

This is the "intelligent" half of the document agent: PaddleOCR (`app.ocr`) turns pixels
into text, and this module turns text into structured, audited procurement data.

Every call degrades gracefully. If `GROQ_API_KEY` is unset, the SDK is missing, or the
model returns something unparseable, the functions raise `LLMUnavailable` and the callers
in `app.classification` / `app.extraction` fall back to the deterministic rule-based
baselines. That keeps the service fully functional in an offline demo while giving a real
accuracy lift whenever a key is configured.
"""
import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)

_client = None


class LLMUnavailable(RuntimeError):
    """Raised when the LLM path cannot produce a usable answer — callers fall back."""


def is_enabled() -> bool:
    return bool(settings.llm_enabled and settings.groq_api_key)


def _get_client():
    """Lazy singleton so import-time never touches the network or requires a key."""
    global _client
    if _client is None:
        if not is_enabled():
            raise LLMUnavailable("GROQ_API_KEY not configured")
        try:
            from groq import Groq
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise LLMUnavailable(f"groq SDK not installed: {exc}") from exc
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def _complete(prompt: str) -> str:
    if not is_enabled():
        raise LLMUnavailable("LLM disabled")
    try:
        response = _get_client().chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
    except LLMUnavailable:
        raise
    except Exception as exc:
        raise LLMUnavailable(f"Groq request failed: {exc}") from exc
    return response.choices[0].message.content or ""


def _parse_json_response(result: str) -> dict:
    """Strip markdown code fences the model sometimes wraps JSON in, then parse."""
    result = result.strip()
    if result.startswith("```json"):
        result = result[7:]
    if result.startswith("```"):
        result = result[3:]
    if result.endswith("```"):
        result = result[:-3]
    try:
        parsed = json.loads(result.strip())
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"Model did not return valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LLMUnavailable("Model returned JSON that is not an object")
    return parsed


def classify_document(text: str) -> dict:
    """Classify document type using the LLM. Returns {document_type, confidence, reason}."""
    prompt = f"""
    You are a medical procurement document classifier.

    Classify the following document into one of these types:
    - INVOICE
    - PURCHASE_ORDER
    - QUOTATION
    - VENDOR_REGISTRATION
    - COMPLIANCE_CERTIFICATE
    - DELIVERY_NOTE
    - OTHER

    Document text:
    {text[:2000]}

    Respond with ONLY a JSON like this:
    {{
        "document_type": "INVOICE",
        "confidence": 0.95,
        "reason": "Contains invoice number, vendor details and total amount"
    }}
    """
    return _parse_json_response(_complete(prompt))


def extract_fields(text: str, document_type: str) -> dict:
    """Extract structured fields from document using the LLM."""
    prompt = f"""
    You are an AI assistant extracting information from a hospital procurement {document_type}.

    Extract the following fields from this document:
    - vendor_name
    - vendor_address
    - invoice_number (or PO number)
    - invoice_date
    - total_amount (number only)
    - tax_amount (number only)
    - line_items (list of items with name, quantity, unit_price)
    - drug_batch_number (if medical item)
    - expiry_date (if medical item)
    - payment_terms

    Document text:
    {text[:3000]}

    Respond with ONLY a JSON object with these fields.
    Use null for fields not found.
    For line_items use a list of objects.
    """
    return _parse_json_response(_complete(prompt))


def check_fraud(text: str, extracted_fields: dict) -> dict:
    """Check document for fraud indicators using the LLM."""
    prompt = f"""
    You are a fraud detection AI for hospital procurement documents.

    Analyze this document for fraud indicators such as:
    - Unusually high prices for medical items
    - Missing required fields
    - Inconsistent totals
    - Suspicious vendor details
    - Invalid drug license or batch numbers

    Document text:
    {text[:2000]}

    Extracted fields:
    {json.dumps(extracted_fields, indent=2, default=str)}

    Respond with ONLY a JSON like this:
    {{
        "fraud_detected": false,
        "fraud_score": 0.1,
        "flags": [],
        "recommendation": "Document appears genuine"
    }}
    """
    return _parse_json_response(_complete(prompt))
