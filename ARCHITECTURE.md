# Architecture

## Style

Database-per-service microservices, integrated through a Kafka event backbone and fronted
by a single Nginx API gateway. Each service owns its own PostgreSQL database and exposes a
FastAPI REST API. Synchronous calls (gateway → service) are used for request/response UI
interactions; Kafka events are used for cross-service side effects (e.g. an approved
procurement request triggering contract generation and inventory reservation without those
services being directly coupled to `approval_workflow`).

```
                                   ┌────────────────────────┐
                                   │   React + Bootstrap     │
                                   │   frontend (SPA)        │
                                   └────────────┬────────────┘
                                                 │ HTTP
                                   ┌────────────▼────────────┐
                                   │   Nginx API Gateway      │
                                   │   /api/documents  ──────┼──► document_intelligence :8001
                                   │   /api/vendors    ──────┼──► vendor_intelligence   :8002
                                   │   /api/approvals  ──────┼──► approval_workflow     :8003
                                   │   /api/inventory  ──────┼──► inventory_intelligence:8004
                                   │   /api/contracts  ──────┼──► contract_intelligence :8005
                                   │   /api/risk       ──────┼──► risk_intelligence     :8006
                                   └───────────────────────────┘

  document_intelligence ──┐                                   ┌── contract_intelligence
  vendor_intelligence ────┤                                   ├── risk_intelligence
  approval_workflow ──────┼──────────►  Kafka  ◄───────────────┤
  inventory_intelligence ─┘         (event backbone)           └──

  Shared infra: PostgreSQL (db-per-service), Redis (locks/dedup), MinIO (documents/
  contracts object storage), Open Policy Agent (approval + compliance rules as code),
  Temporal (long-running approval workflows: reminders, timeouts, escalation), MLflow
  (risk-model experiment tracking).
```

## Services

### document_intelligence (Team A) — port 8001
Ingests documents (upload, and stubs for email/API/shared-folder intake), stores originals
in MinIO, runs PaddleOCR + OpenCV preprocessing, classifies the document type, extracts
structured fields (rule-based + regex extraction over OCR text, pluggable for an LLM
extractor later), computes per-field confidence, flags duplicates by content hash + vendor/
invoice-number match, and exposes a manual-review queue for low-confidence extractions.
Publishes `documents.ingested`, `documents.processed`.

### vendor_intelligence (Team A) — port 8002
Vendor master data for medical suppliers, pharma distributors and biomedical AMC
contractors. Onboarding validates drug-license number format/expiry, an FDA/CDSCO-style
registration ID, GST number, and a sanctions/watchlist stub check; produces an
approve/reject/manual-review outcome. Publishes `vendor.onboarded`, `vendor.updated`.

### approval_workflow (Team B) — port 8003
Evaluates OPA `approval_rules.rego` (spend threshold × department × vendor risk band) to
pick the approver chain, starts a Temporal workflow (`ApprovalWorkflow`) that waits for a
signal (approve/reject) with a timeout, escalates to the next approver on timeout, and
records full history. Redis is used to de-duplicate concurrent submissions of the same
request. Publishes `approval.requested`, `approval.approved`, `approval.rejected`,
`approval.escalated`.

### inventory_intelligence (Team B) — port 8004
Tracks ward/pharmacy stock by SKU + batch + expiry date. On a procurement request, checks
availability, reserves stock with a Redis lock (preventing double-reservation across
concurrent requests), releases expired reservations via a background sweep, and raises
backorder/reorder suggestions for shortfalls — cold-chain items are never partially
reserved across incompatible batches. Publishes `inventory.reserved`, `inventory.backorder`.

### contract_intelligence (Team C) — port 8005
Jinja2 contract templates (Supply Agreement, Biomedical Equipment AMC, Vendor Agreement,
NDA) populated from approved procurement + vendor data, stored in MinIO, sent through an
OpenSign-compatible e-signature client (real HTTP integration, pointed at a self-hosted
OpenSign instance via `OPENSIGN_BASE_URL`), with version/renewal/expiry tracking in
Postgres. Publishes `contract.generated`, `contract.signed`.

### risk_intelligence (Team C) — port 8006
scikit-learn gradient-boosted classifier scoring five risk dimensions (compliance, fraud,
financial, supplier, operational) from vendor + delivery-history + document features
specific to healthcare procurement (license days-to-expiry, cold-chain violation count,
late-delivery rate, financial-health proxy, prior compliance flags). Training runs are
logged to MLflow (params, metrics, model artifact); inference loads the latest
`Production`-stage model. Publishes `risk.assessed`.

## Cross-cutting

- **Kafka** topics are declared in `scripts/init-kafka-topics.sh` and documented in
  `SCHEMA.md`. Each service ships both a producer and (where relevant) a consumer.
- **OPA** policies live in `policies/opa/` and are loaded into the `opa` container at
  startup; services call `POST http://opa:8181/v1/data/...` for a decision.
- **Temporal** worker for `approval_workflow` runs as a second process
  (`temporal_worker.py`) alongside the FastAPI app in the same container.
- **MinIO** buckets: `documents`, `contracts` (created by `scripts/deploy.sh`).
- **Auth**: out of scope for this build (documented as a follow-up — a real deployment
  would put OAuth2/OIDC at the Nginx gateway); demo endpoints are unauthenticated.

## Explicitly deferred (see README "Scoping notes")

- Apache Spark distributed document processing — single-node OCR is sufficient at demo
  scale; the extraction pipeline is stateless per document so horizontal scaling by running
  more `document_intelligence` replicas covers realistic load before Spark would be needed.
- Label Studio — offline OCR/extraction model QA tool, not part of the deployed runtime.
- Full Team-D platform stack (Prometheus/Grafana/Loki, GitLab CE/Jenkins CI-CD, OpenBao,
  Terraform/Ansible, OpenProject) — only the "minimal deploy layer" was requested: compose
  + k8s manifests + migrations + `/health` endpoints on every service.
