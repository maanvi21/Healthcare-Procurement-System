import React from "react";
import { Badge, Card, Col, Row } from "react-bootstrap";
import { Link } from "react-router-dom";

/**
 * Overview page, laid out as the platform's actual flow rather than as the team split
 * that produced it. A document enters at the top, and every agent below is shown in the
 * order it acts on that document — which is how the system behaves and how a new reader
 * needs to understand it. Who built what is a fact about the project, not about the
 * software, so it does not belong on the landing page.
 */

// The four stages every ingested document passes through inside document_intelligence,
// before any other agent sees it.
const intakeStages = [
  { n: "1", title: "OCR", detail: "PaddleOCR + OpenCV over PDFs and scans" },
  { n: "2", title: "Classification", detail: "Invoice, PO, quotation, delivery note, certificate" },
  { n: "3", title: "Validation", detail: "Field extraction, duplicates, fraud screen" },
  { n: "4", title: "Enrichment", detail: "Vendor resolved, confidence scored" },
];

// Agents in the order the architecture lays them out — which is also the order a
// procurement request travels through them.
const agents = [
  {
    key: "document",
    step: "01",
    name: "Document Intelligence",
    engine: "LLM + Rules",
    to: "/documents",
    linkLabel: "Review documents",
    status: "live",
    capabilities: [
      "OCR & layout analysis",
      "Text classification (PO / non-PO)",
      "Field extraction & validation",
      "Genuineness / fraud check",
      "Confidence scoring",
    ],
  },
  {
    key: "vendor",
    step: "02",
    name: "Vendor Intelligence",
    engine: "ML + Rules + External APIs",
    to: "/vendors",
    linkLabel: "Manage vendors",
    status: "partial",
    statusNote: "Contact & address validation not yet built",
    capabilities: [
      "Vendor onboarding",
      "KYC / KYB verification",
      "Contact & address validation",
      "Vendor behaviour analysis",
      "Vendor scoring",
    ],
  },
  {
    key: "approval",
    step: "03",
    name: "Approval Agent",
    engine: "Workflow + Rules",
    to: "/approvals",
    linkLabel: "Open approver inbox",
    status: "live",
    capabilities: [
      "Approval routing (OPA policy)",
      "Track pending approvals",
      "SLA escalation (Temporal)",
      "Email notifications",
      "Approval audit trail",
    ],
  },
  {
    key: "inventory",
    step: "04",
    name: "Inventory Intelligence",
    engine: "Rules + API",
    to: "/inventory",
    linkLabel: "View stock",
    status: "live",
    capabilities: [
      "Check availability",
      "Reserve / hold items",
      "Backorder handling",
      "Reorder suggestions",
      "Inventory alerts",
    ],
  },
  {
    key: "contract",
    step: "05",
    name: "Contract Intelligence",
    engine: "LLM + Template Engine",
    to: "/contracts",
    linkLabel: "Browse contracts",
    status: "live",
    capabilities: [
      "Generate contracts from templates",
      "Send for signature",
      "Track signature status",
      "Versioning & renewal",
      "Contract repository",
    ],
  },
  {
    key: "risk",
    step: "06",
    name: "Risk Analysis",
    engine: "ML + Analytics",
    to: "/risk",
    linkLabel: "See risk scores",
    status: "live",
    capabilities: [
      "Risk scoring (6 dimensions)",
      "Fraud detection",
      "Anomaly detection",
      "Supplier & spend risk",
      "Compliance risk",
    ],
  },
  {
    key: "notification",
    step: "07",
    name: "Notification Agent",
    engine: "Notification Engine",
    to: null,
    status: "planned",
    statusNote: "Not deployed — no service in this build",
    capabilities: [
      "Multi-channel notifications",
      "Email / SMS / Teams / Slack",
      "Templates",
      "Event-driven alerts",
      "Digest & summaries",
    ],
  },
];

const platform = [
  ["Kafka", "Event backbone between agents"],
  ["PostgreSQL", "Database per service"],
  ["Redis", "Locks & de-duplication"],
  ["MinIO", "Original document storage"],
  ["Temporal", "SLA timers & escalation"],
  ["Open Policy Agent", "Approval routing policy"],
  ["MLflow", "Risk model registry"],
  ["Nginx", "API gateway"],
];

const statusStyle = {
  live: { bg: "success", label: "live" },
  partial: { bg: "warning", label: "partial" },
  planned: { bg: "secondary", label: "planned" },
};

/**
 * Connector between intake stages. The stages sit in a row on wide screens and stack on
 * narrow ones, so the glyph has to follow the layout — a rightward arrow floating beside
 * a vertical stack reads as broken. Both are rendered and toggled by breakpoint rather
 * than measured in JS, so it stays correct through a resize with no reflow logic.
 */
function Arrow() {
  return (
    <>
      <div
        aria-hidden="true"
        className="text-muted d-none d-md-flex align-items-center justify-content-center"
        style={{ fontSize: "1.25rem", lineHeight: 1, padding: "0 0.5rem" }}
      >
        →
      </div>
      <div
        aria-hidden="true"
        className="text-muted d-flex d-md-none align-items-center justify-content-center"
        style={{ fontSize: "1.25rem", lineHeight: 1, padding: "0.25rem 0" }}
      >
        ↓
      </div>
    </>
  );
}

