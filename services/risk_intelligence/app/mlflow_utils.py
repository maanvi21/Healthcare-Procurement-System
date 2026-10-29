import logging
from pathlib import Path

import joblib

from app.config import settings

logger = logging.getLogger("risk_intelligence.mlflow_utils")

_cached_model = None
_cached_version = None


def _client():
    import mlflow
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return MlflowClient(tracking_uri=settings.mlflow_tracking_uri)


def train_and_register() -> str:
    """Synthetic labels are a development fixture and must never be promoted.

    Train offline with observed outcomes, validate on a vendor/time-separated holdout,
    then register and tag that artifact through the reviewed model promotion process.
    """
    raise RuntimeError(
        "Automatic risk-model training is disabled: the available training labels are "
        "synthetic rule outputs, not observed supplier outcomes. Register a model trained "
        "on labeled outcomes and mark it training_data_source=observed_outcomes and "
        "validation_passed=true before promotion."
    )


def get_or_train_model():
    """Load a validated registry model when available, else the project baseline.

    The baseline keeps this learning project runnable without real outcomes. Its
    provenance is carried in the version string so the UI and event consumers can
    distinguish it from an observed-outcome model.
    """
    global _cached_model, _cached_version
    client = None
    try:
        import mlflow
        import mlflow.sklearn

        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        client = _client()
        versions = client.get_latest_versions(settings.mlflow_model_name, stages=["Production"])
    except Exception as exc:
        logger.info("Could not read MLflow Production registry (%s); using project baseline", exc)
        versions = []

    if versions:
        version_info = versions[0]
        tags = getattr(version_info, "tags", {}) or {}
        if tags.get("training_data_source") == "observed_outcomes" and tags.get("validation_passed", "").lower() == "true":
            version = version_info.version
            model_version = f"observed:{version}"
            if _cached_model is not None and _cached_version == model_version:
                return _cached_model, _cached_version
            try:
                import mlflow.sklearn

                _cached_model = mlflow.sklearn.load_model(f"models:/{settings.mlflow_model_name}/{version}")
                _cached_version = model_version
                return _cached_model, _cached_version
            except Exception:
                logger.exception("Validated MLflow model v%s could not be loaded", version)
        else:
            logger.warning("MLflow Production model is not tagged as validated observed-outcome data")

    model_version = "synthetic:project-v1"
    if _cached_model is not None and _cached_version == model_version:
        return _cached_model, _cached_version
    artifact = Path(__file__).resolve().parents[1] / "models" / "Model_Synthetic" / "Synthetic_Model.pkl"
    if not artifact.is_file():
        raise RuntimeError(f"Project risk model artifact is missing: {artifact.name}")
    _cached_model = joblib.load(artifact)
    _cached_version = model_version
    logger.warning("Loaded project risk baseline trained on synthetic rule-derived labels")
    return _cached_model, _cached_version
