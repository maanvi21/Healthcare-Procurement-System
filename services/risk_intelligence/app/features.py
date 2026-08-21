"""Feature engineering for healthcare-vendor risk scoring.

Two groups of features, and the distinction matters:

**Vendor master data** — licence days-to-expiry, GSTIN validity, watchlist hit — pulled
from vendor_intelligence. Always available.

**Behavioural features** — spend, fraud and supplier signals derived in `app/analytics.py`
from a vendor's observation history (documents ingested, procurement raised, approvals
decided). These used to be hardcoded constants, which meant the model's "risk" was in
practice a restatement of licence expiry; they are now measured from platform events.

A vendor with no history yet falls back to the documented cold-start defaults in
`analytics.COLD_START`, and the resulting assessment is marked `is_cold_start` so nobody
mistakes an estimate for a measurement.

`cold_chain_violation_count` and `financial_health_score` remain caller-supplied: no
service in this build owns cold-chain telemetry or vendor financial statements, and
inventing them from procurement data would be fabrication. They stay as explicit inputs
for a WMS/ERP integration to supply.
"""
FEATURE_NAMES = [
    # --- vendor master data ---
    "license_days_to_expiry",
    "gstin_valid",
    "watchlist_hit",
    "years_in_business",
    # --- externally supplied operational signals ---
    "cold_chain_violation_count",
    "financial_health_score",
    "prior_compliance_flags",
    # --- measured: supplier behaviour ---
    "late_delivery_rate",
    # --- measured: fraud, carried over from document_intelligence's screen ---
    "doc_fraud_flag_rate",
    "doc_mean_fraud_score",
    "duplicate_invoice_rate",
    # --- measured: spend behaviour ---
    "log_total_spend",
    "spend_volatility",
    "spend_growth_ratio",
    "max_amount_zscore",
    "round_amount_rate",
    # --- measured: unsupervised anomaly signal ---
    "anomaly_score",
]


def build_feature_vector(
    license_days_to_expiry: float,
    gstin_valid: bool,
    watchlist_hit: bool,
    years_in_business: float,
    cold_chain_violation_count: int,
    financial_health_score: float,
    prior_compliance_flags: int,
    late_delivery_rate: float,
    doc_fraud_flag_rate: float,
    doc_mean_fraud_score: float,
    duplicate_invoice_rate: float,
    log_total_spend: float,
    spend_volatility: float,
    spend_growth_ratio: float,
    max_amount_zscore: float,
    round_amount_rate: float,
    anomaly_score: float,
) -> list[float]:
    return [
        float(license_days_to_expiry),
        1.0 if gstin_valid else 0.0,
        1.0 if watchlist_hit else 0.0,
        float(years_in_business),
        float(cold_chain_violation_count),
        float(financial_health_score),
        float(prior_compliance_flags),
        float(late_delivery_rate),
        float(doc_fraud_flag_rate),
        float(doc_mean_fraud_score),
        float(duplicate_invoice_rate),
        float(log_total_spend),
        float(spend_volatility),
        float(spend_growth_ratio),
        float(max_amount_zscore),
        float(round_amount_rate),
        float(anomaly_score),
    ]
