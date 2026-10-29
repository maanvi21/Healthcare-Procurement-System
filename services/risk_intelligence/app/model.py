"""Baseline vendor-risk model: a scikit-learn MultiOutputRegressor over
GradientBoostingRegressor predicting six risk dimensions (compliance, fraud, financial,
supplier, spend, operational) from the feature vector in `features.py`.

No labeled historical dataset exists yet for a from-scratch hospital procurement
deployment, so training data is synthesized from an explicit, documented rule-of-thumb
(`_synthetic_label`) plus noise — this keeps the *shape* of the ML pipeline (training,
MLflow tracking, versioned registry, inference against the registered model) genuinely
real and swappable, while being honest that the initial weights encode domain heuristics
rather than fitted historical risk outcomes. The synthetic generator and trainer are for
the learning project baseline. A separately trained observed-outcome artifact is preferred
when one is registered and validated.

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
    # An expired drug licence is a categorical compliance failure, not a gradient — a
    # hospital legally cannot buy from that supplier today. Weighted as one term among
    # three it topped out around 0.47, which after blending still read "low", so the
    # platform told the approval workflow to use the short chain for a vendor it should
    # have refused outright. Expiry therefore floors compliance risk near the top.
    if license_days < 0:
        compliance = max(compliance, 0.85)
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


def compute_bands(y: np.ndarray, low_max: float, medium_max: float) -> np.ndarray:
    """Vectorized band labels for a whole label/prediction matrix, using the exact blend
    rule (`overall_risk_and_band`) the live service applies to *predicted* scores — so a
    "true band" and a "predicted band" are always produced by the identical function, just
    fed different six-dimension vectors, and are safe to compare directly."""
    bands = np.empty(len(y), dtype=object)
    for i, row in enumerate(y):
        _, band = overall_risk_and_band(dict(zip(RISK_DIMENSIONS, row)), low_max, medium_max)
        bands[i] = band
    return bands


def compute_overall(y: np.ndarray, low_max: float, medium_max: float) -> np.ndarray:
    """Companion to `compute_bands` — the continuous overall_risk value (not just the
    band) for a whole label/prediction matrix. Needed anywhere a ranking score is wanted
    rather than a category, e.g. ROC curves, which need a continuous score to threshold."""
    overall = np.empty(len(y), dtype=float)
    for i, row in enumerate(y):
        value, _ = overall_risk_and_band(dict(zip(RISK_DIMENSIONS, row)), low_max, medium_max)
        overall[i] = value
    return overall


def generate_train_val_test(
    n: int = 4000,
    seed: int = 42,
    train_frac: float = 0.70,
    val_frac: float = 0.15,
    low_max: float = 0.34,
    medium_max: float = 0.67,
):
    """Splits `generate_training_data`'s pool into train / validation / test.

    Stratified by the *true* risk band (not a raw column — derived the same way a
    prediction's band is) rather than a plain random split. Without that, a rare class
    (e.g. `watchlist_hit` is only ~3% of rows, so "high" fraud_risk rows are scarce) can
    land almost entirely in one split by chance, leaving another split with too few
    examples of that band to say anything meaningful about it.

    Returns ((X_train, y_train), (X_val, y_val), (X_test, y_test)).
    """
    X, y = generate_training_data(n=n, seed=seed)
    bands = compute_bands(y, low_max, medium_max)

    test_frac = 1.0 - train_frac - val_frac
    X_trainval, X_test, y_trainval, y_test, bands_trainval, _ = train_test_split(
        X, y, bands, test_size=test_frac, random_state=seed, stratify=bands,
    )
    val_of_trainval = val_frac / (train_frac + val_frac)
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=val_of_trainval, random_state=seed, stratify=bands_trainval,
    )
    return (X_train, y_train), (X_val, y_val), (X_test, y_test)


def evaluate_model(model: MultiOutputRegressor, X: np.ndarray, y: np.ndarray, low_max: float, medium_max: float) -> dict:
    """Full evaluation on a held-out split: per-dimension regression metrics (this is a
    regressor, not a classifier — there's no single "confusion matrix" over 6 continuous
    0-1 scores), plus a genuine confusion matrix for the *risk band* (low/medium/high)
    obtained by blending the six predicted dimensions the same way the live service does
    and comparing it against the band the true labels would have produced.
    """
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        mean_absolute_error,
        mean_squared_error,
        precision_recall_fscore_support,
        r2_score,
    )

    preds = np.clip(model.predict(X), 0.0, 1.0)

    per_dimension = {}
    for i, dim in enumerate(RISK_DIMENSIONS):
        per_dimension[dim] = {
            "mae": float(mean_absolute_error(y[:, i], preds[:, i])),
            "rmse": float(mean_squared_error(y[:, i], preds[:, i]) ** 0.5),
            "r2": float(r2_score(y[:, i], preds[:, i])),
        }

    true_bands = compute_bands(y, low_max, medium_max)
    pred_bands = compute_bands(preds, low_max, medium_max)
    labels = ["low", "medium", "high"]
    cm = confusion_matrix(true_bands, pred_bands, labels=labels)
    precision, recall, f1, support = precision_recall_fscore_support(
        true_bands, pred_bands, labels=labels, zero_division=0,
    )

    return {
        "n_samples": len(X),
        "regression": per_dimension,
        "overall_mae": float(mean_absolute_error(y, preds)),
        "band_classification": {
            "labels": labels,
            "confusion_matrix": cm.tolist(),
            "accuracy": float(accuracy_score(true_bands, pred_bands)),
            "per_class": {
                labels[i]: {
                    "precision": float(precision[i]),
                    "recall": float(recall[i]),
                    "f1": float(f1[i]),
                    "support": int(support[i]),
                }
                for i in range(len(labels))
            },
        },
    }


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


# How much the single worst dimension counts toward the headline score. A plain mean let
# one severe risk be outvoted by the dimensions that happened to look fine: a vendor on the
# sanctions watchlist with an expired licence scored compliance 0.69 and fraud 0.37, yet
# averaged out to 0.26 — "low" — because the four dimensions with no evidence sat near
# zero and dragged it down. Risk does not average; a supplier is as risky as its worst
# problem. Blending the mean with the maximum keeps breadth meaningful while stopping a
# single severe finding from being diluted into nothing.
_WORST_DIMENSION_WEIGHT = 0.5

# a single dimension at or above this is treated as decisive on its own
_CRITICAL_DIMENSION = 0.80


def overall_risk_and_band(scores: dict[str, float], low_max: float, medium_max: float) -> tuple[float, str]:
    """Returns (overall_risk, band).

    `overall` blends the mean of the dimensions with the worst of them, so a vendor that is
    mildly poor everywhere and a vendor that is catastrophic in one place can both surface.
    """
    values = list(scores.values())
    mean = sum(values) / len(values)
    worst = max(values)
    overall = (1 - _WORST_DIMENSION_WEIGHT) * mean + _WORST_DIMENSION_WEIGHT * worst

    # Above this, a single dimension is not a contribution to an average — it is the
    # finding. A pharma distributor whose drug licence expired scores ~0.85 on compliance
    # and near zero elsewhere, because it has no trading history to be risky *about*;
    # blending still reported ~0.51, "medium", for a supplier the hospital cannot legally
    # buy from at all. A critical dimension therefore becomes the headline score outright,
    # rather than being tempered by the dimensions that had nothing to say.
    if worst >= _CRITICAL_DIMENSION:
        overall = worst
    overall = float(round(min(overall, 1.0), 4))

    if overall <= low_max:
        band = "low"
    elif overall <= medium_max:
        band = "medium"
    else:
        band = "high"
    return overall, band
