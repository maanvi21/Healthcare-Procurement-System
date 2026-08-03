"""Baseline vendor-risk model: a scikit-learn MultiOutputRegressor over
GradientBoostingRegressor predicting five risk dimensions (compliance, fraud, financial,
supplier, operational) from the feature vector in `features.py`.

No labeled historical dataset exists yet for a from-scratch hospital procurement
deployment, so training data is synthesized from an explicit, documented rule-of-thumb
(`_synthetic_label`) plus noise — this keeps the *shape* of the ML pipeline (training,
MLflow tracking, versioned registry, inference against the registered model) genuinely
real and swappable, while being honest that the initial weights encode domain heuristics
rather than fitted historical risk outcomes. Once real labeled outcomes exist (e.g.
contracts that later had a compliance incident), `train()` is the exact same entrypoint
retrained against real data — nothing about the serving path changes.
"""
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor

from app.features import FEATURE_NAMES

RISK_DIMENSIONS = ["compliance_risk", "fraud_risk", "financial_risk", "supplier_risk", "operational_risk"]


def _synthetic_label(row: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    (license_days, cold_chain_violations, late_rate, financial_health,
     compliance_flags, years_in_business, gstin_valid, watchlist_hit) = row

    compliance = np.clip(0.6 * (compliance_flags / 5) + 0.4 * max(0, (90 - license_days) / 90), 0, 1)
    fraud = np.clip(0.8 * watchlist_hit + 0.2 * (1 - gstin_valid), 0, 1)
    financial = np.clip(1 - financial_health, 0, 1)
    supplier = np.clip(0.6 * late_rate + 0.4 * min(1, cold_chain_violations / 5), 0, 1)
    operational = np.clip(0.5 * min(1, cold_chain_violations / 5) + 0.5 * max(0, (3 - years_in_business) / 3), 0, 1)

    noise = rng.normal(0, 0.03, size=5)
    return np.clip(np.array([compliance, fraud, financial, supplier, operational]) + noise, 0, 1)


def generate_training_data(n: int = 3000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = np.column_stack([
        rng.uniform(-30, 730, n),           # license_days_to_expiry (can be negative = already expired)
        rng.poisson(0.7, n),                # cold_chain_violation_count
        rng.beta(2, 10, n),                 # late_delivery_rate
        rng.beta(6, 3, n),                  # financial_health_score
        rng.poisson(0.5, n),                # prior_compliance_flags
        rng.uniform(0, 25, n),              # years_in_business
        rng.choice([0, 1], n, p=[0.1, 0.9]),  # gstin_valid
        rng.choice([0, 1], n, p=[0.97, 0.03]),  # watchlist_hit
    ])
    y = np.array([_synthetic_label(row, rng) for row in X])
    return X, y


def train_model() -> tuple[MultiOutputRegressor, dict]:
    X, y = generate_training_data()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = MultiOutputRegressor(GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.08, random_state=42))
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    mae = float(np.mean(np.abs(predictions - y_test)))
    metrics = {"mean_absolute_error": mae, "n_train": len(X_train), "n_test": len(X_test)}
    return model, metrics


def predict_risk(model: MultiOutputRegressor, feature_vector: list[float]) -> dict[str, float]:
    prediction = model.predict(np.array([feature_vector]))[0]
    return {dim: float(round(score, 4)) for dim, score in zip(RISK_DIMENSIONS, prediction)}


def overall_risk_and_band(scores: dict[str, float], low_max: float, medium_max: float) -> tuple[float, str]:
    overall = float(round(sum(scores.values()) / len(scores), 4))
    if overall <= low_max:
        band = "low"
    elif overall <= medium_max:
        band = "medium"
    else:
        band = "high"
    return overall, band
