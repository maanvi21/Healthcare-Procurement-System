"""File-system watcher for Input/Processed/Failed document folders.

This implements the "staff drops invoice.pdf into watched_documents/" scenario. The watcher
runs as a background thread alongside the Kafka consumer, scanning every 1–2 seconds for
new files. When a file appears it is:

  1. Read and stored in MinIO (same path the upload endpoint uses)
  2. Recorded in the database as a new Document with source=shared_folder
  3. Published to documents.ingested (triggering the same OCR/extraction pipeline)
  4. Leaves the source in Input until OCR/extraction finishes; the consumer moves it to
     Processed or Failed and records a failure sidecar when needed.

Thread-safety: the watcher uses its own SQLAlchemy session per file, just like the Kafka
consumer does. The only shared state is the telemetry dict, which is lock-protected.
"""
import hashlib
import logging
import os
import shutil
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.db import SessionLocal
from app.kafka_producer import publish_event
from app.models import Document, DocumentSource, DocumentStatus
from app import minio_client

logger = logging.getLogger("document_intelligence.file_watcher")

WATCH_DIR = os.environ.get("WATCH_DIR", "/app/watched_documents")
INPUT_DIR = os.path.join(WATCH_DIR, "Input")
PROCESSED_DIR = os.path.join(WATCH_DIR, "Processed")
FAILED_DIR = os.path.join(WATCH_DIR, "Failed")
POLL_INTERVAL = float(os.environ.get("WATCHER_POLL_INTERVAL", "1.5"))

_SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

_watcher_lock = threading.Lock()
_watcher_thread: threading.Thread | None = None

_watcher_telemetry = {
    "started_at": None,
    "is_running": False,
    "watch_dir": INPUT_DIR,
    "poll_interval_seconds": POLL_INTERVAL,
    "total_detected": 0,
    "total_ingested": 0,
    "total_failed": 0,
    "recent_files": deque(maxlen=50),
    "last_scan_at": None,
}


def record_watcher_event(
    filename: str,
    document_id: str | None,
    status: str,
    error: str | None = None,
) -> None:
    """Record a file watcher event for telemetry."""
    now = datetime.now(timezone.utc).isoformat()
    with _watcher_lock:
        _watcher_telemetry["total_detected"] += 1
        if error:
            _watcher_telemetry["total_failed"] += 1
        else:
            _watcher_telemetry["total_ingested"] += 1
        _watcher_telemetry["recent_files"].appendleft({
            "filename": filename,
            "document_id": document_id,
            "status": status,
            "error": error,
            "detected_at": now,
        })


def get_watcher_telemetry() -> dict:
    """Retrieve file watcher telemetry for the API."""
    with _watcher_lock:
        return {
            "is_running": _watcher_telemetry["is_running"],
            "watch_dir": _watcher_telemetry["watch_dir"],
            "poll_interval_seconds": _watcher_telemetry["poll_interval_seconds"],
            "started_at": _watcher_telemetry["started_at"],
            "total_detected": _watcher_telemetry["total_detected"],
            "total_ingested": _watcher_telemetry["total_ingested"],
            "total_failed": _watcher_telemetry["total_failed"],
            "last_scan_at": _watcher_telemetry["last_scan_at"],
            "recent_files": list(_watcher_telemetry["recent_files"]),
        }


