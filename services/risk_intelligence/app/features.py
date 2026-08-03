"""Feature engineering for healthcare-vendor risk scoring.

Features are the healthcare-specific signals named in ARCHITECTURE.md: license
days-to-expiry, cold-chain violation history, late-delivery rate, a financial-health
proxy, prior compliance flags, tenure, and identity-verification flags. Vendor master
data (license expiry, GSTIN presence) is pulled from vendor_intelligence; the
operational/financial signals (deliveries, cold-chain violations, financial health) are
not owned by any service in this build (no logistics/ERP integration exists yet) so they
are accepted as caller-supplied inputs with conservative defaults — this mirrors how a
real deployment would source them from a WMS/ERP integration once one exists.
"""
FEATURE_NAMES = [
    "license_days_to_expiry",
    "cold_chain_violation_count",
    "late_delivery_rate",
    "financial_health_score",
    "prior_compliance_flags",
    "years_in_business",
    "gstin_valid",
    "watchlist_hit",
]


def build_feature_vector(
    license_days_to_expiry: float,
    cold_chain_violation_count: int,
    late_delivery_rate: float,
    financial_health_score: float,
    prior_compliance_flags: int,
    years_in_business: float,
    gstin_valid: bool,
    watchlist_hit: bool,
) -> list[float]:
    return [
        float(license_days_to_expiry),
        float(cold_chain_violation_count),
        float(late_delivery_rate),
        float(financial_health_score),
        float(prior_compliance_flags),
        float(years_in_business),
        1.0 if gstin_valid else 0.0,
        1.0 if watchlist_hit else 0.0,
    ]
