import React from "react";
import { Card, Col, Row } from "react-bootstrap";
import { Link } from "react-router-dom";

const teams = [
  {
    team: "Team A — Document & Vendor Intelligence",
    items: [
      { to: "/documents", label: "Document ingestion, OCR & review queue" },
      { to: "/vendors", label: "Medical vendor onboarding & KYC" },
    ],
  },
  {
    team: "Team B — Approval & Inventory Intelligence",
    items: [
      { to: "/approvals", label: "Approver inbox, SLA & escalation" },
      { to: "/inventory", label: "Ward/pharmacy stock, reservations & backorders" },
    ],
  },
  {
    team: "Team C — Contract & Risk Intelligence",
    items: [
      { to: "/contracts", label: "Contract generation & e-signature" },
      { to: "/risk", label: "Vendor risk scoring dashboard" },
    ],
  },
];

export default function Home() {
  return (
    <div>
      <h1 className="mb-3">MediSource AI</h1>
      <p className="text-muted mb-4">
        An agentic, AI-powered procurement automation platform for hospital &amp;
        health-system supply chains — document intelligence, approval &amp; inventory
        orchestration, and contract &amp; risk intelligence, unified in one app.
      </p>
      <Row className="g-4">
        {teams.map((t) => (
          <Col md={4} key={t.team}>
            <Card className="h-100 shadow-sm">
              <Card.Body>
                <Card.Title style={{ fontSize: "1.05rem" }}>{t.team}</Card.Title>
                <ul className="list-unstyled mt-3">
                  {t.items.map((item) => (
                    <li key={item.to} className="mb-2">
                      <Link to={item.to}>{item.label}</Link>
                    </li>
                  ))}
                </ul>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