def _content_type_for(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "application/pdf"
    elif ext in {".png"}:
        return "image/png"
    elif ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    elif ext in {".tif", ".tiff"}:
        return "image/tiff"
    elif ext in {".bmp"}:
        return "image/bmp"
    return "application/octet-stream"


def _ingest_file(filepath: str) -> None:
    """Ingest a single file: store in MinIO, create DB record, publish Kafka event."""
    filename = os.path.basename(filepath)
    logger.info("File watcher detected: %s", filename)

    document = None
    try:
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        if not file_bytes:
            logger.warning("Empty file skipped: %s", filename)
            _move_to_failed(filepath, "Empty file")
            record_watcher_event(filename, None, "failed", "Empty file")
            return

        content_hash = hashlib.sha256(file_bytes).hexdigest()
        content_type = _content_type_for(filename)
        object_key = f"watched/{uuid.uuid4()}/{filename}"

        # Upload to MinIO
        minio_client.upload_bytes(object_key, file_bytes, content_type)

        # Create database record
        db = SessionLocal()
        try:
            document = Document(
                source=DocumentSource.shared_folder,
                original_filename=filename,
                minio_object_key=object_key,
                content_hash=content_hash,
                status=DocumentStatus.received,
                watcher_input_path=filepath,
            )
            db.add(document)
            db.commit()
            db.refresh(document)

            # Publish Kafka event
            publish_event("documents.ingested", str(document.id), {
                "document_id": str(document.id),
                "source": "shared_folder",
                "filename": filename,
                "watcher": True,
            })

            record_watcher_event(filename, str(document.id), "ingested")
            logger.info(
                "File watcher ingested %s -> document %s",
                filename, document.id,
            )
        finally:
            db.close()

    except Exception as e:
        logger.exception("File watcher failed to ingest %s", filename)
        if document is not None:
            _persist_ingestion_failure(document.id, filepath, str(e))
        else:
            _move_to_failed(filepath, str(e))
        record_watcher_event(filename, None, "failed", str(e))


def _persist_ingestion_failure(document_id, filepath: str, reason: str) -> None:
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        moved = _move_to_failed(filepath, reason)
        if document:
            document.status = DocumentStatus.failed
            document.processing_error = reason[:4000]
            document.processed_at = datetime.utcnow()
            document.watcher_input_path = moved
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist ingestion failure for document %s", document_id)
    finally:
        db.close()


def _move_to_failed(filepath: str, reason: str) -> str | None:
    """Move an intake file to Failed and persist a human-readable sidecar reason."""
    if not os.path.exists(filepath):
        return None
    os.makedirs(FAILED_DIR, exist_ok=True)
    dest = os.path.join(FAILED_DIR, f"{time.time_ns()}_{os.path.basename(filepath)}")
    shutil.move(filepath, dest)
    with open(f"{dest}.error.txt", "w", encoding="utf-8") as error_file:
        error_file.write(reason[:4000])
    return dest


def finalize_watched_file(document: Document, outcome: str, error: str | None = None) -> str | None:
    """Move an ingested source file after the processing outcome is known."""
    source = document.watcher_input_path
    if not source or not os.path.exists(source):
        return source
    if outcome == "failed":
        return _move_to_failed(source, error or document.processing_error or "Processing failed")
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    dest = os.path.join(PROCESSED_DIR, f"{time.time_ns()}_{os.path.basename(source)}")
    shutil.move(source, dest)
    return dest


def _watch_loop() -> None:
    """Main watcher loop: scans the watched folder every POLL_INTERVAL seconds."""
    with _watcher_lock:
        _watcher_telemetry["started_at"] = datetime.now(timezone.utc).isoformat()
        _watcher_telemetry["is_running"] = True

    os.makedirs(WATCH_DIR, exist_ok=True)
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(FAILED_DIR, exist_ok=True)

    logger.info("File watcher started — watching %s (every %.1fs)", INPUT_DIR, POLL_INTERVAL)

    while True:
        try:
            with _watcher_lock:
                _watcher_telemetry["last_scan_at"] = datetime.now(timezone.utc).isoformat()

            for entry in os.scandir(INPUT_DIR):
                if not entry.is_file():
                    continue
                ext = Path(entry.name).suffix.lower()
                if ext not in _SUPPORTED_EXTENSIONS:
                    continue
                # Skip files still being written (< 0.5s old)
                try:
                    age = time.time() - os.path.getmtime(entry.path)
                    if age < 0.5:
                        continue
                except OSError:
                    continue

                _ingest_file(entry.path)

        except Exception:
            logger.exception("File watcher scan error")

        time.sleep(POLL_INTERVAL)


def start_watcher_thread() -> None:
    """Start the file watcher in a daemon thread."""
    global _watcher_thread
    _watcher_thread = threading.Thread(
        target=_watch_loop, daemon=True, name="document-file-watcher",
    )
    _watcher_thread.start()
