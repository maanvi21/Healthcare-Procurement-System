import React, { useMemo, useState } from "react";
import { Badge, Button, Col, Row, Spinner } from "react-bootstrap";
import { documentsApi } from "../api/client.js";
import { useLiveData } from "../api/useLiveData.js";
import ConnectionAlert from "../components/ConnectionAlert.jsx";

const topicMarks = {
  "documents.ingested": "DOC",
  "documents.processed": "OCR",
  "documents.reviewed": "REV",
  "vendor.onboarded": "VEN",
  "vendor.updated": "VEN",
  "procurement.request.created": "REQ",
  "approval.requested": "APR",
  "approval.approved": "APR",
  "approval.rejected": "APR",
  "approval.escalated": "APR",
  "inventory.reserved": "INV",
  "inventory.backorder": "INV",
  "contract.generated": "CTR",
  "contract.signed": "SIG",
  "contract.sent_for_signature": "SIG",
  "risk.assessed": "RSK",
  "notification.sent": "MSG",
  "storage.saved": "STO",
  "contract.signature_pending": "SIG",
};

const topicColors = {
  "documents.ingested": "#3498db",
  "documents.processed": "#2ecc71",
  "documents.reviewed": "#9b59b6",
  "approval.requested": "#f39c12",
  "approval.approved": "#27ae60",
  "approval.rejected": "#e74c3c",
  "approval.escalated": "#e67e22",
  "contract.generated": "#1abc9c",
  "contract.signed": "#16a085",
  "contract.sent_for_signature": "#2980b9",
  "notification.sent": "#8e44ad",
  "storage.saved": "#34495e",
};

