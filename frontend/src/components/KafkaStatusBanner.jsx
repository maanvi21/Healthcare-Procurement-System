import React from "react";
import { Badge, Button, Col, Dropdown, Row, Spinner } from "react-bootstrap";

const sourceIcons = {
  upload: "📤",
  email: "✉️",
  api: "🌐",
  shared_folder: "📂",
};

const sourceLabels = {
  upload: "Portal Upload",
  email: "Email Stream",
  api: "API Webhook",
  shared_folder: "Shared Folder",
};

export default function KafkaStatusBanner({ kafkaStatus, onSimulateInput, simulating }) {
  const currentStatus = kafkaStatus || {
    is_connected: true,
    worker_thread_alive: true,
    broker: "kafka:9092",
    consumer_group: "document-intelligence-ingest",
    topics: ["documents.ingested"],
    metrics: {
      total_processed: 0,
      queue_lag: 0,
      source_breakdown: { upload: 0, email: 0, api: 0, shared_folder: 0 },
      last_event_at: null,
    },
    recent_events: [],
  };

  const {
    is_connected = true,
    worker_thread_alive = true,
    broker = "kafka:9092",
    consumer_group = "document-intelligence-ingest",
    topics = ["documents.ingested"],
    metrics = {},
    recent_events = [],
  } = currentStatus;

  const totalProcessed = metrics.total_processed || 0;
  const queueLag = metrics.queue_lag || 0;
  const sourceBreakdown = metrics.source_breakdown || {};
  const isHealthy = is_connected || worker_thread_alive;

  return (
    <div className="ms-kafka-panel mb-4">
      <div className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
        <div className="d-flex align-items-center gap-2">
          <span className={`ms-pulse-dot ${isHealthy ? "" : "idle"}`} />
          <h5 className="mb-0 text-white font-weight-bold" style={{ fontSize: "1.1rem" }}>
            Kafka Event Stream & Input Pipeline
          </h5>
          <Badge bg={isHealthy ? "success" : "warning"} className="ms-1">
            {isHealthy ? "STREAM LIVE" : "STANDBY / RECONNECTING"}
          </Badge>
          <span className="text-white-50 ms-2" style={{ fontSize: "0.78rem" }}>
            Broker: <code>{broker}</code> | Topic: <code>{topics.join(", ")}</code>
          </span>
        </div>

        <div className="d-flex align-items-center gap-2">
          <Dropdown>
            <Dropdown.Toggle
              size="sm"
              variant="outline-light"
              style={{ borderRadius: "999px", fontSize: "0.8rem" }}
              disabled={simulating}
            >
              {simulating ? <Spinner size="sm" animation="border" /> : "⚡ Simulate Live Kafka Input"}
            </Dropdown.Toggle>
            <Dropdown.Menu align="end" style={{ background: "#2b2f36", borderColor: "rgba(255,255,255,0.15)" }}>
              <Dropdown.Header className="text-white-50">Choose Input Source Stream</Dropdown.Header>
              <Dropdown.Item
                className="text-white"
                onClick={() => onSimulateInput("email")}
              >
                ✉️ Simulate Incoming Supplier Email
              </Dropdown.Item>
              <Dropdown.Item
                className="text-white"
                onClick={() => onSimulateInput("api")}
              >
                🌐 Simulate ERP API Webhook Ingest
              </Dropdown.Item>
              <Dropdown.Item
                className="text-white"
                onClick={() => onSimulateInput("shared_folder")}
              >
                📂 Simulate Shared Network Folder Drop
              </Dropdown.Item>
              <Dropdown.Item
                className="text-white"
                onClick={() => onSimulateInput("upload")}
              >
                📤 Simulate Portal Upload Event
              </Dropdown.Item>
            </Dropdown.Menu>
          </Dropdown>
        </div>
      </div>

      <Row className="g-3 mb-3">
        <Col xs={6} md={3}>
          <div className="ms-kafka-stat-card">
            <div className="ms-stat-label text-white-50">Stream Ingest Volume</div>
            <div className="d-flex align-items-baseline gap-2">
              <span className="ms-stat-value text-white" style={{ fontSize: "1.5rem" }}>
                {totalProcessed}
              </span>
              <span className="text-white-50" style={{ fontSize: "0.72rem" }}>events</span>
            </div>
            <div className="mt-1" style={{ fontSize: "0.7rem", color: "var(--ms-accent)" }}>
              Group: {consumer_group}
            </div>
          </div>
        </Col>

        <Col xs={6} md={3}>
          <div className="ms-kafka-stat-card">
            <div className="ms-stat-label text-white-50">Consumer Queue / Lag</div>
            <div className="d-flex align-items-baseline gap-2">
              <span
                className="ms-stat-value"
                style={{
                  fontSize: "1.5rem",
                  color: queueLag > 0 ? "#f39c12" : "#2ecc71",
                }}
              >
                {queueLag}
              </span>
              <span className="text-white-50" style={{ fontSize: "0.72rem" }}>pending OCR</span>
            </div>
            <div className="mt-1 text-white-50" style={{ fontSize: "0.7rem" }}>
              Worker thread: {worker_thread_alive ? "Active" : "Ready"}
            </div>
          </div>
        </Col>

        <Col xs={12} md={6}>
          <div className="ms-kafka-stat-card h-100 d-flex flex-column justify-content-between">
            <div className="ms-stat-label text-white-50 mb-1">Input Stream Distribution</div>
            <div className="d-flex align-items-center gap-3 flex-wrap mt-1">
              {Object.entries(sourceLabels).map(([key, label]) => {
                const count = sourceBreakdown[key] || 0;
                return (
                  <div key={key} className="d-flex align-items-center gap-1" style={{ fontSize: "0.78rem" }}>
                    <span>{sourceIcons[key]}</span>
                    <span className="text-white-50">{label}:</span>
                    <strong className="text-white">{count}</strong>
                  </div>
                );
              })}
            </div>
          </div>
        </Col>
      </Row>

      {/* Live Event Stream Ticker */}
      <div className="mt-2">
        <div className="d-flex justify-content-between align-items-center mb-1 px-1">
          <span className="text-white-50 font-weight-bold" style={{ fontSize: "0.74rem", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Live Event Stream Ticker ({recent_events.length} recent events)
          </span>
          {metrics.last_event_at && (
            <span className="text-white-50" style={{ fontSize: "0.7rem" }}>
              Last Event: {new Date(metrics.last_event_at).toLocaleTimeString()}
            </span>
          )}
        </div>

        <div className="ms-kafka-ticker">
          {recent_events.length === 0 ? (
            <div className="text-white-50 py-2 text-center" style={{ fontSize: "0.78rem" }}>
              No Kafka events ingested yet in this session. Click <strong>⚡ Simulate Live Kafka Input</strong> above to push sample events live.
            </div>
          ) : (
            recent_events.map((ev, idx) => (
              <div key={ev.id || idx} className="ms-kafka-event-row">
                <div className="d-flex align-items-center gap-2" style={{ minWidth: 0 }}>
                  <span>{sourceIcons[ev.source] || "📄"}</span>
                  <span className="text-white font-weight-semibold text-truncate" style={{ maxWidth: "220px" }}>
                    {ev.original_filename}
                  </span>
                  <span className="text-white-50" style={{ fontSize: "0.72rem" }}>
                    via {sourceLabels[ev.source] || ev.source}
                  </span>
                </div>
                <div className="d-flex align-items-center gap-2 flex-shrink-0">
                  <Badge bg="dark" style={{ border: "1px solid rgba(255,255,255,0.2)", fontSize: "0.68rem" }}>
                    {ev.status}
                  </Badge>
                  <span className="text-white-50" style={{ fontSize: "0.68rem" }}>
                    {new Date(ev.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
