"""Fraud screening for ingested procurement documents.

Two layers, deliberately ordered cheapest-first:

1. Deterministic arithmetic/consistency checks that need no model at all — these catch
   the most common real-world invoice fraud (a total that doesn't match its line items)
   and always run, so fraud screening is never silently skipped in offline demos.
2. An LLM pass (`app.llm_extractor.check_fraud`) for the judgement calls a regex cannot
   make: implausible pricing for a medical item, suspicious vendor details, malformed
   drug-license numbers.

The two are merged: the union of both flag sets, and the max of both scores.
"""
import json
import logging

from app.llm_extractor import LLMUnavailable, check_fraud as llm_check_fraud

logger = logging.getLogger(__name__)


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("₹", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def _coerce_line_items(value) -> list:
    """`app.extraction` stores line_items as a JSON string (it is one column), so decode
    it back to a list before doing arithmetic on it."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    return value if isinstance(value, list) else []


def _rule_based_flags(extracted: dict) -> list[str]:
    flags: list[str] = []

    total = _to_float(extracted.get("total_amount"))
    tax = _to_float(extracted.get("tax_amount"))
    line_items = _coerce_line_items(extracted.get("line_items"))

    if total is not None and total <= 0:
        flags.append("total_amount is zero or negative")

    if total is not None and tax is not None and tax > total:
        flags.append("tax_amount exceeds total_amount")

    if line_items and total is not None:
        line_sum = 0.0
        priced_items = 0
        for item in line_items:
            if not isinstance(item, dict):
                continue
            quantity = _to_float(item.get("quantity")) or 0.0
            unit_price = _to_float(item.get("unit_price"))
            if unit_price is None:
                continue
            line_sum += quantity * unit_price
            priced_items += 1
        # only meaningful if we actually priced every line, and allow 5% headroom for
        # tax/rounding/shipping that the line items don't carry
        if priced_items == len(line_items) and line_sum > 0:
            if abs(line_sum - total) / max(total, 1.0) > 0.05 and line_sum > total:
                flags.append(
                    f"line items sum to {line_sum:.2f} but stated total is {total:.2f}"
                )

    if not extracted.get("vendor_name"):
        flags.append("no vendor name could be identified")

    return flags


def screen(text: str, extracted: dict) -> dict:
    """Returns {fraud_detected, fraud_score, flags, recommendation, engine}."""
    flags = _rule_based_flags(extracted)
    score = min(1.0, 0.25 * len(flags))
    recommendation = "Document appears genuine" if not flags else "Manual review recommended"
    engine = "rules"

    try:
        llm_result = llm_check_fraud(text, extracted)
    except LLMUnavailable as exc:
        logger.info("Fraud LLM pass unavailable, using rule-based flags only: %s", exc)
    else:
        engine = "llm+rules"
        llm_flags = llm_result.get("flags") or []
        if isinstance(llm_flags, list):
            flags = flags + [str(f) for f in llm_flags if str(f) not in flags]
        llm_score = _to_float(llm_result.get("fraud_score"))
        if llm_score is not None:
            score = max(score, min(1.0, max(0.0, llm_score)))
        if llm_result.get("recommendation"):
            recommendation = str(llm_result["recommendation"])
        if llm_result.get("fraud_detected"):
            score = max(score, 0.5)

    return {
        "fraud_detected": bool(flags) or score >= 0.5,
        "fraud_score": round(score, 2),
        "flags": flags,
        "recommendation": recommendation,
        "engine": engine,
    }
