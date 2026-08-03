"""Background consumer: on `approval.approved`, fetches the full procurement request
(approval_workflow) and vendor profile (vendor_intelligence) over REST, then
auto-generates a draft Supply Agreement — the one cross-service synchronous read this
platform does, because contract generation genuinely needs data two other services own
and a Kafka event payload deliberately stays small (ids + minimal facts, not a full
denormalized snapshot)."""
import json
import logging
import threading
from datetime import date, timedelta

import requests

from app.config import settings
from app.db import SessionLocal
from app.models import TemplateType
from app.service import generate_contract

logger = logging.getLogger("contract_intelligence.kafka_consumer")

TOPICS = ["approval.approved"]


def _handle_approval_approved(data: dict) -> None:
    request_id = data.get("request_id")
    vendor_id = data.get("vendor_id")
    if not request_id or not vendor_id:
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
        return

    context = {
        "hospital_name": settings.hospital_name,
        "vendor_name": vendor_data.get("legal_name", "Unknown Vendor"),
        "items": request_data.get("items", []),
        "total_value": request_data.get("total_value"),
        "currency": request_data.get("currency", "INR"),
    }

    db = SessionLocal()
    try:
        generate_contract(
            db, TemplateType.supply_agreement, vendor_id, request_id, context,
            effective_date=date.today(), expiry_date=date.today() + timedelta(days=365),
            renewal_reminder_days=settings.default_renewal_reminder_days,
        )
        logger.info("Auto-generated contract draft for approved request %s", request_id)
    except Exception:
        logger.exception("Contract auto-generation failed for request %s", request_id)
    finally:
        db.close()


def _consume_loop():
    from kafka import KafkaConsumer

    consumer = KafkaConsumer(
        *TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="contract-intelligence",
    )
    for message in consumer:
        try:
            envelope = message.value
            if envelope.get("event") == "approval.approved":
                _handle_approval_approved(envelope.get("data", {}))
        except Exception:
            logger.exception("Failed to process Kafka message on %s", message.topic)


def start_consumer_thread() -> None:
    threading.Thread(target=_consume_loop, daemon=True, name="contract-approval-consumer").start()
