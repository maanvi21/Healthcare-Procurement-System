import logging

import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

from app.config import settings
from app.model import train_model

logger = logging.getLogger("risk_intelligence.mlflow_utils")

_cached_model = None
_cached_version = None


def _client() -> MlflowClient:
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return MlflowClient(tracking_uri=settings.mlflow_tracking_uri)


def train_and_register() -> str:
    """Trains a fresh model, logs the run (params/metrics/artifact) to MLflow, registers
    a new version of `vendor_risk_model`, and promotes it to the Production stage."""
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment("vendor-risk-scoring")

    # MLflow tracks the active run in process-global state. If a previous training attempt
    # died partway (a failed artifact write, a dropped connection) that run can still be
    # marked active, and every later attempt then fails with "Run ... is already active"
    # — turning one transient failure into a permanently broken service. Close any
    # leftover run before starting a new one.
    if mlflow.active_run() is not None:
        logger.warning("Ending a leftover active MLflow run before retraining")
        mlflow.end_run()

    with mlflow.start_run() as run:
        model, metrics = train_model()
        mlflow.log_params({"n_estimators": 150, "max_depth": 3, "learning_rate": 0.08})
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(model, artifact_path="model", registered_model_name=settings.mlflow_model_name)
        run_id = run.info.run_id

    client = _client()
    versions = client.search_model_versions(f"name='{settings.mlflow_model_name}'")
    latest = max(versions, key=lambda v: int(v.version))
    client.transition_model_version_stage(
        name=settings.mlflow_model_name, version=latest.version, stage="Production", archive_existing_versions=True,
    )
    logger.info("Registered %s v%s as Production (run %s)", settings.mlflow_model_name, latest.version, run_id)
    return latest.version


def get_or_train_model():
    """Loads the current Production model from the MLflow registry, training and
    registering one on the spot if none exists yet (first boot of a fresh MLflow
    instance)."""
    global _cached_model, _cached_version
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    client = _client()

    try:
        versions = client.get_latest_versions(settings.mlflow_model_name, stages=["Production"])
    except Exception:
        versions = []

    if not versions:
        logger.info("No Production model registered yet — training an initial baseline model")
        version = train_and_register()
    else:
        version = versions[0].version

    if _cached_model is not None and _cached_version == version:
        return _cached_model, _cached_version

    model_uri = f"models:/{settings.mlflow_model_name}/Production"
    try:
        _cached_model = mlflow.sklearn.load_model(model_uri)
    except Exception:
        # The registry can outlive its artifacts: the tracking DB is persisted but the
        # artifact root is a local filesystem path, so a registered version can point at
        # files that are no longer there (a recreated container, a cleared volume). That
        # is recoverable — the model is reproducible from `train_model()` — but left
        # unhandled it makes *every* assessment fail with OSError, permanently, with no
        # way back short of editing the registry by hand. Retrain and re-register instead.
        logger.exception(
            "Registered model %s v%s could not be loaded — retraining and re-registering",
            settings.mlflow_model_name, version,
        )
        version = train_and_register()
        _cached_model = mlflow.sklearn.load_model(model_uri)
    _cached_version = version
    return _cached_model, _cached_version
