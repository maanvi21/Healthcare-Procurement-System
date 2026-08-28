"""Plain-language reasons for each risk dimension's score, built from this vendor's own
measured feature values -- not a generic description of what the dimension means.

Important caveat: this is not a literal readout of the trained GradientBoostingRegressor's
internal decision path (that would require something like SHAP, which is out of scope
here). It mirrors the terms model.py's training-label formula (`_synthetic_label`) weighs
for each dimension -- license expiry and compliance flags for compliance, watchlist/fraud
signals for fraud, and so on -- checked against this vendor's actual measured values. The
model was trained to approximate that formula, and the feature/label correlations are
strong (see training_metrics.json), so this reflects what is actually driving the score in
the overwhelming majority of cases. It is a rule-based explanation layer, the same style
already used in app/anomaly.py's named rules, not model-internals attribution.
"""


def _get(features: dict, name: str, default: float = 0.0) -> float:
    return features.get(name, default)


def _compliance(f: dict) -> list[str]:
    reasons = []
    license_days = _get(f, "license_days_to_expiry", 365)
    if license_days < 0:
        reasons.append(f"Drug licence is already expired ({-int(license_days)} days overdue).")
    elif license_days < 90:
        reasons.append(f"Drug licence expires soon ({int(license_days)} days left).")
    if _get(f, "gstin_valid", 1) < 0.5:
        reasons.append("No valid GSTIN on file.")
    flags = _get(f, "prior_compliance_flags")
    if flags > 0:
        reasons.append(f"{int(flags)} prior compliance flag(s) on record.")
    if not reasons:
        reasons.append("Licence in good standing, valid GSTIN, no prior compliance flags.")
    return reasons


def _fraud(f: dict) -> list[str]:
    reasons = []
    if _get(f, "watchlist_hit") > 0.5:
        reasons.append("Vendor matches a sanctions/watchlist entry.")
    rate = _get(f, "doc_fraud_flag_rate")
    if rate > 0.15:
        reasons.append(f"{rate * 100:.0f}% of this vendor's documents were fraud-flagged.")
    dup = _get(f, "duplicate_invoice_rate")
    if dup > 0.10:
        reasons.append(f"{dup * 100:.0f}% of invoices look like duplicates.")
    rnd = _get(f, "round_amount_rate")
    if rnd > 0.15:
        reasons.append(f"{rnd * 100:.0f}% of invoices are suspiciously round amounts.")
    if not reasons:
        reasons.append("No fraud signals observed in documents reviewed so far.")
    return reasons


def _financial(f: dict) -> list[str]:
    reasons = []
    health = _get(f, "financial_health_score", 0.7)
    if health < 0.5:
        reasons.append(f"Financial health score is low ({health:.2f} of 1.0).")
    vol = _get(f, "spend_volatility")
    if vol > 0.7:
        reasons.append(f"Spend varies widely month to month (volatility {vol:.2f}).")
    if not reasons:
        reasons.append("Financial health and spend stability look normal.")
    return reasons


def _supplier(f: dict) -> list[str]:
    reasons = []
    late = _get(f, "late_delivery_rate", 0.05)
    if late > 0.2:
        reasons.append(f"{late * 100:.0f}% of deliveries arrived late.")
    cold = _get(f, "cold_chain_violation_count")
    if cold > 0:
        reasons.append(f"{int(cold)} cold-chain violation(s) recorded.")
    if not reasons:
        reasons.append("Deliveries have been on time with no cold-chain issues.")
    return reasons


def _spend(f: dict) -> list[str]:
    reasons = []
    growth = _get(f, "spend_growth_ratio", 1.0)
    if growth > 2:
        reasons.append(f"Recent spend is {growth:.1f}x the prior period.")
    z = _get(f, "max_amount_zscore")
    if z > 3:
        reasons.append("At least one invoice is a statistical outlier against this vendor's own history.")
    vol = _get(f, "spend_volatility")
    if vol > 0.7:
        reasons.append(f"Invoice amounts vary widely (volatility {vol:.2f}).")
    if not reasons:
        reasons.append("Spend pattern looks stable.")
    return reasons


def _operational(f: dict) -> list[str]:
    reasons = []
    years = _get(f, "years_in_business", 3.0)
    if years < 1:
        reasons.append(f"New vendor — only {years:.1f} year(s) on record.")
    cold = _get(f, "cold_chain_violation_count")
    if cold > 0:
        reasons.append(f"{int(cold)} cold-chain violation(s) recorded.")
    anomaly = _get(f, "anomaly_score")
    if anomaly > 0.5:
        reasons.append("Recent activity was flagged as statistically anomalous.")
    if not reasons:
        reasons.append("No operational red flags.")
    return reasons


_EXPLAINERS = {
    "compliance_risk": _compliance,
    "fraud_risk": _fraud,
    "financial_risk": _financial,
    "supplier_risk": _supplier,
    "spend_risk": _spend,
    "operational_risk": _operational,
}


def explain_scores(features: dict[str, float]) -> dict[str, list[str]]:
    """One or more plain-language reasons per risk dimension, from this vendor's own
    measured feature values. Returns {} when no feature snapshot exists (assessments
    created before this feature was added)."""
    if not features:
        return {}
    return {dim: fn(features) for dim, fn in _EXPLAINERS.items()}
