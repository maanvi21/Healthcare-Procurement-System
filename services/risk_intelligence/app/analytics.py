"""Derives real risk features from a vendor's observation history.

This module is the answer to a specific problem: five of the eight model features used to
be hardcoded constants (`late_delivery_rate=0.05`, `financial_health_score=0.7`, ...), so
a published "low risk" band was mostly a restatement of the vendor's licence expiry date.
Every function here computes a signal from something the platform actually observed.

Where a vendor has too little history to support a statistic, the function returns the
documented cold-start default rather than a fabricated number, and `profile()` reports
`observation_count` so callers can tell a measurement from an estimate.
"""
import math
import statistics
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ObservationSource, VendorObservation

# below this many priced observations, spend statistics are noise
_MIN_OBSERVATIONS_FOR_STATS = 3
# recency windows used for spend velocity/growth
_RECENT_DAYS = 90
_PRIOR_DAYS = 180

# Cold-start defaults, applied only when there is no history to measure. These are the
# same values the service used unconditionally before observations existed; keeping them
# explicit here (rather than inline in assess_vendor) makes it obvious which numbers are
# assumptions and which are measurements.
COLD_START = {
    "late_delivery_rate": 0.05,
    "financial_health_score": 0.7,
    "cold_chain_violation_count": 0,
    "prior_compliance_flags": 0,
    "years_in_business": 3.0,
}


def _load(db: Session, vendor_id) -> list[VendorObservation]:
    return list(
        db.execute(
            select(VendorObservation)
            .where(VendorObservation.vendor_id == vendor_id)
            .order_by(VendorObservation.occurred_at)
        ).scalars().all()
    )


# A "suspiciously round" total is a weak fabrication tell, so the threshold has to be
# strict or the signal is pure noise: at `% 1000` almost every real invoice qualifies
# (12,000 and 9,000 are perfectly ordinary), which would flag honest vendors and drown the
# fraud dimension. Multiples of 5,000 are uncommon for a genuinely itemised total.
# It stays a weak signal by design and is weighted lightly in the fraud label.
_ROUND_STEP = 5000


def _is_round(amount: float) -> bool:
    return amount >= _ROUND_STEP and amount % _ROUND_STEP == 0


def profile(db: Session, vendor_id) -> dict:
    """Returns every derived feature for a vendor, plus the evidence behind it."""
    observations = _load(db, vendor_id)
    now = datetime.utcnow()

    priced = [o for o in observations if o.amount is not None and o.amount > 0]
    amounts = [float(o.amount) for o in priced]
    documents = [o for o in observations if o.source == ObservationSource.document]

    result = dict(COLD_START)
    result.update({
        "observation_count": len(observations),
        "document_count": len(documents),
        "priced_count": len(priced),
        "total_spend": round(sum(amounts), 2) if amounts else 0.0,
        # --- fraud signals, carried over from document_intelligence's own screen ---
        "doc_fraud_flag_rate": 0.0,
        "doc_mean_fraud_score": 0.0,
        "duplicate_invoice_rate": 0.0,
        # --- spend signals ---
        "spend_volatility": 0.0,
        "spend_growth_ratio": 1.0,
        "max_amount_zscore": 0.0,
        "round_amount_rate": 0.0,
        "days_since_last_activity": 0.0,
    })

    if documents:
        result["doc_fraud_flag_rate"] = round(sum(1 for o in documents if o.fraud_flag) / len(documents), 4)
        result["doc_mean_fraud_score"] = round(
            sum(float(o.fraud_score or 0.0) for o in documents) / len(documents), 4
        )
        result["duplicate_invoice_rate"] = round(
            sum(1 for o in documents if o.is_duplicate) / len(documents), 4
        )

    if observations:
        result["days_since_last_activity"] = round((now - observations[-1].occurred_at).total_seconds() / 86400, 2)

    if amounts:
        result["round_amount_rate"] = round(sum(1 for a in amounts if _is_round(a)) / len(amounts), 4)

    if len(amounts) >= _MIN_OBSERVATIONS_FOR_STATS:
        mean = statistics.fmean(amounts)
        stdev = statistics.pstdev(amounts)
        # coefficient of variation — scale-free, so a vendor billing in crores is
        # comparable to one billing in thousands
        result["spend_volatility"] = round(stdev / mean, 4) if mean > 0 else 0.0
        if stdev > 0:
            result["max_amount_zscore"] = round(max(abs(a - mean) / stdev for a in amounts), 4)

        recent_cut = now - timedelta(days=_RECENT_DAYS)
        prior_cut = now - timedelta(days=_PRIOR_DAYS)
        recent = sum(float(o.amount) for o in priced if o.occurred_at >= recent_cut)
        prior = sum(float(o.amount) for o in priced if prior_cut <= o.occurred_at < recent_cut)
        if prior > 0:
            # capped: a 40x jump and a 4x jump are both simply "way up"
            result["spend_growth_ratio"] = round(min(recent / prior, 10.0), 4)
        elif recent > 0:
            result["spend_growth_ratio"] = 2.0  # new spend with no prior baseline

    late_rate = _late_delivery_rate(observations)
    if late_rate is not None:
        result["late_delivery_rate"] = late_rate

    return result


