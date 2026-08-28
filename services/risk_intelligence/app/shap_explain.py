"""SHAP attribution for a single vendor's risk prediction.

Distinct from `app/explain.py`, and the difference matters:

* `explain.py` is a **rule-based** layer. It re-checks a handful of features a human
  decided were relevant per dimension and writes a sentence. It never consults the model,
  so it describes what *should* drive a score, not what did.
* This module asks the **trained model itself**. SHAP (SHapley Additive exPlanations)
  assigns each of the 17 features a signed contribution such that

      base_value + sum(contributions) == the model's actual prediction

  so nothing is hand-waved: the numbers reconcile exactly to what was served. The base
  value is the model's average output over its training distribution — i.e. what it would
  predict knowing nothing about this vendor — and each contribution is how much this
  vendor's particular feature value moved the score away from that.

`TreeExplainer` is used because every estimator here is a GradientBoostingRegressor;
for tree ensembles it computes exact Shapley values in polynomial time by walking the
trees, rather than the exponential brute-force the general definition implies.

The model is a MultiOutputRegressor, which holds one independent regressor per risk
dimension, so each dimension gets its own explainer and its own base value — a feature can
push compliance up while pushing spend down, and that is visible here.

Explainers are cached per model version: construction walks every tree in the ensemble and
would otherwise repeat on every request, while the trees only change when MLflow promotes
a new version.
"""
import logging

import numpy as np

from app.features import FEATURE_NAMES
from app.model import RISK_DIMENSIONS

logger = logging.getLogger("risk_intelligence.shap_explain")

_explainers: dict[str, list] = {}

# Features whose raw value is not self-explanatory in a UI get a friendlier rendering.
_PRETTY = {
    "license_days_to_expiry": "Days until drug licence expires",
    "gstin_valid": "GSTIN valid",
    "watchlist_hit": "Sanctions/watchlist hit",
    "years_in_business": "Years in business",
    "cold_chain_violation_count": "Cold-chain violations",
    "financial_health_score": "Financial health score",
    "prior_compliance_flags": "Prior compliance flags",
    "late_delivery_rate": "Late-delivery rate",
    "doc_fraud_flag_rate": "Document fraud-flag rate",
    "doc_mean_fraud_score": "Mean document fraud score",
    "duplicate_invoice_rate": "Duplicate-invoice rate",
    "log_total_spend": "Total spend (log scale)",
    "spend_volatility": "Spend volatility",
    "spend_growth_ratio": "Spend growth vs prior period",
    "max_amount_zscore": "Largest invoice (z-score)",
    "round_amount_rate": "Suspiciously-round invoice rate",
    "anomaly_score": "Anomaly score",
}


def _build_explainers(model, version: str):
    """One TreeExplainer per risk dimension. Returns None if shap is unavailable."""
    if version in _explainers:
        return _explainers[version]
    try:
        import shap
    except ImportError:  # pragma: no cover - dependency guard
        logger.warning("shap not installed — SHAP attribution unavailable")
        return None

    try:
        built = [shap.TreeExplainer(est) for est in model.estimators_]
    except Exception:
        logger.exception("Could not build SHAP explainers for model version %s", version)
        return None

    _explainers.clear()  # only the current version is ever needed
    _explainers[version] = built
    return built


def explain_prediction(model, version: str, feature_vector: list[float], top_n: int = 5) -> dict:
    """Per-dimension SHAP attribution for one vendor.

    Returns {} when shap is unavailable, so callers degrade to the rule-based
    explanations rather than failing an assessment.
    """
    explainers = _build_explainers(model, version)
    if explainers is None:
        return {}

    x = np.array([feature_vector], dtype=float)
    out: dict[str, dict] = {}

    for dim, explainer, estimator in zip(RISK_DIMENSIONS, explainers, model.estimators_):
        try:
            values = explainer.shap_values(x)
        except Exception:
            logger.exception("SHAP failed for dimension %s", dim)
            continue

        row = np.asarray(values)[0]
        base = float(np.asarray(explainer.expected_value).reshape(-1)[0])
        predicted = float(estimator.predict(x)[0])

        contributions = [
            {
                "feature": name,
                "label": _PRETTY.get(name, name),
                "value": round(float(raw), 4),
                "contribution": round(float(shap_value), 4),
                # a positive SHAP value pushes the risk score up
                "direction": "increases" if shap_value > 0 else "decreases",
            }
            for name, raw, shap_value in zip(FEATURE_NAMES, feature_vector, row)
        ]
        # rank by absolute impact — the biggest movers, in either direction
        contributions.sort(key=lambda c: abs(c["contribution"]), reverse=True)

        out[dim] = {
            "base_value": round(base, 4),
            "predicted": round(predicted, 4),
            # kept so a reader can verify base + sum(all contributions) == predicted,
            # which is the property that makes SHAP an exact decomposition rather than
            # an approximation
            "sum_contributions": round(float(row.sum()), 4),
            "top_contributions": [c for c in contributions[:top_n] if c["contribution"] != 0],
        }

    return out
