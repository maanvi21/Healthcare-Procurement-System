"""Loads demo data through the running platform's own REST APIs (via the Nginx
gateway) — five medical vendors, hospital stock items with batches, a synthetic
pharma invoice (if `reportlab` is available) run through real OCR ingestion, risk
assessments, and one end-to-end procurement request that exercises approval routing +
inventory reservation together.

Run after `docker-compose up` (or via scripts/deploy.sh, which calls this
automatically): `python scripts/seed-data.py`
"""
import io
import os
import sys
import time

import requests

BASE = os.environ.get("GATEWAY_BASE_URL", "http://localhost")


def wait_for_gateway(timeout_seconds: int = 180) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            if requests.get(f"{BASE}/api/health/vendors", timeout=3).status_code == 200:
                print("Gateway is up.")
                return
        except requests.RequestException:
            pass
        time.sleep(3)
    print("Gateway did not become ready in time — seeding may fail.", file=sys.stderr)


VENDORS = [
    {
        "legal_name": "Apex Pharma Distributors", "vendor_type": "pharma_distributor",
        "gst_number": "27AAAAA0000A1Z5", "drug_license_number": "DL-20-2025-00123",
        "drug_license_expiry": "2027-06-30", "fda_cdsco_registration_id": "CDSCO-45231",
        "contact_email": "sales@apexpharma.example",
    },
    {
        "legal_name": "MediEquip Systems", "vendor_type": "equipment_supplier",
        "gst_number": "29BBBBB1111B1Z6", "fda_cdsco_registration_id": "CDSCO-98211",
        "contact_email": "orders@mediequip.example",
    },
    {
        "legal_name": "SafeCare Consumables Pvt Ltd", "vendor_type": "consumables_supplier",
        "gst_number": "07CCCCC2222C1Z7", "contact_email": "info@safecareconsumables.example",
    },
    {
        "legal_name": "BioServ Biomedical AMC", "vendor_type": "amc_contractor",
        "gst_number": "19DDDDD3333D1Z8", "contact_email": "support@bioserv.example",
    },
    {
        "legal_name": "Unverified Pharma Traders", "vendor_type": "pharma_distributor",
        "gst_number": "24EEEEE4444E1Z9", "drug_license_number": "DL-99-2020-00099",
        "drug_license_expiry": "2024-01-01",  # already expired — demonstrates a manual-review outcome
        "contact_email": "contact@unverifiedpharma.example",
    },
]

STOCK_ITEMS = [
    {"sku": "DRG-PARA-500", "name": "Paracetamol 500mg (strip of 10)", "category": "drug", "cold_chain": False, "reorder_point": 200, "reorder_qty": 1000},
    {"sku": "PPE-N95-MASK", "name": "N95 Respirator Mask", "category": "ppe", "cold_chain": False, "reorder_point": 500, "reorder_qty": 2000},
    {"sku": "CON-GLOVES-L", "name": "Surgical Gloves (Large, box of 100)", "category": "consumable", "cold_chain": False, "reorder_point": 100, "reorder_qty": 500},
    {"sku": "DRG-VACCINE-A", "name": "Vaccine Type A (cold-chain)", "category": "drug", "cold_chain": True, "reorder_point": 50, "reorder_qty": 200},
    {"sku": "EQP-VENTILATOR", "name": "ICU Ventilator", "category": "equipment", "cold_chain": False, "reorder_point": 2, "reorder_qty": 5},
]

BATCHES = {
    "DRG-PARA-500": [{"batch_no": "PARA-B1", "expiry_date": "2027-01-01", "quantity_on_hand": 5000}],
    "PPE-N95-MASK": [{"batch_no": "N95-B1", "expiry_date": None, "quantity_on_hand": 10000}],
    "CON-GLOVES-L": [{"batch_no": "GLV-B1", "expiry_date": None, "quantity_on_hand": 3000}],
    "DRG-VACCINE-A": [
        {"batch_no": "VAX-B1", "expiry_date": "2026-12-01", "quantity_on_hand": 150},
        {"batch_no": "VAX-B2", "expiry_date": "2027-03-01", "quantity_on_hand": 100},
    ],
    "EQP-VENTILATOR": [{"batch_no": "VENT-B1", "expiry_date": None, "quantity_on_hand": 8}],
}


