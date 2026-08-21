"""Baseline vendor-risk model: a scikit-learn MultiOutputRegressor over
GradientBoostingRegressor predicting six risk dimensions (compliance, fraud, financial,
supplier, spend, operational) from the feature vector in `features.py`.

No labeled historical dataset exists yet for a from-scratch hospital procurement
deployment, so training data is synthesized from an explicit, documented rule-of-thumb
(`_synthetic_label`) plus noise — this keeps the *shape* of the ML pipeline (training,
MLflow tracking, versioned registry, inference against the registered model) genuinely
real and swappable, while being honest that the initial weights encode domain heuristics
rather than fitted historical risk outcomes. Once real labeled outcomes exist (e.g.
contracts that later had a compliance incident), `train_model()` is the exact same
entrypoint retrained against real data — nothing about the serving path changes.

The heuristics below are written against the *measured* features (fraud rates observed by
document_intelligence, spend volatility, anomaly score) rather than the constants the
model was previously fed, so the dimensions now separate on real behaviour.
"""
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor

from app.features import FEATURE_NAMES

RISK_DIMENSIONS = [
    "compliance_risk", "fraud_risk", "financial_risk",
    "supplier_risk", "spend_risk", "operational_risk",
]


def _synthetic_label(row: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    (license_days, gstin_valid, watchlist_hit, years_in_business,
     cold_chain_violations, financial_health, compliance_flags,
     late_rate, fraud_flag_rate, mean_fraud_score, duplicate_rate,
     log_spend, spend_volatility, spend_growth, max_zscore, round_rate,
     anomaly_score) = row

    compliance = np.clip(
        0.45 * (compliance_flags / 5)
        + 0.35 * max(0.0, (90 - license_days) / 90)
        + 0.20 * (1 - gstin_valid),
        0, 1,
    )
    # fraud is now driven by what document_intelligence actually flagged on this vendor's
    # paperwork, not solely by a watchlist name match
    fraud = np.clip(
        0.35 * watchlist_hit
        + 0.25 * fraud_flag_rate
        + 0.20 * mean_fraud_score
        + 0.12 * duplicate_rate
        + 0.08 * round_rate,
        0, 1,
    )
    financial = np.clip(0.75 * (1 - financial_health) + 0.25 * min(1.0, spend_volatility), 0, 1)
    supplier = np.clip(0.6 * late_rate + 0.4 * min(1.0, cold_chain_violations / 5), 0, 1)
    # spend risk: concentration and instability in what this vendor bills
    spend = np.clip(
        0.35 * min(1.0, spend_volatility)
        + 0.30 * min(1.0, max(0.0, spend_growth - 1.0) / 4.0)
        + 0.20 * min(1.0, max_zscore / 4.0)
        + 0.15 * min(1.0, log_spend / 8.0),
        0, 1,
    )
    operational = np.clip(
        0.4 * min(1.0, cold_chain_violations / 5)
        + 0.3 * max(0.0, (3 - years_in_business) / 3)
        + 0.3 * anomaly_score,
        0, 1,
    )

    noise = rng.normal(0, 0.03, size=len(RISK_DIMENSIONS))
    label = np.array([compliance, fraud, financial, supplier, spend, operational])
    return np.clip(label + noise, 0, 1)


def generate_training_data(n: int = 4000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = np.column_stack([
        rng.uniform(-30, 730, n),                 # license_days_to_expiry (negative = expired)
        rng.choice([0, 1], n, p=[0.1, 0.9]),      # gstin_valid
        rng.choice([0, 1], n, p=[0.97, 0.03]),    # watchlist_hit
        rng.uniform(0, 25, n),                    # years_in_business
        rng.poisson(0.7, n),                      # cold_chain_violation_count
        rng.beta(6, 3, n),                        # financial_health_score
        rng.poisson(0.5, n),                      # prior_compliance_flags
        rng.beta(2, 10, n),                       # late_delivery_rate
        rng.beta(1.5, 12, n),                     # doc_fraud_flag_rate
        rng.beta(1.5, 10, n),                     # doc_mean_fraud_score
        rng.beta(1.2, 20, n),                     # duplicate_invoice_rate
        rng.uniform(0, 8, n),                     # log_total_spend
        rng.gamma(2.0, 0.25, n),                  # spend_volatility
        rng.gamma(2.0, 0.6, n),                   # spend_growth_ratio
        rng.gamma(2.0, 0.8, n),                   # max_amount_zscore
        rng.beta(1.5, 12, n),                     # round_amount_rate
        rng.beta(1.5, 10, n),                     # anomaly_score
    ])
    assert X.shape[1] == len(FEATURE_NAMES), f"{X.shape[1]} columns vs {len(FEATURE_NAMES)} feature names"
    y = np.array([_synthetic_label(row, rng) for row in X])
    return X, y


def train_model() -> tuple[MultiOutputRegressor, dict]:
    X, y = generate_training_data()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = MultiOutputRegressor(GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.08, random_state=42))
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    mae = float(np.mean(np.abs(predictions - y_test)))
    metrics = {"mean_absolute_error": mae, "n_train": len(X_train), "n_test": len(X_test),
               "n_features": len(FEATURE_NAMES), "n_dimensions": len(RISK_DIMENSIONS)}
    return model, metrics


def predict_risk(model: MultiOutputRegressor, feature_vector: list[float]) -> dict[str, float]:
    """Returns each risk dimension as a probability-like score in [0, 1].

    The clip is load-bearing, not defensive tidying: gradient boosting extrapolates beyond
    the range of its training labels, so a very clean vendor genuinely produces small
    negative predictions. A negative "risk" is meaningless to every consumer, drags
    `overall_risk` below the true floor, and renders as a broken progress bar in the UI.
    """
    prediction = model.predict(np.array([feature_vector]))[0]
    clipped = np.clip(prediction, 0.0, 1.0)
    return {dim: float(round(score, 4)) for dim, score in zip(RISK_DIMENSIONS, clipped)}


def overall_risk_and_band(scores: dict[str, float], low_max: float, medium_max: float) -> tuple[float, str]:
    overall = float(round(sum(scores.values()) / len(scores), 4))
    if overall <= low_max:
        band = "low"
    elif overall <= medium_max:
        band = "medium"
    else:
        band = "high"
    return overall, band
