"""Unsupervised anomaly detection over vendor behaviour.

Distinct from the supervised risk dimensions in `model.py`, and deliberately so: that
model scores a vendor against patterns someone anticipated when the labels were written.
This one asks a different question — *is this vendor behaving unlike itself, or unlike its
peers?* — and so can surface a novel pattern for which every individual risk score looks
unremarkable.

Two layers, because they catch different things:

1. **IsolationForest** over the vendor's own priced-observation history. Trees isolate
   points that sit apart from the bulk of the data, which suits invoice amounts (heavily
   skewed, no useful distributional assumption).
2. **Explicit rules** for anomalies with a name a human can act on — a sudden spend jump,
   an invoice far outside peer norms, a burst of invoices in a short window. These carry
   reasons; a bare score nobody can interpret is not actionable in a procurement review.

Both degrade to "no anomaly" on thin history rather than inventing signal. Under roughly
eight priced observations, IsolationForest is fitting noise, so only the rules run.
"""
import logging
from datetime import timedelta

import numpy as np

logger = logging.getLogger("risk_intelligence.anomaly")

# IsolationForest needs a usable sample before its scores mean anything
_MIN_SAMPLES_FOR_FOREST = 8
# spend in the recent window this many times the prior window is worth flagging
_SPEND_SPIKE_RATIO = 3.0
# |z| against peer invoice amounts beyond which a single invoice is an outlier
_PEER_ZSCORE_LIMIT = 3.0
# more than this many invoices inside the burst window is unusual for one vendor
_BURST_COUNT = 5
_BURST_WINDOW_DAYS = 7


def _forest_score(amounts: list[float]) -> float:
    """Returns 0..1, higher = more anomalous. 0.0 when there is too little to fit."""
    if len(amounts) < _MIN_SAMPLES_FOR_FOREST:
        return 0.0
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:  # pragma: no cover - dependency guard
        logger.warning("scikit-learn unavailable — skipping IsolationForest")
        return 0.0

    features = np.array([[a, np.log10(a + 1.0)] for a in amounts])
    forest = IsolationForest(n_estimators=100, contamination="auto", random_state=42)
    forest.fit(features)
    # score_samples: less negative = more normal. Evaluate the most recent point.
    raw = float(forest.score_samples(features[-1:])[0])
    baseline = float(np.median(forest.score_samples(features)))
    if baseline == 0:
        return 0.0
    # how much more isolated the latest point is than a typical one
    deviation = (baseline - raw) / abs(baseline)
    return float(np.clip(deviation, 0.0, 1.0))


def detect(series: list[tuple], peer_mean: float, peer_stdev: float) -> dict:
    """`series` is chronological (timestamp, amount) pairs for one vendor.

    Returns {anomaly_score, anomaly_flag, reasons}.
    """
    reasons: list[str] = []
    if not series:
        return {"anomaly_score": 0.0, "anomaly_flag": False, "reasons": []}

    amounts = [amount for _, amount in series]
    timestamps = [ts for ts, _ in series]

    score = _forest_score(amounts)
    if score > 0.5:
        reasons.append(f"latest invoice is a statistical outlier against this vendor's own history (score {score:.2f})")

    # --- rule 1: spend spike, recent window vs the one before it ---
    if len(series) >= 4:
        latest = timestamps[-1]
        window = timedelta(days=90)
        recent = sum(a for ts, a in series if ts > latest - window)
        prior = sum(a for ts, a in series if latest - 2 * window < ts <= latest - window)
        if prior > 0 and recent / prior >= _SPEND_SPIKE_RATIO:
            reasons.append(f"spend rose {recent / prior:.1f}x versus the previous 90 days")
            score = max(score, min(1.0, 0.3 + 0.1 * (recent / prior)))

    # --- rule 2: single invoice far outside peer norms ---
    if peer_stdev > 0:
        z = abs(amounts[-1] - peer_mean) / peer_stdev
        if z >= _PEER_ZSCORE_LIMIT:
            reasons.append(f"latest invoice is {z:.1f} standard deviations from the peer-vendor average")
            score = max(score, min(1.0, 0.4 + 0.1 * z))

    # --- rule 3: burst of invoices in a short window ---
    if len(timestamps) >= _BURST_COUNT:
        cutoff = timestamps[-1] - timedelta(days=_BURST_WINDOW_DAYS)
        burst = sum(1 for ts in timestamps if ts >= cutoff)
        if burst > _BURST_COUNT:
            reasons.append(f"{burst} invoices submitted within {_BURST_WINDOW_DAYS} days")
            score = max(score, min(1.0, 0.3 + 0.05 * burst))

    score = round(float(np.clip(score, 0.0, 1.0)), 4)
    return {"anomaly_score": score, "anomaly_flag": bool(reasons), "reasons": reasons}
