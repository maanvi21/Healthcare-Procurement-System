import React, { useState } from "react";
import { Alert, Badge, Button, Card, Col, Form, ListGroup, ProgressBar, Row } from "react-bootstrap";
import { riskApi } from "../api/client.js";
import { useLiveData } from "../api/useLiveData.js";
import ConnectionAlert from "../components/ConnectionAlert.jsx";

const riskVariant = { low: "success", medium: "warning", high: "danger" };
const dimensions = [
  ["compliance_risk", "Compliance"], ["fraud_risk", "Fraud"], ["financial_risk", "Financial"],
  ["supplier_risk", "Supplier"], ["spend_risk", "Spend"], ["operational_risk", "Operational"],
];

// Signals the platform cannot observe for itself. Left blank they are omitted from the
// request, and the service uses what it measured — sending a value overrides the
// measurement, so these must not carry defaults.
const overrides = [
  ["cold_chain_violation_count", "Cold-chain violations", "1"],
  ["financial_health_score", "Financial health (0-1, higher=better)", "0.01"],
  ["prior_compliance_flags", "Prior compliance flags", "1"],
  ["years_in_business", "Years in business", "1"],
  ["late_delivery_rate", "Late delivery rate (0-1)", "0.01"],
];

const bar = (v) => (v > 0.67 ? "danger" : v > 0.34 ? "warning" : "success");

export default function RiskDashboard() {
  const [assessments, setAssessments] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [form, setForm] = useState({ vendor_id: "" });
  const [error, setError] = useState(null);

  const load = () =>
    Promise.all([
      riskApi.get("/assessments").then((res) => setAssessments(res.data)),
      riskApi.get("/anomalies").then((res) => setAnomalies(res.data)),
    ]);
  const { error: connectionError, refresh: reloadRisk } = useLiveData(load);

  const assess = async (e) => {
    e.preventDefault();
    setError(null);
    // send only what was actually filled in — everything else stays measured
    const payload = { vendor_id: form.vendor_id };
    for (const [key] of overrides) {
      if (form[key] !== undefined && form[key] !== "") payload[key] = Number(form[key]);
    }
    try {
      await riskApi.post("/assess", payload);
      reloadRisk();
    } catch (err) {
      setError(err.response?.data?.detail || "Assessment failed");
    }
  };

  return (
    <div>
      <h2>Risk Intelligence</h2>
      <ConnectionAlert error={connectionError} onRetry={reloadRisk} />
      <p className="text-muted">
        Six-dimension scikit-learn vendor risk model (compliance, fraud, financial, supplier,
        spend, operational) tracked in MLflow, plus unsupervised anomaly detection. Features are
        measured from platform activity — invoices and their fraud screens, delivery notes against
        purchase orders, procurement spend — so assessments refresh automatically as vendors
        transact. A vendor with too little history is marked <em>cold start</em>.
      </p>

      {anomalies.length > 0 && (
        <Alert variant="danger">
          <strong>{anomalies.length} vendor{anomalies.length > 1 ? "s" : ""} flagged anomalous</strong>
          <ListGroup variant="flush" className="mt-2">
            {anomalies.slice(0, 5).map((a) => (
              <ListGroup.Item key={a.id} className="bg-transparent px-0 py-1 border-0 small">
                <code>{a.vendor_id.slice(0, 8)}</code> — {a.anomaly_reasons.join("; ")}
              </ListGroup.Item>
            ))}
          </ListGroup>
        </Alert>
      )}

      <Row className="g-4">
        <Col md={5}>
          <Card>
            <Card.Body>
              <Card.Title>Run an assessment</Card.Title>
              <p className="small text-muted">
                Leave a field blank to use what the platform measured. Fill one in only to
                override it with data the platform cannot see (e.g. an ERP financial rating).
              </p>
              <Form onSubmit={assess}>
                <Form.Group className="mb-2">
                  <Form.Label>Vendor ID</Form.Label>
                  <Form.Control
                    required value={form.vendor_id}
                    onChange={(e) => setForm({ ...form, vendor_id: e.target.value })}
                    placeholder="uuid from Vendors page"
                  />
                </Form.Group>
                {overrides.map(([key, label, step]) => (
                  <Form.Group className="mb-2" key={key}>
                    <Form.Label className="small">{label}</Form.Label>
                    <Form.Control
                      type="number" step={step} placeholder="measured"
                      value={form[key] ?? ""}
                      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                    />
                  </Form.Group>
                ))}
                <Button type="submit" className="mt-2">Assess vendor</Button>
              </Form>
              {error && <Alert variant="danger" className="mt-3 py-2 small">{error}</Alert>}
            </Card.Body>
          </Card>
        </Col>

        <Col md={7}>
          <h5>Recent assessments</h5>
          {assessments.map((a) => (
            <Card key={a.id} className="mb-3">
              <Card.Body>
                <div className="d-flex justify-content-between align-items-start">
                  <div className="text-truncate" style={{ maxWidth: 240 }}>{a.vendor_id}</div>
                  <div className="text-end">
                    <Badge bg={riskVariant[a.risk_band]}>
                      {a.risk_band} · {Math.round(a.overall_risk * 100)}%
                    </Badge>
                    {a.is_cold_start && (
                      <Badge bg="secondary" className="ms-1" title="Too little history to measure — this is an estimate">
                        cold start
                      </Badge>
                    )}
                    {a.anomaly_flag && <Badge bg="danger" className="ms-1">anomaly</Badge>}
                  </div>
                </div>

                <div className="small text-muted mt-1">
                  {a.observation_count} observation{a.observation_count === 1 ? "" : "s"} · model v{a.model_version}
                </div>

                {a.anomaly_flag && a.anomaly_reasons.length > 0 && (
                  <ul className="small text-danger mt-2 mb-0 ps-3">
                    {a.anomaly_reasons.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                )}

                {dimensions.map(([key, label]) => (
                  <div key={key} className="mt-2">
                    <div className="d-flex justify-content-between small text-muted">
                      <span>{label}</span><span>{Math.round(a[key] * 100)}%</span>
                    </div>
                    <ProgressBar now={a[key] * 100} variant={bar(a[key])} />
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
