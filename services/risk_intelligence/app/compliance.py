"""Hard compliance policy overlays applied after statistical risk inference."""


GSTIN_COMPLIANCE_FLOOR = 0.80


def apply_gstin_compliance_floor(scores: dict[str, float], gstin_valid: bool) -> dict[str, float]:
    """Keep malformed or missing GSTINs from being hidden by unrelated low scores."""
    adjusted = dict(scores)
    if not gstin_valid:
        adjusted["compliance_risk"] = max(
            float(adjusted.get("compliance_risk", 0.0)), GSTIN_COMPLIANCE_FLOOR,
        )
    return adjusted
