"""Background consumer: on `approval.approved`, fetches the full procurement request
(approval_workflow) and vendor profile (vendor_intelligence) over REST, then
auto-generates a draft Supply Agreement — the one cross-service synchronous read this
platform does, because contract generation genuinely needs data two other services own
and a Kafka event payload deliberately stays small (ids + minimal facts, not a full
denormalized snapshot)."""
import json
import logging
import threading
import time
import uuid
from datetime import date, timedelta

import requests

from app.config import settings
from app.db import SessionLocal
from app.models import Contract, ContractStatus, TemplateType
from app.service import dispatch_signature, generate_contract

logger = logging.getLogger("contract_intelligence.kafka_consumer")

TOPICS = ["approval.approved"]


def _handle_approval_approved(data: dict) -> None:
    request_id = data.get("request_id")
    vendor_id = data.get("vendor_id")
    if not request_id or not vendor_id:
        return
    # Kafka carries UUIDs as strings, while SQLAlchemy's PostgreSQL UUID columns use
    # uuid.UUID objects. Convert before querying/writing or an approved request can
    # fail at the DB bind step and never produce its contract.
    try:
        request_uuid = uuid.UUID(str(request_id))
        vendor_uuid = uuid.UUID(str(vendor_id))
    except (ValueError, TypeError, AttributeError):
        logger.error("Approval event contains invalid request/vendor UUIDs: request=%r vendor=%r", request_id, vendor_id)
        return

    try:
        request_resp = requests.get(f"{settings.approval_workflow_url}/approvals/requests/{request_id}", timeout=5)
        request_resp.raise_for_status()
        request_data = request_resp.json()

        vendor_resp = requests.get(f"{settings.vendor_intelligence_url}/vendors/{vendor_id}", timeout=5)
        vendor_resp.raise_for_status()
        vendor_data = vendor_resp.json()
    except requests.RequestException:
        logger.exception("Could not fetch request/vendor detail for approved request %s", request_id)
        raise

    context = {
        "hospital_name": settings.hospital_name,
        "vendor_name": vendor_data.get("legal_name", "Unknown Vendor"),
        "items": request_data.get("items", []),
        "total_value": request_data.get("total_value"),
        "currency": request_data.get("currency", "INR"),
    }

    db = SessionLocal()
    try:
        existing = db.query(Contract).filter(Contract.request_id == request_uuid).first()
        if existing:
            if existing.status == ContractStatus.draft and vendor_data.get("contact_email"):
                try:
                    dispatch_signature(
                        db, existing, vendor_data["contact_email"],
                        vendor_data.get("legal_name") or vendor_data.get("name") or "Supplier",
                    )
                except Exception as exc:
                    existing.signing_error = str(exc)[:4000]
                    db.commit()
                    logger.exception("Retrying signature dispatch failed for contract %s", existing.id)
            return
        contract = generate_contract(
            db, TemplateType.supply_agreement, vendor_uuid, request_uuid, context,
            effective_date=date.today(), expiry_date=date.today() + timedelta(days=365),
            renewal_reminder_days=settings.default_renewal_reminder_days,
        )
        signer_email = vendor_data.get("contact_email")
        signer_name = vendor_data.get("legal_name") or vendor_data.get("name") or "Supplier"
        if signer_email:
            try:
                dispatch_signature(db, contract, signer_email, signer_name)
                logger.info("Generated and sent contract %s for approved request %s", contract.id, request_id)
            except Exception as exc:
                contract.signing_error = str(exc)[:4000]
                db.commit()
                logger.exception("Contract generated but e-signature delivery failed for request %s", request_id)
        else:
            contract.signing_error = "Vendor profile has no contact_email; add a signer address and send from the CPanel."
            db.commit()
            logger.warning("Generated contract %s without signer email for request %s", contract.id, request_id)
    except Exception:
        logger.exception("Contract auto-generation failed for request %s", request_id)
        raise
    finally:
        db.close()


def _consume_loop():
    from kafka import KafkaConsumer, TopicPartition
    from kafka.structs import OffsetAndMetadata

    consumer = KafkaConsumer(
        *TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        # Process one approval at a time and commit only after contract creation (or
        # a persisted, actionable signing failure). Unhandled REST/database failures
        # are retried from their original Kafka offset instead of being lost.
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_records=1,
        group_id="contract-intelligence",
    )
    for message in consumer:
        try:
            envelope = message.value
            if envelope.get("event") == "approval.approved":
                _handle_approval_approved(envelope.get("data", {}))
        except Exception:
            logger.exception("Failed to process Kafka message on %s", message.topic)
            consumer.seek(TopicPartition(message.topic, message.partition), message.offset)
            time.sleep(5)
            continue
        consumer.commit({
            TopicPartition(message.topic, message.partition): OffsetAndMetadata(message.offset + 1, None)
        })


def start_consumer_thread() -> None:
    threading.Thread(target=_consume_loop, daemon=True, name="contract-approval-consumer").start()
