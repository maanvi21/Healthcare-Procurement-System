import React, { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, Col, Form, Modal, Row, Spinner } from "react-bootstrap";
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
  ["financial_health_score", "Financial health (0-1)", "0.01"],
  ["prior_compliance_flags", "Prior compliance flags", "1"],
  ["years_in_business", "Years in business", "1"],
  ["late_delivery_rate", "Late delivery rate (0-1)", "0.01"],
];

const tagLabel = (v) => (v > 0.67 ? "High" : v > 0.34 ? "Medium" : "Low");
const meterClass = (v) => (v > 0.67 ? "ms-meter-high" : v > 0.34 ? "ms-meter-med" : "ms-meter-low");
const bar = (v) => (v > 0.67 ? "danger" : v > 0.34 ? "warning" : "success");
const pct = (v) => Math.round(v * 100);

export default function RiskDashboard() {
  const [assessments, setAssessments] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [form, setForm] = useState({ vendor_id: "" });
  const [error, setError] = useState(null);
  const [shap, setShap] = useState({ open: false, loading: false, data: null, error: null });

  const load = () =>
    Promise.all([
      riskApi.get("/assessments").then((res) => setAssessments(res.data)),
      riskApi.get("/anomalies").then((res) => setAnomalies(res.data)),
    ]);
  const { error: connectionError, refresh: reloadRisk } = useLiveData(load);

  // Select the newest assessment once data first lands, so the detail pane is never
  // empty on arrival; leave the user's choice alone on subsequent polls.
  useEffect(() => {
    if (!selectedId && assessments.length) setSelectedId(assessments[0].id);
  }, [assessments, selectedId]);

  const selected = assessments.find((a) => a.id === selectedId) || assessments[0] || null;

  const assess = async (e) => {
    e.preventDefault();
    setError(null);
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

  const openShap = async (vendorId) => {
    setShap({ open: true, loading: true, data: null, error: null });
    try {
      const res = await riskApi.get(`/vendors/${vendorId}/explain?top_n=6`);
      setShap({ open: true, loading: false, data: res.data, error: null });
    } catch (err) {
      setShap({
        open: true, loading: false, data: null,
        error: err.response?.data?.detail || "Could not load SHAP attribution",
      });
    }
  };

  const latestByVendor = Object.values(
    assessments.reduce((acc, a) => {
      if (!acc[a.vendor_id]) acc[a.vendor_id] = a;
      return acc;
    }, {})
  );
  const highCount = latestByVendor.filter((a) => a.risk_band === "high").length;
  const coldStart = latestByVendor.filter((a) => a.is_cold_start).length;

  return (
    <div>
      <h1 className="ms-page-title">Risk Intelligence</h1>
      <p className="ms-page-sub">
        Six model dimensions, supplier evidence, and anomaly signals feed this learning project's
        approval flow. The current baseline uses synthetic training labels, with provenance shown
        alongside each assessment.
      </p>

      {assessments.some((a) => a.model_status !== "validated") && (
        <Alert variant="warning" className="mb-3">
          <strong>Project model provenance:</strong> these scores use synthetic training labels
          derived from documented risk rules. They keep the end-to-end project workflow functional,
          including approval routing, but do not establish real-world predictive accuracy.
        </Alert>
      )}

      <ConnectionAlert error={connectionError} onRetry={reloadRisk} />
      {error && <Alert variant="danger" dismissible onClose={() => setError(null)}>{error}</Alert>}

      {/* ---------------------------------------------------- headline tiles */}
      <Row className="g-3 mb-4" xs={2} md={4}>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Vendors assessed</div>
            <div className="ms-stat-value">{latestByVendor.length}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">High risk</div>
            <div className="ms-stat-value" style={{ color: highCount ? "#c53434" : undefined }}>
              {highCount}
            </div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Anomalous</div>
            <div className="ms-stat-value">{anomalies.length}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Cold start</div>
            <div className="ms-stat-value">
              {coldStart}<span className="ms-stat-unit">of {latestByVendor.length || 0}</span>
            </div>
          </div>
        </Col>
      </Row>

      {/* ------------------------------------------- master / detail assessment */}
      <div className="ms-split mb-4">
        <Row className="g-3">
          {/* ------- list ------- */}
          <Col xl={4}>
            <div className="d-flex justify-content-between align-items-center px-2 mb-2">
              <h6 className="mb-0 text-white">Assessments</h6>
              <span className="ms-chip" style={{ background: "rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.72)" }}>
                {assessments.length}
              </span>
            </div>
            <div className="ms-list">
              {assessments.map((a) => {
                const isSel = selected && a.id === selected.id;
                return (
                  <button
                    key={a.id}
                    type="button"
                    className={`ms-list-row ${isSel ? "selected" : ""}`}
                    onClick={() => setSelectedId(a.id)}
                  >
                    <span className="ms-list-avatar">{a.vendor_id.slice(0, 2).toUpperCase()}</span>
                    <span className="flex-grow-1" style={{ minWidth: 0 }}>
                      <span className="d-block text-truncate" style={{ fontSize: "0.82rem", fontWeight: 600 }}>
                        {a.vendor_id.slice(0, 8)}
                      </span>
                      <span
                        className="d-block"
                        style={{ fontSize: "0.72rem", opacity: 0.7 }}
                      >
                        {a.observation_count} obs{a.anomaly_flag ? " · anomaly" : ""}
                      </span>
                    </span>
                    <Badge bg={riskVariant[a.risk_band]} className="flex-shrink-0">
                      {pct(a.overall_risk)}%
                    </Badge>
                  </button>
                );
              })}
              {assessments.length === 0 && (
                <div className="px-2 py-3" style={{ color: "rgba(255,255,255,0.84)", fontSize: "0.85rem" }}>
                  No assessments yet.
                </div>
              )}
            </div>
          </Col>

          {/* ------- detail ------- */}
          <Col xl={8}>
            {selected ? (
              <div className="ms-detail">
                <Row className="g-3 align-items-start mb-2 flex-shrink-0">
                  <Col sm={5}>
                    <div className="ms-detail-label">Vendor assessment</div>
                    <div className="ms-detail-hero">{selected.vendor_id.slice(0, 8)}</div>
                    <div className="d-flex gap-1 flex-wrap mt-2">
                      <Badge bg={riskVariant[selected.risk_band]}>{selected.risk_band}</Badge>
                      {selected.is_cold_start && <Badge bg="light-aqua">cold start</Badge>}
                      {selected.anomaly_flag && <Badge bg="danger">anomaly</Badge>}
                    </div>
                  </Col>
                  <Col sm={3}>
                    <div className="ms-detail-label">Overall risk</div>
                    <div className="ms-detail-hero">{pct(selected.overall_risk)}%</div>
                  </Col>
                  <Col sm={4}>
                    <div className="ms-detail-label">Model</div>
                    <div style={{ fontWeight: 650 }}>
                      {selected.model_status === "validated"
                        ? `Observed-outcome model v${selected.model_version.replace("observed:", "")}`
                        : `Synthetic project model · ${selected.model_version.replace("synthetic:", "")}`}
                    </div>
                    <div className="ms-tile-sub">
                      {selected.model_status === "validated" ? "Validated on observed outcomes" : "Project baseline · synthetic training labels"}
                    </div>
                    <div className="ms-tile-sub">
                      {new Date(selected.assessed_at).toLocaleString()}
                    </div>
                  </Col>
                </Row>

                <div className="ms-detail-scroll">
                {/* six dimensions as nested tiles */}
                <Row className="g-2 mb-3 ms-tile-grid" xs={1} sm={2} lg={3}>
                  {dimensions.map(([key, label]) => (
                    <Col key={key}>
                      <div className="ms-tile">
                        <div className="ms-tile-label">{label}</div>
                        <div className="ms-tile-value">
                          {pct(selected[key])}%
                          <span
                            className="ms-tile-sub ms-1"
                            style={{ fontWeight: 600 }}
                          >
                            {tagLabel(selected[key])}
                          </span>
                        </div>
                        <div className={`ms-meter ${meterClass(selected[key])}`}>
                          <span style={{ width: `${Math.max(2, pct(selected[key]))}%` }} />
                        </div>
                        {selected.explanations?.[key]?.length > 0 && (
                          <div className="ms-tile-sub">{selected.explanations[key][0]}</div>
                        )}
                      </div>
                    </Col>
                  ))}
                </Row>

                {/* summary strip + primary action */}
                <Row className="g-2 align-items-stretch">
                  <Col sm={3}>
                    <div className="ms-tile ms-tile-strong">
                      <div className="ms-tile-label">Observations</div>
                      <div className="ms-tile-value">{selected.observation_count}</div>
                    </div>
                  </Col>
                  <Col sm={3}>
                    <div className="ms-tile ms-tile-strong">
                      <div className="ms-tile-label">Anomaly score</div>
                      <div className="ms-tile-value">{pct(selected.anomaly_score)}%</div>
                    </div>
                  </Col>
                  <Col sm={3}>
                    <div className="ms-tile ms-tile-strong">
                      <div className="ms-tile-label">Worst dimension</div>
                      <div className="ms-tile-value" style={{ fontSize: "0.95rem" }}>
                        {dimensions.reduce((w, [k, l]) => (selected[k] > selected[w[0]] ? [k, l] : w), dimensions[0])[1]}
                      </div>
                    </div>
                  </Col>
                  <Col sm={3} className="d-flex align-items-center">
                    <Button
                      variant="success"
                      className="w-100"
                      onClick={() => openShap(selected.vendor_id)}
                    >
                      Why? SHAP
                    </Button>
                  </Col>
                </Row>

                {selected.anomaly_flag && selected.anomaly_reasons.length > 0 && (
                  <div className="ms-tile ms-tile-strong mt-2">
                    <div className="ms-tile-label">Anomaly reasons</div>
                    <ul className="mb-0 ps-3" style={{ fontSize: "0.78rem" }}>
                      {selected.anomaly_reasons.map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                  </div>
                )}
                </div>
              </div>
            ) : (
              <div className="ms-detail d-flex align-items-center justify-content-center">
                <span>Select an assessment to see its breakdown.</span>
              </div>
            )}
          </Col>
        </Row>
      </div>

      {/* ------------------------------------------- anomalies + assess form */}
      <Row className="g-4">
        <Col lg={7}>
          <div className="ms-panel h-100 p-4">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <h5 className="mb-0">Anomaly review queue</h5>
              <span className="ms-chip" style={{ background: "rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.75)" }}>
                {anomalies.length} flagged
              </span>
            </div>
            {anomalies.length === 0 && (
              <div style={{ color: "rgba(255,255,255,0.84)", fontSize: "0.875rem" }}>
                No vendors currently flagged. Each vendor appears once, based on their latest assessment.
              </div>
            )}
            {anomalies.map((a) => (
              <div
                key={a.id}
                className="d-flex justify-content-between align-items-start py-2"
                style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
              >
                <div className="pe-3">
                  <code style={{ background: "rgba(255,255,255,0.1)", color: "#fff" }}>
                    {a.vendor_id.slice(0, 8)}
                  </code>
                  <div style={{ color: "rgba(255,255,255,0.84)", fontSize: "0.8rem" }} className="mt-1">
                    {a.anomaly_reasons.join(" · ")}
                  </div>
                </div>
                <Badge bg="danger" className="flex-shrink-0">{pct(a.anomaly_score)}%</Badge>
              </div>
            ))}
          </div>
        </Col>

        <Col lg={5}>
          <Card className="h-100">
            <Card.Body>
              <Card.Title style={{ fontSize: "1rem" }}>Run an assessment</Card.Title>
              <p className="small text-muted">
                Leave a field blank to use what the platform measured. Fill one in only to
                override it with data the platform cannot see.
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
                <Row xs={1} sm={2} className="g-2">
                  {overrides.map(([key, label, step]) => (
                    <Col key={key}>
                      <Form.Group>
                        <Form.Label className="small">{label}</Form.Label>
                        <Form.Control
                          type="number" step={step} placeholder="measured"
                          value={form[key] ?? ""}
                          onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                        />
                      </Form.Group>
                    </Col>
                  ))}
                </Row>
                <Button type="submit" className="mt-3">Assess vendor</Button>
              </Form>
              {error && <Alert variant="danger" className="mt-3 py-2 small">{error}</Alert>}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <ShapModal shap={shap} onClose={() => setShap((s) => ({ ...s, open: false }))} />
    </div>
  );
}

/* ---------------------------------------------------------------- SHAP modal */
/* Renders the model's own attribution: each feature's signed contribution, which
   sum with the base value to exactly the served prediction. Distinct from the
   rule-based sentences on the tiles — those describe what should matter, this
   shows what the trained trees actually used. */
export function ShapModal({ shap, onClose }) {
  const dims = shap.data?.dimensions || {};
  const maxAbs = Math.max(
    0.01,
    ...Object.values(dims).flatMap((d) => d.top_contributions.map((c) => Math.abs(c.contribution)))
  );

  return (
    <Modal show={shap.open} onHide={onClose} size="lg" scrollable>
      <Modal.Header closeButton>
        <Modal.Title style={{ fontSize: "1.1rem" }}>
          SHAP attribution
          {shap.data && (
            <div className="text-muted" style={{ fontSize: "0.8rem", fontWeight: 400 }}>
              {shap.data.method}
            </div>
          )}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {shap.loading && (
          <div className="text-center py-4">
            <Spinner animation="border" size="sm" /> <span className="ms-2 small">Computing Shapley values…</span>
          </div>
        )}
        {shap.error && <Alert variant="warning" className="py-2 small mb-0">{shap.error}</Alert>}

        {shap.data && (
          <>
            <div className="d-flex gap-2 flex-wrap mb-3">
              <span className="ms-chip">vendor {shap.data.vendor_id.slice(0, 8)}</span>
              <span className="ms-chip">band {shap.data.risk_band}</span>
              <span className="ms-chip">overall {pct(shap.data.overall_risk)}%</span>
              <span className="ms-chip">
                model {shap.data.model_version.startsWith("synthetic:")
                  ? `project baseline ${shap.data.model_version.replace("synthetic:", "")}`
                  : `v${shap.data.model_version.replace("observed:", "")}`}
              </span>
              {shap.data.is_cold_start && <span className="ms-chip">cold start</span>}
            </div>

            <p className="small text-muted">
              Each bar is how much that feature moved the model prediction away from its baseline —
              right/red pushes risk up, left/green pulls it down. The model contribution totals are
              shown before any policy adjustments listed below.
            </p>
            {shap.data.policy_adjustments?.length > 0 && (
              <Alert variant="warning" className="small py-2">
                <strong>Compliance policy adjustment:</strong> {shap.data.policy_adjustments.join(" ")}
              </Alert>
            )}

            {Object.entries(dims).map(([dim, d]) => (
              <Card key={dim} className="mb-3">
                <Card.Body className="py-3">
                  <div className="d-flex justify-content-between align-items-center mb-2">
                    <strong style={{ fontSize: "0.9rem" }}>
                      {dim.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    </strong>
                    <span className="small text-muted">
                      base {d.base_value.toFixed(3)} → <strong>{d.predicted.toFixed(3)}</strong>
                    </span>
                  </div>
                  {d.top_contributions.length === 0 && (
                    <div className="small text-muted">No feature moved this dimension measurably.</div>
                  )}
                  {d.top_contributions.map((c) => {
                    const width = (Math.abs(c.contribution) / maxAbs) * 50;
                    return (
                      <div className="ms-shap-row" key={c.feature}>
                        <div className="ms-shap-label">
                          {c.label}
                          <span className="text-muted"> · {c.value}</span>
                        </div>
                        <div className="ms-shap-track">
                          <div className="ms-shap-mid" />
                          <div
                            className={`ms-shap-fill ${c.contribution > 0 ? "up" : "down"}`}
                            style={{ width: `${width}%` }}
                          />
                        </div>
                        <div
                          className="ms-shap-value"
                          style={{ color: c.contribution > 0 ? "#c53434" : "#2f9e5f" }}
                        >
                          {c.contribution > 0 ? "+" : ""}{c.contribution.toFixed(3)}
                        </div>
                      </div>
                    );
                  })}
                </Card.Body>
              </Card>
            ))}
          </>
        )}
      </Modal.Body>
    </Modal>
  );
}
