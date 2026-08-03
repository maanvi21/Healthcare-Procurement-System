# MediSource AI — Hospital Procurement Intelligence Platform

An agentic, AI-powered procurement automation platform for hospitals and health systems,
adapted from the generic "AI-Powered Procurement Automation Platform" plan onto the
**healthcare supply chain domain**: medical equipment, pharmaceuticals, PPE, consumables,
and biomedical-equipment service contracts.

It implements the three application-facing team scopes from the original plan as one
integrated system, plus a minimal deploy layer so it actually runs end to end:

| Team | Domain | Services in this repo |
|---|---|---|
| **Team A** — Document & Vendor Intelligence | Ingest supplier invoices/POs/quotations/compliance certs, OCR + extraction, vendor onboarding | `services/document_intelligence`, `services/vendor_intelligence` |
| **Team B** — Approval & Inventory Intelligence | Multi-level approvals with SLA/escalation, ward/pharmacy stock reservation & reorder | `services/approval_workflow`, `services/inventory_intelligence` |
| **Team C** — Contract & Risk Intelligence | Contract generation + e-signature, vendor risk scoring (compliance/fraud/financial/supplier/operational) | `services/contract_intelligence`, `services/risk_intelligence` |
| **Team D** (minimal) — Platform | docker-compose, Kubernetes manifests, one-command deploy, DB migrations | `infra/`, `k8s/`, `scripts/` |

## Why healthcare?

Every entity in the original generic procurement plan is re-specialized for a hospital's
supply chain:

- **Vendors** → medical equipment suppliers, pharmaceutical distributors, biomedical AMC
  contractors. Onboarding checks drug-license numbers, FDA/CDSCO-style registration IDs,
  GST, and sanctions/watchlist status instead of generic KYC.
- **Documents** → supplier invoices, purchase orders, quotations, drug-license certificates,
  cold-chain compliance certificates.
- **Inventory** → hospital ward/pharmacy stock (drugs, consumables, PPE, implants), with
  **expiry-date and cold-chain awareness** driving reorder points, not just quantity.
- **Contracts** → Supply Agreements, Biomedical Equipment AMC (Annual Maintenance Contract),
  Vendor Agreements, NDAs — templated and auto-populated from approved procurement data.
- **Risk** → vendor compliance risk (license expiry, regulatory standing), financial risk,
  fraud risk, supplier risk (on-time delivery, cold-chain violations), and operational risk.

## Tech stack (matches the original plan's tool choices)

- **OCR / documents**: PaddleOCR, OpenCV, MinIO, PostgreSQL, FastAPI, React + Bootstrap
- **Approvals / inventory**: FastAPI, Open Policy Agent, PostgreSQL, Redis, Temporal, Kafka
- **Contracts / risk**: OpenSign-style e-signature integration, MinIO, PostgreSQL, FastAPI,
  Open Policy Agent, scikit-learn, MLflow
- **Platform**: Docker Compose (local) + Kubernetes manifests (`k8s/`), Nginx API gateway,
  Kafka event backbone, PostgreSQL (database-per-service), Redis, MinIO

**Scoping notes** (see `ARCHITECTURE.md` for the full rationale):
- **Apache Spark** (listed for Team A's "distributed document processing") is not wired up.
  At this system's scale a single FastAPI worker pool comfortably handles OCR throughput;
  Spark is documented as the future scale-out path once document volume justifies a cluster.
- **Label Studio** (human-in-the-loop OCR labelling) is an offline MLOps tool for improving
  the extraction model over time, not a runtime dependency of the deployed app — it's
  documented as an optional add-on, not deployed by default.
- Monitoring/CI-CD/secrets-management/IaC (Prometheus/Grafana/Loki, GitLab CI/Jenkins,
  OpenBao, Terraform/Ansible) were explicitly scoped out as "minimal deploy layer" —
  the platform ships with docker-compose + Kubernetes manifests + migrations + health
  checks, not a full Team-D observability/CI stack.
- **OpenSign** itself is not bundled in `docker-compose.yml`/`k8s/` — self-hosting it
  requires its own Parse Server + MongoDB stack, a separate deployment concern from this
  platform. `contract_intelligence`'s `esign_client.py` makes real HTTP calls to
  `OPENSIGN_BASE_URL` (point it at your own instance to use it for real) and falls back
  to a locally-simulated signature envelope if unreachable, so the demo flow — including
  the "signed" webhook callback — works end to end without a live OpenSign deployment.

## Repository layout

```
medisource-ai (this repo)
├── services/
│   ├── document_intelligence/   # Team A — OCR, classification, extraction
│   ├── vendor_intelligence/     # Team A — vendor onboarding & profiles
│   ├── approval_workflow/       # Team B — approval routing, SLA, escalation
│   ├── inventory_intelligence/  # Team B — stock reservation, reorder
│   ├── contract_intelligence/   # Team C — contract generation, e-sign
│   └── risk_intelligence/       # Team C — vendor risk scoring
├── frontend/                    # React + Bootstrap unified UI
├── gateway/                     # Nginx API gateway config
├── policies/opa/                # Open Policy Agent rego policies
├── k8s/                         # Kubernetes manifests (production-shaped deploy)
├── scripts/                     # One-command deploy + seed data
├── docker-compose.yml           # Local dev / demo stack (16 containers)
└── ARCHITECTURE.md / SCHEMA.md  # Design docs
```

## Running it

```bash
cp .env.example .env
./scripts/deploy.sh        # Linux/Mac
# or
./scripts/deploy.ps1       # Windows PowerShell
```

This builds and starts every service via `docker-compose`, waits for Postgres/Kafka/MinIO
to be healthy, runs Alembic migrations for each service database, creates Kafka topics,
and loads demo seed data (one hospital, five medical vendors, a sample invoice, a sample
purchase request). The app is then available at **http://localhost** (Nginx gateway serves
the frontend at `/` and proxies `/api/*` to the six services). Temporal UI is at
`:8088`, MLflow UI at `:5000`, MinIO console at `:9001`, OPA at `:8181`.

For a Kubernetes deployment, see `k8s/README.md`.

## End-to-end flow (matches the plan's worked examples, re-skinned for healthcare)

1. A pharma distributor's invoice arrives (upload or `/api/documents/ingest`). Team A's
   `document_intelligence` service stores it in MinIO, runs PaddleOCR, classifies it as
   an *Invoice*, extracts vendor, line items (drug batch/expiry), taxes and total, checks
   for duplicates, and scores confidence per field. Low-confidence fields are queued for
   manual review.
2. The extracted data creates a **procurement request**. `approval_workflow` (Team B)
   evaluates OPA routing rules (spend threshold, department, vendor risk) to pick approvers,
   starts a Temporal workflow that tracks the SLA and escalates on timeout.
3. `inventory_intelligence` (Team B) checks ward/pharmacy stock, reserves available units
   (Redis lock), and raises a backorder/reorder suggestion for the shortfall — accounting
   for cold-chain items that can't be split across shipments.
4. Once approved, `contract_intelligence` (Team C) selects a Supply Agreement or AMC
   template, populates it from the approved request, and routes it through an OpenSign-style
   e-signature flow, tracking version/renewal/expiry.
5. In parallel, `risk_intelligence` (Team C) scores the vendor (compliance/fraud/financial/
   supplier/operational) using a scikit-learn model tracked in MLflow; high-risk results are
   surfaced to the contract manager before execution.

All inter-service handoffs are Kafka events (`documents.processed`,
`procurement.request.created`, `approval.approved`, `inventory.reserved`,
`contract.generated`, `risk.assessed`, …) so each service stays independently deployable.