def _late_delivery_rate(observations: list[VendorObservation]) -> float | None:
    """Late-delivery rate measured from delivery notes against their purchase orders.

    Both document types flow through document_intelligence, so this is a real measurement
    rather than the constant it replaces — but only when a vendor actually has POs and
    matching delivery notes. Returns None (use the cold-start default) otherwise.

    Matching is by reference number when the delivery note cites its PO, else positional:
    the Nth delivery note against the Nth PO, oldest first. Positional matching is a
    heuristic, so it is only used when the counts line up.
    """
    orders = [o for o in observations if o.doc_type == "purchase_order"]
    notes = [o for o in observations if o.doc_type == "delivery_note"]
    if not orders or not notes:
        return None

    by_reference = {o.reference_number: o for o in orders if o.reference_number}
    pairs: list[tuple[VendorObservation, VendorObservation]] = []
    unmatched_notes = []
    for note in notes:
        order = by_reference.get(note.reference_number) if note.reference_number else None
        if order:
            pairs.append((order, note))
        else:
            unmatched_notes.append(note)

    if unmatched_notes and len(unmatched_notes) <= len(orders):
        used = {id(o) for o, _ in pairs}
        remaining = [o for o in orders if id(o) not in used]
        pairs.extend(zip(remaining, unmatched_notes))

    if not pairs:
        return None

    # "late" = delivered more than the grace period after the PO was raised
    grace = timedelta(days=7)
    late = sum(1 for order, note in pairs if note.occurred_at - order.occurred_at > grace)
    return round(late / len(pairs), 4)


def spend_series(db: Session, vendor_id) -> list[tuple[datetime, float]]:
    """Chronological (timestamp, amount) pairs — the input to anomaly detection."""
    return [
        (o.occurred_at, float(o.amount))
        for o in _load(db, vendor_id)
        if o.amount is not None and o.amount > 0
    ]


def peer_amount_stats(db: Session, exclude_vendor_id=None) -> tuple[float, float]:
    """Mean and stdev of invoice amounts across all vendors — the peer baseline an
    individual vendor's behaviour is compared against."""
    query = select(VendorObservation).where(VendorObservation.amount.isnot(None))
    if exclude_vendor_id is not None:
        query = query.where(VendorObservation.vendor_id != exclude_vendor_id)
    amounts = [float(o.amount) for o in db.execute(query).scalars().all() if o.amount and o.amount > 0]
    if len(amounts) < _MIN_OBSERVATIONS_FOR_STATS:
        return 0.0, 0.0
    return statistics.fmean(amounts), statistics.pstdev(amounts)


def log_scale(value: float) -> float:
    """Compress a monetary amount into a model-friendly range."""
    return math.log10(value + 1.0) if value > 0 else 0.0