export default function KafkaLogs() {
  const [kafkaStatus, setKafkaStatus] = useState(null);
  const [watcherStatus, setWatcherStatus] = useState(null);
  const [demoTimeline, setDemoTimeline] = useState([]);
  const [runningDemo, setRunningDemo] = useState(false);
  const [topicFilter, setTopicFilter] = useState("all");
  const [simulatingKafka, setSimulatingKafka] = useState(false);

  const loadData = async () => {
    const [kafkaRes, watcherRes] = await Promise.allSettled([
      documentsApi.get("/kafka-status"),
      documentsApi.get("/watcher/status"),
    ]);
    if (kafkaRes.status === "fulfilled") setKafkaStatus(kafkaRes.value.data);
    if (watcherRes.status === "fulfilled") setWatcherStatus(watcherRes.value.data);
  };
  const { error: connectionError, refresh: reload } = useLiveData(loadData, { intervalMs: 2000 });

  const handleSimulateKafka = async (source) => {
    setSimulatingKafka(true);
    try {
      await documentsApi.post(`/kafka/simulate-input?source=${source}`);
      await reload();
    } catch (err) {
      console.warn("Simulate notice:", err);
    } finally {
      setSimulatingKafka(false);
    }
  };

  const handleRunDemo = async () => {
    setRunningDemo(true);
    setDemoTimeline([]);
    try {
      const res = await documentsApi.post("/demo/end-to-end");
      setDemoTimeline(res.data.timeline || []);
      await reload();
    } catch (err) {
      console.warn("Demo error:", err);
    } finally {
      setRunningDemo(false);
    }
  };

  const recentEvents = kafkaStatus?.recent_events || [];
  const allEvents = useMemo(() => {
    const combined = [
      ...demoTimeline.map((e) => ({
        id: `demo-${e.timestamp}-${e.topic}`,
        topic: e.topic,
        message: e.message,
        timestamp: e.timestamp,
        data: e.data,
        source: "demo",
      })),
      ...recentEvents.map((e) => ({
        id: e.id || `kafka-${e.timestamp}`,
        topic: "documents.processed",
        message: `${e.original_filename} — ${e.status}`,
        timestamp: e.timestamp,
        data: e,
        source: e.source || "kafka",
      })),
    ].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    return combined;
  }, [demoTimeline, recentEvents]);

  const filteredEvents = useMemo(() => {
    if (topicFilter === "all") return allEvents;
    return allEvents.filter((e) => e.topic === topicFilter);
  }, [allEvents, topicFilter]);

  const uniqueTopics = [...new Set(allEvents.map((e) => e.topic))];

  const metrics = kafkaStatus?.metrics || {};
  const watcherData = watcherStatus || {};

  return (
    <div>
      <h1 className="ms-page-title">Kafka Event Logs</h1>
      <p className="ms-page-sub">
        Live cross-service event stream showing every Kafka message flowing through the
        MediSource AI platform — from document ingestion through approval, contract generation,
        and e-signature.
      </p>

      <ConnectionAlert error={connectionError} onRetry={reload} />

      {/* ── Status Bar ─────────────────────────────────────────────── */}
      <Row className="g-3 mb-4" xs={2} md={5}>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Kafka Broker</div>
            <div className="d-flex align-items-center gap-2">
              <span className={`ms-pulse-dot ${kafkaStatus?.is_connected ? "" : "idle"}`} />
              <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>
                {kafkaStatus?.is_connected ? "Connected" : "Standby"}
              </span>
            </div>
            <div className="ms-tile-sub">{kafkaStatus?.broker || "kafka:9092"}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Events Processed</div>
            <div className="ms-stat-value">{metrics.total_processed || 0}</div>
            <div className="ms-tile-sub">
              Failed: {metrics.total_failed || 0}
            </div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Queue Lag</div>
            <div className="ms-stat-value" style={{ color: (metrics.queue_lag || 0) > 0 ? "#f39c12" : "#2ecc71" }}>
              {metrics.queue_lag || 0}
            </div>
            <div className="ms-tile-sub">pending OCR</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">File Watcher</div>
            <div className="d-flex align-items-center gap-2">
              <span className={`ms-pulse-dot ${watcherData.is_running ? "" : "idle"}`} />
              <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>
                {watcherData.is_running ? "Watching" : "Idle"}
              </span>
            </div>
            <div className="ms-tile-sub">
              {watcherData.total_ingested || 0} files ingested
            </div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Demo Events</div>
            <div className="ms-stat-value">{demoTimeline.length}</div>
            <div className="ms-tile-sub">timeline steps</div>
          </div>
        </Col>
      </Row>

      {/* ── Action Buttons ───────────────────────────────────────── */}
      <div className="d-flex gap-2 mb-4 flex-wrap">
        <Button
          variant="primary"
          onClick={handleRunDemo}
          disabled={runningDemo}
          className="d-flex align-items-center gap-2"
          style={{ borderRadius: 999, fontWeight: 600, fontSize: "0.85rem", padding: "0.5rem 1.25rem" }}
        >
          {runningDemo ? (
            <><Spinner size="sm" animation="border" /> Building example timeline…</>
          ) : (
            <>▶ Preview workflow (simulation)</>
          )}
        </Button>

        {["shared_folder", "email", "api", "upload"].map((src) => (
          <Button
            key={src}
            size="sm"
            variant="outline-light"
            disabled={simulatingKafka}
            onClick={() => handleSimulateKafka(src)}
            style={{ borderRadius: 999, fontSize: "0.78rem" }}
          >
            Simulate {src.replace(/_/g, " ")}
          </Button>
        ))}
      </div>

      {/* ── File Watcher Panel ──────────────────────────────────── */}
      {watcherData.is_running && (
        <div className="ms-kafka-panel mb-4" style={{ padding: "1rem 1.25rem" }}>
          <div className="d-flex align-items-center gap-2 mb-2">
            <span className="ms-pulse-dot" />
            <h6 className="mb-0 text-white" style={{ fontSize: "0.95rem" }}>
              Document Watcher — <code style={{ fontSize: "0.8rem" }}>{watcherData.watch_dir}</code>
            </h6>
            <Badge bg="success" className="ms-2">ACTIVE</Badge>
            <span className="text-white-50 ms-auto" style={{ fontSize: "0.72rem" }}>
              Polling every {watcherData.poll_interval_seconds}s
              {watcherData.last_scan_at && ` · Last scan: ${new Date(watcherData.last_scan_at).toLocaleTimeString()}`}
            </span>
          </div>
          <div className="d-flex gap-4" style={{ fontSize: "0.78rem", color: "rgba(255,255,255,0.7)" }}>
            <span>Detected: <strong className="text-white">{watcherData.total_detected || 0}</strong></span>
            <span>Ingested: <strong className="text-white">{watcherData.total_ingested || 0}</strong></span>
            <span>Failed: <strong style={{ color: "#e74c3c" }}>{watcherData.total_failed || 0}</strong></span>
          </div>
          {(watcherData.recent_files || []).length > 0 && (
            <div className="mt-2">
              {watcherData.recent_files.slice(0, 5).map((f, i) => (
                <div key={i} className="d-flex align-items-center gap-2 py-1"
                  style={{ fontSize: "0.76rem", borderTop: i > 0 ? "1px solid rgba(255,255,255,0.08)" : "none" }}>
                  <span className="text-white fw-semibold">{f.filename}</span>
                  <Badge bg={f.status === "ingested" ? "success" : f.status === "failed" ? "danger" : "secondary"}
                    style={{ fontSize: "0.65rem" }}>{f.status}</Badge>
                  <span className="text-white-50 ms-auto">{new Date(f.detected_at).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Topic Filter ──────────────────────────────────────── */}
      <div className="d-flex align-items-center gap-2 mb-3 flex-wrap">
        <span className="text-white-50" style={{ fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 700 }}>
          Filter by topic:
        </span>
        <Badge
          bg={topicFilter === "all" ? "primary" : "dark"}
          role="button"
          onClick={() => setTopicFilter("all")}
          style={{ cursor: "pointer", fontSize: "0.72rem", border: "1px solid rgba(255,255,255,0.2)" }}
        >
          All ({allEvents.length})
        </Badge>
        {uniqueTopics.map((topic) => (
          <Badge
            key={topic}
            bg={topicFilter === topic ? "primary" : "dark"}
            role="button"
            onClick={() => setTopicFilter(topic)}
            style={{ cursor: "pointer", fontSize: "0.72rem", border: "1px solid rgba(255,255,255,0.15)" }}
          >
            {topic} ({allEvents.filter((e) => e.topic === topic).length})
          </Badge>
        ))}
      </div>

      {/* ── Event Stream ──────────────────────────────────────── */}
      <div className="ms-kafka-panel" style={{ maxHeight: 600, overflowY: "auto" }}>
        <div className="d-flex justify-content-between align-items-center mb-2 px-1">
          <span className="text-white-50" style={{ fontSize: "0.74rem", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 700 }}>
            Live Event Stream ({filteredEvents.length} events)
          </span>
          {metrics.last_event_at && (
            <span className="text-white-50" style={{ fontSize: "0.7rem" }}>
              Last: {new Date(metrics.last_event_at).toLocaleTimeString()}
            </span>
          )}
        </div>

        {filteredEvents.length === 0 ? (
          <div className="text-white-50 py-4 text-center" style={{ fontSize: "0.85rem" }}>
            No events yet. Click <strong>Preview workflow (simulation)</strong> to see an illustrative timeline,
            or <strong>Simulate</strong> individual events.
          </div>
        ) : (
          filteredEvents.map((ev, idx) => {
            const mark = topicMarks[ev.topic] || "EVT";
            const color = topicColors[ev.topic] || "#95a5a6";
            return (
              <div key={ev.id || idx} className="ms-kafka-event-row" style={{ borderLeft: `3px solid ${color}` }}>
                <div className="d-flex align-items-start gap-2 flex-grow-1" style={{ minWidth: 0 }}>
                  <span className="ms-event-mark" style={{ borderColor: color }}>{mark}</span>
                  <div style={{ minWidth: 0 }}>
                    <div className="d-flex align-items-center gap-2 flex-wrap">
                      <Badge bg="dark" style={{ border: `1px solid ${color}40`, fontSize: "0.68rem", color }}>
                        {ev.topic}
                      </Badge>
                      {ev.source === "demo" && (
                        <Badge bg="info" style={{ fontSize: "0.62rem" }}>SIMULATED · no records or signatures created</Badge>
                      )}
                    </div>
                    <div className="text-white mt-1" style={{ fontSize: "0.82rem", fontWeight: 500 }}>
                      {ev.message}
                    </div>
                    {ev.data && Object.keys(ev.data).length > 0 && (
                      <div className="mt-1 d-flex flex-wrap gap-1">
                        {Object.entries(ev.data).slice(0, 4).map(([k, v]) => (
                          <span key={k} className="text-white-50" style={{ fontSize: "0.68rem" }}>
                            {k}=<code>{String(v).slice(0, 30)}</code>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex-shrink-0 text-end">
                  <span className="text-white-50" style={{ fontSize: "0.68rem" }}>
                    {new Date(ev.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