function AgentCard({ agent }) {
  const status = statusStyle[agent.status];
  const dimmed = agent.status === "planned";

  const body = (
    <Card
      className="h-100 shadow-sm"
      style={{ opacity: dimmed ? 0.65 : 1, borderTop: "3px solid var(--bs-primary)" }}
    >
      <Card.Body className="d-flex flex-column">
        <div className="d-flex justify-content-between align-items-start mb-1">
          <span className="text-muted fw-bold" style={{ fontSize: "0.75rem", letterSpacing: "0.05em" }}>
            {agent.step}
          </span>
          <Badge bg={status.bg}>{status.label}</Badge>
        </div>

        <Card.Title style={{ fontSize: "1rem" }} className="mb-1">
          {agent.name}
        </Card.Title>
        <div className="text-muted mb-2" style={{ fontSize: "0.75rem" }}>
          {agent.engine}
        </div>

        <ul className="list-unstyled small mb-2 flex-grow-1">
          {agent.capabilities.map((c) => (
            <li key={c} className="text-body-secondary mb-1">
              {c}
            </li>
          ))}
        </ul>

        {agent.statusNote && (
          <div className="small fst-italic text-muted mb-1">{agent.statusNote}</div>
        )}
        {agent.to && <div className="small fw-semibold">{agent.linkLabel} →</div>}
      </Card.Body>
    </Card>
  );

  return agent.to ? (
    <Link to={agent.to} className="text-decoration-none text-reset d-block h-100">
      {body}
    </Link>
  ) : (
    body
  );
}

export default function Home() {
  return (
    <div>
      <h1 className="mb-2">MediSource AI</h1>
      <p className="text-muted mb-4" style={{ maxWidth: "62rem" }}>
        An agentic procurement platform for hospital and health-system supply chains. A supplier
        document enters once and moves through seven agents on its own — read and verified, matched
        to a vendor, routed for approval, checked against ward stock, turned into a contract, and
        scored for risk. Every handoff below is a Kafka event, so each agent stays independently
        deployable.
      </p>

      {/* ---------- intake pipeline ---------- */}
      <h5 className="mb-1">Intake</h5>
      <p className="text-muted small mb-3">
        Uploads, email and API drops land in Kafka, then pass through four stages inside the
        document agent before any other agent sees them.
      </p>
      <div className="d-flex flex-column flex-md-row align-items-stretch mb-5">
        {intakeStages.map((stage, i) => (
          <React.Fragment key={stage.title}>
            <Card className="shadow-sm flex-grow-1" style={{ minWidth: "10rem", flexBasis: 0 }}>
              <Card.Body className="py-3">
                <div className="text-muted small fw-bold">{stage.n}</div>
                <div className="fw-semibold">{stage.title}</div>
                <div className="text-muted" style={{ fontSize: "0.78rem" }}>
                  {stage.detail}
                </div>
              </Card.Body>
            </Card>
            {i < intakeStages.length - 1 && <Arrow />}
          </React.Fragment>
        ))}
      </div>

      {/* ---------- agents ---------- */}
      <h5 className="mb-1">Agents</h5>
      <p className="text-muted small mb-3">
        Shown in the order they act on a request. Each is a separate service behind the API gateway.
      </p>
      <Row className="g-3 mb-5" xs={1} sm={2} lg={4}>
        {agents.map((agent) => (
          <Col key={agent.key}>
            <AgentCard agent={agent} />
          </Col>
        ))}
      </Row>

      {/* ---------- worked example ---------- */}
      <Card className="mb-5 shadow-sm">
        <Card.Body>
          <Card.Title style={{ fontSize: "1rem" }}>A pharma invoice, end to end</Card.Title>
          <ol className="small text-body-secondary mb-0 ps-3">
            <li>
              A distributor's invoice arrives. It is stored in MinIO, read with OCR, classified,
              field-extracted, duplicate-checked and fraud-screened, then matched to a known vendor.
              Anything low-confidence or unmatched waits in the review queue.
            </li>
            <li>
              A clean invoice raises a procurement request. Open Policy Agent picks the approver
              chain from spend, department and vendor risk; Temporal tracks the SLA and escalates.
            </li>
            <li>
              Ward and pharmacy stock is checked, available units reserved, and a backorder raised
              for the shortfall — respecting cold-chain items that cannot be split.
            </li>
            <li>
              On approval, a supply agreement or AMC is generated from a template and routed for
              e-signature, with versions and renewal dates tracked.
            </li>
            <li>
              Throughout, the risk agent scores the vendor from what actually happened — observed
              fraud rates, spend patterns, delivery timeliness — and flags anomalies for review.
            </li>
          </ol>
        </Card.Body>
      </Card>

      {/* ---------- platform ---------- */}
      <h5 className="mb-1">Platform</h5>
      <p className="text-muted small mb-3">Shared infrastructure every agent runs on.</p>
      <Row className="g-2" xs={2} md={4}>
        {platform.map(([name, detail]) => (
          <Col key={name}>
            <div className="border rounded p-2 h-100">
              <div className="fw-semibold small">{name}</div>
              <div className="text-muted" style={{ fontSize: "0.75rem" }}>
                {detail}
              </div>
            </div>
          </Col>
        ))}
      </Row>
    </div>
  );
}
