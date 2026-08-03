import React, { useEffect, useState } from "react";
import { Badge, Button, Card, Col, Form, ProgressBar, Row, Table } from "react-bootstrap";
import { riskApi } from "../api/client.js";

const riskVariant = { low: "success", medium: "warning", high: "danger" };
const dimensions = [
  ["compliance_risk", "Compliance"], ["fraud_risk", "Fraud"], ["financial_risk", "Financial"],
  ["supplier_risk", "Supplier"], ["operational_risk", "Operational"],
];

export default function RiskDashboard() {
  const [assessments, setAssessments] = useState([]);
  const [form, setForm] = useState({
    vendor_id: "", cold_chain_violation_count: 0, late_delivery_rate: 0.05,
    financial_health_score: 0.7, prior_compliance_flags: 0, years_in_business: 3,
  });

  const load = () => riskApi.get("/assessments").then((res) => setAssessments(res.data)).catch(() => {});
  useEffect(load, []);

  const assess = async (e) => {
    e.preventDefault();
    await riskApi.post("/assess", {
      ...form,
      cold_chain_violation_count: parseInt(form.cold_chain_violation_count, 10),
      late_delivery_rate: parseFloat(form.late_delivery_rate),
      financial_health_score: parseFloat(form.financial_health_score),
      prior_compliance_flags: parseInt(form.prior_compliance_flags, 10),
      years_in_business: parseFloat(form.years_in_business),
    });
    load();
  };

  return (
    <div>
      <h2>Risk Intelligence</h2>
      <p className="text-muted">
        scikit-learn vendor risk model (compliance, fraud, financial, supplier, operational),
        tracked in MLflow. Assessments also run automatically whenever a vendor is onboarded
        or updated.
      </p>

      <Row className="g-4">
        <Col md={5}>
          <Card>
            <Card.Body>
              <Card.Title>Run an assessment</Card.Title>
              <Form onSubmit={assess}>
                <Form.Group className="mb-2"><Form.Label>Vendor ID</Form.Label>
                  <Form.Control required value={form.vendor_id} onChange={(e) => setForm({ ...form, vendor_id: e.target.value })} placeholder="uuid from Vendors page" /></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Cold-chain violations</Form.Label>
                  <Form.Control type="number" value={form.cold_chain_violation_count} onChange={(e) => setForm({ ...form, cold_chain_violation_count: e.target.value })} /></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Late delivery rate (0-1)</Form.Label>
                  <Form.Control type="number" step="0.01" value={form.late_delivery_rate} onChange={(e) => setForm({ ...form, late_delivery_rate: e.target.value })} /></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Financial health score (0-1, higher=better)</Form.Label>
                  <Form.Control type="number" step="0.01" value={form.financial_health_score} onChange={(e) => setForm({ ...form, financial_health_score: e.target.value })} /></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Prior compliance flags</Form.Label>
                  <Form.Control type="number" value={form.prior_compliance_flags} onChange={(e) => setForm({ ...form, prior_compliance_flags: e.target.value })} /></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Years in business</Form.Label>
                  <Form.Control type="number" value={form.years_in_business} onChange={(e) => setForm({ ...form, years_in_business: e.target.value })} /></Form.Group>
                <Button type="submit" className="mt-2">Assess vendor</Button>
              </Form>
            </Card.Body>
          </Card>
        </Col>

        <Col md={7}>
          <h5>Recent assessments</h5>
          {assessments.map((a) => (
            <Card key={a.id} className="mb-3">
              <Card.Body>
                <div className="d-flex justify-content-between">
                  <div className="text-truncate" style={{ maxWidth: 260 }}>{a.vendor_id}</div>
                  <Badge bg={riskVariant[a.risk_band]}>{a.risk_band} · {Math.round(a.overall_risk * 100)}%</Badge>
                </div>
                {dimensions.map(([key, label]) => (
                  <div key={key} className="mt-2">
                    <div className="d-flex justify-content-between small text-muted"><span>{label}</span><span>{Math.round(a[key] * 100)}%</span></div>
                    <ProgressBar now={a[key] * 100} variant={a[key] > 0.67 ? "danger" : a[key] > 0.34 ? "warning" : "success"} />
                  </div>
                ))}
              </Card.Body>
            </Card>
          ))}
          {assessments.length === 0 && <p className="text-muted">No assessments yet.</p>}
        </Col>
      </Row>
    </div>
  );
}
