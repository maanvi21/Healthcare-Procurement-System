"""
Generates docs/Project_Proposal_MediSource_AI.pdf — the project proposal document,
adapted from the fcritprojects26 "AI-Powered Procurement Automation Platform" plan
(Teams A/B/C + minimal Team D) onto the hospital/health-system procurement domain.

Run: python scripts/generate_proposal_pdf.py
Requires: pip install reportlab
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
OUT_PATH = os.path.join(OUT_DIR, "Project_Proposal_MediSource_AI.pdf")

PRIMARY = colors.HexColor("#0B5B6B")
ACCENT = colors.HexColor("#0E7C86")
LIGHT = colors.HexColor("#EAF3F4")
TEXT = colors.HexColor("#1A1A1A")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleBig", fontSize=26, leading=32, textColor=PRIMARY,
                           spaceAfter=6, alignment=TA_CENTER, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="Subtitle", fontSize=13, leading=18, textColor=colors.HexColor("#444444"),
                           alignment=TA_CENTER, spaceAfter=4))
styles.add(ParagraphStyle(name="H1", fontSize=16, leading=20, textColor=PRIMARY,
                           spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="H2", fontSize=12.5, leading=16, textColor=ACCENT,
                           spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="Body", fontSize=10.2, leading=15, textColor=TEXT,
                           alignment=TA_JUSTIFY, spaceAfter=6))
styles.add(ParagraphStyle(name="BodyBold", parent=styles["Body"], fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="BulletText", fontSize=10.2, leading=14.5, textColor=TEXT,
                           alignment=TA_JUSTIFY))
styles.add(ParagraphStyle(name="Caption", fontSize=8.5, leading=11, textColor=colors.HexColor("#666666"),
                           alignment=TA_CENTER))
styles.add(ParagraphStyle(name="TOCEntry", fontSize=10.5, leading=18, textColor=TEXT))

story = []


def h1(text):
    story.append(Paragraph(text, styles["H1"]))


def h2(text):
    story.append(Paragraph(text, styles["H2"]))


def body(text):
    story.append(Paragraph(text, styles["Body"]))


def bullets(items):
    story.append(ListFlowable(
        [ListItem(Paragraph(i, styles["BulletText"]), bulletColor=ACCENT) for i in items],
        bulletType="bullet", start="circle", leftIndent=14, spaceBefore=2, spaceAfter=8,
    ))


def numbered(items):
    story.append(ListFlowable(
        [ListItem(Paragraph(i, styles["BulletText"])) for i in items],
        bulletType="1", leftIndent=14, spaceBefore=2, spaceAfter=8,
    ))


def table(head, rows, col_widths=None):
    data = [head] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))


def cell(text):
    return Paragraph(text, styles["BulletText"])


# ---------------------------------------------------------------- Title page
story.append(Spacer(1, 4 * cm))
story.append(Paragraph("MediSource AI", styles["TitleBig"]))
story.append(Paragraph("An Agentic AI-Powered Procurement Automation Platform", styles["Subtitle"]))
story.append(Paragraph("for Hospital &amp; Health-System Supply Chains", styles["Subtitle"]))
story.append(Spacer(1, 1.2 * cm))
story.append(Paragraph("PROJECT PROPOSAL", ParagraphStyle(
    name="TP2", fontSize=14, alignment=TA_CENTER, textColor=ACCENT,
    fontName="Helvetica-Bold", spaceAfter=6)))
story.append(Paragraph(
    "Adapted from the FCRIT Projects '26 Teamwise Plan — Team A (Document &amp; Vendor "
    "Intelligence), Team B (Approval &amp; Inventory Intelligence), Team C (Contract &amp; Risk "
    "Intelligence) and a minimal Team D (Platform &amp; Infrastructure) — re-specialized "
    "end to end for the <b>healthcare procurement domain</b>.",
    styles["Subtitle"]))
story.append(Spacer(1, 3 * cm))
story.append(Paragraph("Domain specialization: Hospital / Health-System Procurement Supply Chain", styles["Caption"]))
story.append(PageBreak())

# ---------------------------------------------------------------- 1. Executive Summary
h1("1. Executive Summary")
body(
    "Hospitals and health systems run procurement operations that are uniquely "
    "unforgiving of the inefficiencies that plague generic enterprise procurement: a "
    "stock-out of a critical drug or an expired cold-chain vaccine batch is not merely a "
    "cost overrun, it is a patient-safety incident. Yet most hospital procurement today "
    "still runs on manual document handling, email-based approvals, spreadsheet inventory "
    "tracking, and paper contract cycles with biomedical-equipment vendors and pharmaceutical "
    "distributors."
)
body(
    "<b>MediSource AI</b> proposes an agentic, AI-driven procurement automation platform "
    "purpose-built for this domain. It automates the complete source-to-pay lifecycle for "
    "hospital procurement — from an incoming supplier invoice to a signed, risk-assessed "
    "vendor contract — using intelligent document processing (OCR + extraction), rule-driven "
    "and workflow-orchestrated approvals, cold-chain-aware inventory reservation, templated "
    "contract generation with e-signature, and a machine-learning vendor risk model tuned to "
    "healthcare-specific risk factors (drug-license validity, cold-chain violations, delivery "
    "reliability for critical supplies)."
)
body(
    "The system is designed and delivered as three integrated application teams — "
    "<b>Document &amp; Vendor Intelligence</b>, <b>Approval &amp; Inventory Intelligence</b>, and "
    "<b>Contract &amp; Risk Intelligence</b> — unified into a single deployable platform, backed "
    "by a minimal but real platform/infrastructure layer (containerized services, an event "
    "backbone, and a one-command deployment)."
)

# ---------------------------------------------------------------- 2. Problem Statement
h1("2. Problem Statement")
body("Hospital procurement teams face challenges that compound the general problems named in "
     "the source plan, with healthcare-specific consequences:")

table(
    ["Challenge", "Generic Procurement Impact", "Healthcare-Specific Consequence"],
    [
        [cell("Manual document processing"), cell("Slow, error-prone data entry"),
         cell("Misread drug batch/expiry data risks dispensing expired stock")],
        [cell("Inefficient vendor onboarding"), cell("Long onboarding, fraud exposure"),
         cell("Unverified drug-license/FDA-CDSCO registration risks non-compliant suppliers")],
        [cell("Delayed procurement requests"), cell("Missed savings, slow cycles"),
         cell("Delayed restock of critical consumables/PPE during demand spikes")],
        [cell("Complex, email-based approvals"), cell("Bottlenecks, no SLA visibility"),
         cell("Emergency-equipment purchases stall in unstructured approval chains")],
        [cell("Limited risk visibility"), cell("Reactive risk management"),
         cell("Undetected cold-chain or delivery-reliability failures reach patient care")],
        [cell("Contract creation delays"), cell("Legal/administrative bottlenecks"),
         cell("Biomedical equipment AMC lapses leave critical devices unmaintained")],
        [cell("Manual signature collection"), cell("Slow execution, weak audit trail"),
         cell("No verifiable audit trail for regulatory/accreditation review (e.g. NABH/JCI)")],
        [cell("No end-to-end visibility"), cell("Slow, undocumented decisions"),
         cell("Procurement leadership cannot see exposure across drug/equipment supply chain")],
    ],
    col_widths=[4.6 * cm, 4.9 * cm, 6.2 * cm],
)

# ---------------------------------------------------------------- 3. Objectives
h1("3. Objectives")
numbered([
    "Automate ingestion, OCR extraction, and validation of hospital procurement documents "
    "(supplier invoices, purchase orders, quotations, drug-license/compliance certificates).",
    "Digitize and accelerate medical-vendor onboarding with healthcare-specific KYC "
    "(drug-license number and expiry, FDA/CDSCO-style registration ID, GST, sanctions/"
    "watchlist screening).",
    "Replace email-driven approvals with a policy-as-code, SLA-monitored, auto-escalating "
    "approval workflow spanning department, spend, and vendor-risk dimensions.",
    "Provide real-time ward/pharmacy inventory visibility with expiry- and cold-chain-aware "
    "stock reservation, backorder detection, and reorder suggestions.",
    "Auto-generate and route healthcare-specific contracts (Supply Agreement, Biomedical "
    "Equipment AMC, Vendor Agreement, NDA) for e-signature, with version/renewal/expiry "
    "tracking.",
    "Continuously score vendor risk across five dimensions — compliance, fraud, financial, "
    "supplier, and operational — using a trained ML model, surfaced before contract execution.",
    "Deliver the platform as a single, integrated, independently-deployable system rather "
    "than four disconnected team prototypes.",
])

# ---------------------------------------------------------------- 4. Scope
h1("4. Scope")
h2("4.1 In Scope")
bullets([
    "Team A — Document &amp; Vendor Intelligence: multi-source document ingestion, OCR "
    "(PaddleOCR) + OpenCV preprocessing, document classification, field extraction, "
    "confidence scoring, duplicate detection, manual-review queue, vendor onboarding &amp; "
    "profile management.",
    "Team B — Approval &amp; Inventory Intelligence: policy-driven (OPA) approval routing, "
    "Temporal-orchestrated SLA tracking and escalation, ward/pharmacy stock reservation "
    "(Redis-locked), expiry/cold-chain-aware reorder and backorder suggestions.",
    "Team C — Contract &amp; Risk Intelligence: templated contract generation, DocuSign-"
    "compatible e-signature integration, contract lifecycle tracking, scikit-learn vendor "
    "risk scoring with MLflow experiment tracking.",
    "Team D (minimal) — Platform: Docker Compose for local/demo deployment, Kubernetes "
    "manifests for a production-shaped deployment, a Kafka event backbone connecting all "
    "six services, an Nginx API gateway, database-per-service PostgreSQL, and one-command "
    "deploy scripts with health checks and seed data.",
])
h2("4.2 Out of Scope (this iteration)")
bullets([
    "Apache Spark distributed processing — deferred as a future scale-out path; single-node "
    "OCR/extraction is sufficient at the demo/pilot data volumes this proposal targets.",
    "Label Studio — an offline OCR/extraction model-quality tool, not a runtime dependency "
    "of the deployed platform.",
    "Full enterprise observability/CI-CD/IaC stack (Prometheus/Grafana/Loki, GitLab CE or "
    "Jenkins pipelines, OpenBao secrets management, Terraform/Ansible) — the platform ships "
    "with a minimal but real deploy layer (compose + Kubernetes manifests + migrations + "
    "health checks) rather than a full production observability suite.",
    "Authentication/authorization (OAuth2/OIDC) — flagged as a required addition before any "
    "real deployment; out of scope for the functional proof-of-concept.",
    "Integration with a live hospital ERP/EHR system — the platform is built to be "
    "integration-ready (documented REST APIs, Kafka events) but no live ERP/EHR connector "
    "is implemented in this phase.",
])

# ---------------------------------------------------------------- 5. Team-wise responsibilities
h1("5. Team-wise Responsibilities (Healthcare-Specialized)")

h2("Team A — Document &amp; Vendor Intelligence")
body(
    "Ingests procurement documents from upload, email, API, and shared-folder sources; runs "
    "PaddleOCR + OpenCV preprocessing; classifies documents as invoices, purchase orders, "
    "quotations, or compliance certificates; extracts vendor details, line items (including "
    "drug batch numbers and expiry dates), taxes, and totals; scores extraction confidence; "
    "flags duplicates; routes low-confidence fields to a manual-review UI. Separately manages "
    "medical-vendor onboarding: drug-license number/expiry validation, FDA/CDSCO-style "
    "registration ID checks, GST validation, and a sanctions/watchlist screening stub, "
    "producing an approve/reject/manual-review outcome per vendor."
)

h2("Team B — Approval &amp; Inventory Intelligence")
body(
    "Defines and evaluates approval rules as code (Open Policy Agent) — spend threshold, "
    "requesting department, and vendor risk band determine the approver chain. A Temporal "
    "workflow tracks each approval step's SLA deadline, sends reminders, and escalates to "
    "the next approver automatically on timeout. In parallel, checks ward/pharmacy stock "
    "availability, reserves units against a procurement request with a Redis lock to prevent "
    "double-reservation, releases expired reservations, and raises backorder/reorder "
    "suggestions for shortfalls — with cold-chain items never split across incompatible "
    "batches."
)

h2("Team C — Contract &amp; Risk Intelligence")
body(
    "Maintains reusable, Jinja2-templated contracts (Supply Agreement, Biomedical Equipment "
    "AMC, Vendor Agreement, NDA), auto-populates them from approved procurement and vendor "
    "data, and routes the populated contract through the DocuSign e-signature API "
    "flow, tracking version history, renewal reminders, and expiry dates. Independently, "
    "scores each vendor across five risk dimensions — compliance, fraud, financial, "
    "supplier, and operational — with a scikit-learn model whose training runs are tracked "
    "in MLflow; high-risk outcomes are surfaced to the contract manager before execution."
)

h2("Team D (minimal) — Platform &amp; Infrastructure")
body(
    "Provides the shared backbone every other team's service runs on: containerized "
    "services (Docker), a Kafka event bus connecting document, vendor, approval, inventory, "
    "contract, and risk services without tight coupling, database-per-service PostgreSQL, "
    "Redis for locks/deduplication, MinIO for document/contract object storage, an Nginx "
    "API gateway unifying all six services and the frontend behind one origin, and both a "
    "Docker Compose stack (local/demo) and Kubernetes manifests (production-shaped) with a "
    "single deploy script that runs migrations and seed data."
)

story.append(PageBreak())

# ---------------------------------------------------------------- 6. Architecture
h1("6. System Architecture")
body(
    "The platform follows a database-per-service microservice architecture. Each of the six "
    "services owns a private PostgreSQL database and exposes a FastAPI REST API for "
    "synchronous UI-driven interactions. Cross-service side effects — an approved "
    "procurement request triggering contract generation and inventory reservation, for "
    "example — flow asynchronously through Kafka events, keeping services independently "
    "deployable and avoiding direct service-to-service coupling."
)
h2("6.1 Component Diagram (textual)")
body(
    "React + Bootstrap SPA &#8594; Nginx API Gateway &#8594; six FastAPI services "
    "(document_intelligence, vendor_intelligence, approval_workflow, inventory_intelligence, "
    "contract_intelligence, risk_intelligence). All services share: Kafka (event backbone), "
    "Redis (locks/dedup), MinIO (document/contract storage), Open Policy Agent (approval + "
    "compliance rules), Temporal (long-running approval workflows), and MLflow (risk-model "
    "tracking). See <b>ARCHITECTURE.md</b> in the repository for the full diagram and "
    "per-service detail."
)
h2("6.2 End-to-End Flow (worked example)")
numbered([
    "A pharmaceutical distributor's invoice is ingested. Document Intelligence stores it in "
    "MinIO, runs OCR, classifies it as an <i>Invoice</i>, extracts vendor details, line items "
    "(drug batch/expiry), taxes, and total; low-confidence fields queue for manual review.",
    "The extracted data creates a procurement request. Approval Workflow evaluates OPA "
    "routing rules and starts a Temporal-tracked, SLA-bound approval chain.",
    "Inventory Intelligence checks ward/pharmacy stock, reserves available units, and raises "
    "a backorder/reorder suggestion for any shortfall, respecting cold-chain batch integrity.",
    "On approval, Contract Intelligence selects a Supply Agreement or AMC template, "
    "populates it, and routes it for e-signature, tracking version/renewal/expiry.",
    "In parallel, Risk Intelligence scores the vendor across five risk dimensions; high-risk "
    "results are surfaced to the contract manager before final execution.",
])

# ---------------------------------------------------------------- 7. Technology Stack
h1("7. Technology Stack")
table(
    ["Layer", "Technology", "Purpose"],
    [
        [cell("Document Processing"), cell("PaddleOCR, OpenCV, PyMuPDF"), cell("OCR, image preprocessing, PDF rendering")],
        [cell("Backend APIs"), cell("FastAPI (Python)"), cell("All six microservices")],
        [cell("Approval &amp; Compliance Rules"), cell("Open Policy Agent (Rego)"), cell("Policy-as-code for routing &amp; compliance")],
        [cell("Workflow Orchestration"), cell("Temporal"), cell("SLA tracking, reminders, escalation")],
        [cell("Event Backbone"), cell("Apache Kafka"), cell("Cross-service domain events")],
        [cell("Relational Storage"), cell("PostgreSQL (database-per-service)"), cell("Transactional data per service")],
        [cell("Caching / Locks"), cell("Redis"), cell("Reservation locks, dedup")],
        [cell("Object Storage"), cell("MinIO"), cell("Documents &amp; contracts")],
        [cell("Risk Modeling"), cell("scikit-learn, MLflow"), cell("Vendor risk scoring &amp; experiment tracking")],
        [cell("E-Signature"), cell("DocuSign eSignature API"), cell("Contract signature workflow")],
        [cell("Frontend"), cell("React, Bootstrap"), cell("Unified operator UI")],
        [cell("API Gateway"), cell("Nginx"), cell("Single-origin routing to all services")],
        [cell("Containerization"), cell("Docker / Docker Compose"), cell("Local &amp; demo deployment")],
        [cell("Orchestration"), cell("Kubernetes"), cell("Production-shaped deployment")],
    ],
    col_widths=[3.6 * cm, 5.6 * cm, 6.5 * cm],
)
body("All tools are free / open-source, consistent with the source plan's cost-efficiency principle.")

# ---------------------------------------------------------------- 8. Data Model Summary
h1("8. Data Model Summary")
body("Full entity-relationship detail is documented in <b>SCHEMA.md</b>. Summary per service:")
table(
    ["Service", "Core Entities"],
    [
        [cell("document_intelligence"), cell("documents, extracted_fields, duplicate_flags")],
        [cell("vendor_intelligence"), cell("vendors, vendor_documents")],
        [cell("approval_workflow"), cell("procurement_requests, approval_steps, approval_history")],
        [cell("inventory_intelligence"), cell("stock_items, stock_batches, reservations, backorders")],
        [cell("contract_intelligence"), cell("contract_templates, contracts, contract_events")],
        [cell("risk_intelligence"), cell("risk_assessments, risk_features_snapshot")],
    ],
    col_widths=[5 * cm, 10.7 * cm],
)

# ---------------------------------------------------------------- 9. Expected Outcomes
h1("9. Expected Business Outcomes")
table(
    ["Metric", "Target Improvement"],
    [
        [cell("Manual document-processing effort"), cell("70-90% reduction")],
        [cell("Document processing turnaround"), cell("60-80% faster")],
        [cell("Approval turnaround time"), cell("50-70% faster")],
        [cell("Vendor onboarding cycle time"), cell("Significantly reduced via automated KYC checks")],
        [cell("Stock-out / expired-stock incidents"), cell("Reduced via expiry- and cold-chain-aware reordering")],
        [cell("Contract execution time"), cell("Reduced via templated generation + e-signature")],
        [cell("Risk visibility"), cell("Proactive (pre-execution) instead of reactive")],
    ],
    col_widths=[7 * cm, 8.7 * cm],
)

# ---------------------------------------------------------------- 10. Deliverables
h1("10. Deliverables")
numbered([
    "Business case &amp; problem statement (this document, Sections 1-2).",
    "Requirement and scope documentation (this document, Sections 3-5; ARCHITECTURE.md).",
    "Schema documentation (SCHEMA.md).",
    "Architecture diagrams and technical documentation (ARCHITECTURE.md, README.md).",
    "Working source code for all six services, unified frontend, gateway, and policies.",
    "Kubernetes manifests and Docker Compose stack for deployment.",
    "One-command deploy script with database migrations and demo seed data.",
    "User manual and test-case documentation (delivered alongside the implementation).",
])

# ---------------------------------------------------------------- 11. Risks
h1("11. Risks &amp; Mitigations")
table(
    ["Risk", "Mitigation"],
    [
        [cell("OCR accuracy on poor-quality scans"), cell("Confidence scoring routes low-confidence fields to manual review rather than silently accepting bad data")],
        [cell("PaddleOCR model download requires internet on first run"), cell("Documented as a deployment prerequisite; models are cached after first pull")],
        [cell("Approval bottlenecks if escalation misconfigured"), cell("Temporal workflow makes SLA/escalation state inspectable and testable independent of business logic")],
        [cell("Vendor risk model trained on limited data"), cell("MLflow tracks every training run so model quality is versioned and auditable, not a black box")],
        [cell("No authentication in this phase"), cell("Explicitly documented as required before any real deployment; gateway is the designed insertion point for OAuth2/OIDC")],
    ],
    col_widths=[6.3 * cm, 9.4 * cm],
)

# ---------------------------------------------------------------- 12. Conclusion
h1("12. Conclusion")
body(
    "MediSource AI translates the FCRIT Projects '26 procurement-automation plan into a "
    "concrete, working system for a domain where procurement failures carry patient-safety "
    "consequences. By unifying Teams A, B, and C into one integrated, event-driven platform "
    "with a real (if intentionally minimal) deployment layer, the project delivers a "
    "demonstrable, end-to-end proof of agentic AI applied to healthcare supply-chain "
    "operations — ready to extend toward live ERP/EHR integration, authentication, and full "
    "production observability in a subsequent phase."
)

story.append(Spacer(1, 0.6 * cm))
story.append(Paragraph(
    "Repository docs: README.md, ARCHITECTURE.md, SCHEMA.md",
    styles["Caption"],
))


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm, f"MediSource AI — Project Proposal — Page {doc.page}")
    canvas.restoreState()


def build():
    os.makedirs(OUT_DIR, exist_ok=True)
    doc = SimpleDocTemplate(
        OUT_PATH, pagesize=A4,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
        title="MediSource AI - Project Proposal", author="MediSource AI Project Team",
    )
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    build()