def seed_vendors() -> list[dict]:
    created = []
    for vendor in VENDORS:
        resp = requests.post(f"{BASE}/api/vendors", json=vendor, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        created.append(data)
        print(f"Vendor onboarded: {data['legal_name']} -> {data['status']}")
    return created


def seed_inventory() -> None:
    for item in STOCK_ITEMS:
        resp = requests.post(f"{BASE}/api/inventory/stock-items", json=item, timeout=10)
        resp.raise_for_status()
        created = resp.json()
        print(f"Stock item created: {created['sku']}")
        for batch in BATCHES[item["sku"]]:
            requests.post(f"{BASE}/api/inventory/stock-items/{created['id']}/batches", json=batch, timeout=10).raise_for_status()
        print(f"  {len(BATCHES[item['sku']])} batch(es) added")


def seed_risk_assessments(vendors: list[dict]) -> None:
    for vendor in vendors:
        payload = {"vendor_id": vendor["id"]}
        resp = requests.post(f"{BASE}/api/risk/assess", json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Risk assessed for {vendor['legal_name']}: {data['risk_band']} ({data['overall_risk']})")
        else:
            print(f"Risk assessment skipped for {vendor['legal_name']}: {resp.status_code} {resp.text}")


def seed_sample_invoice() -> None:
    try:
        from reportlab.pdfgen import canvas
    except ImportError:
        print("reportlab not installed — skipping synthetic invoice OCR demo (pip install reportlab to enable).")
        return

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    lines = [
        "TAX INVOICE",
        "Invoice No: INV-2026-00842",
        "Date: 01/08/2026",
        "Supplier: Apex Pharma Distributors",
        "GSTIN: 27AAAAA0000A1Z5",
        "Batch No: PARA-B1",
        "Expiry Date: 01/2027",
        "Item: Paracetamol 500mg x 1000 strips",
        "Tax Amount: 4500.00",
        "Total Amount: 94500.00",
    ]
    y = 800
    for line in lines:
        c.drawString(72, y, line)
        y -= 24
    c.save()
    buffer.seek(0)

    files = {"file": ("apex-pharma-invoice.pdf", buffer, "application/pdf")}
    resp = requests.post(f"{BASE}/api/documents/ingest?source=upload", files=files, timeout=120)
    if resp.status_code == 200:
        data = resp.json()
        print(f"Sample invoice ingested -> status: {data['status']}, doc_type: {data['doc_type']}")
    else:
        print(f"Sample invoice ingestion failed: {resp.status_code} {resp.text}")


def seed_procurement_request(vendors: list[dict]) -> None:
    pharma_vendor = next(v for v in vendors if v["vendor_type"] == "pharma_distributor" and v["status"] == "approved")
    payload = {
        "requested_by": "dr.sharma@medisource.example",
        "department": "pharmacy",
        "category": "pharma",
        "vendor_id": pharma_vendor["id"],
        "vendor_risk_band": "low",
        "total_value": 94500.0,
        "items": [{"sku": "DRG-PARA-500", "quantity": 500, "description": "Paracetamol 500mg"}],
    }
    resp = requests.post(f"{BASE}/api/approvals/requests", json=payload, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        print(f"Procurement request submitted: {data['id']} -> {data['status']}, "
              f"{len(data['steps'])} approval step(s)")
    else:
        print(f"Procurement request seeding failed: {resp.status_code} {resp.text}")


def main() -> None:
    wait_for_gateway()
    vendors = seed_vendors()
    seed_inventory()
    time.sleep(2)  # let the risk_intelligence Kafka consumer's auto-assessment settle first
    seed_risk_assessments(vendors)
    seed_sample_invoice()
    seed_procurement_request(vendors)
    print("\nSeed data loaded. Open the app at", BASE)


if __name__ == "__main__":
    main()
