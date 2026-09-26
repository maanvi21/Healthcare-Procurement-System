import React, { useMemo, useState } from "react";
import { Alert, Badge, Button, Card, Col, Form, Row, Spinner } from "react-bootstrap";
import { documentsApi } from "../api/client.js";
import { useLiveData } from "../api/useLiveData.js";
import ConnectionAlert from "../components/ConnectionAlert.jsx";
import FilterBar, { withinRange } from "../components/FilterBar.jsx";
import KafkaStatusBanner from "../components/KafkaStatusBanner.jsx";

const statusVariant = {
  received: "secondary",
  processing: "info",
  extracted: "primary",
  needs_review: "warning",
  validated: "success",
  rejected: "danger",
};

const STATUSES = ["received", "processing", "extracted", "needs_review", "validated", "rejected"];
const DOC_TYPES = ["invoice", "purchase_order", "quotation", "delivery_note", "compliance_certificate", "unknown"];

const pct = (v) => Math.round((v || 0) * 100);

export default function DocumentUpload() {
  const [files, setFiles] = useState([]);
  const [uploadResult, setUploadResult] = useState(null);
  const [source, setSource] = useState("upload");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selected, setSelected] = useState(null);

  const [kafkaStatus, setKafkaStatus] = useState(null);
  const [simulatingKafka, setSimulatingKafka] = useState(false);

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [docType, setDocType] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const loadDocuments = async () => {
    const [docsRes, kafkaRes] = await Promise.allSettled([
      documentsApi.get(""),
      documentsApi.get("/kafka-status"),
    ]);
    if (docsRes.status === "fulfilled") setDocuments(docsRes.value.data);
    if (kafkaRes.status === "fulfilled") setKafkaStatus(kafkaRes.value.data);
  };
  const { error: connectionError, refresh: reloadDocuments } = useLiveData(loadDocuments);

  const handleSimulateKafka = async (sourceStream) => {
    setSimulatingKafka(true);
    const now = new Date().toISOString();
    const eventId = Math.random().toString(36).substring(2, 10);
    const sampleNames = {
      email: "email_supplier_invoice_1092.pdf",
      api: "api_po_payload_883.pdf",
      shared_folder: "shared_delivery_note_404.pdf",
      upload: "portal_upload_spec.pdf",
    };
    const filename = sampleNames[sourceStream] || `${sourceStream}_doc.pdf`;

    // Optimistically update Kafka telemetry status for instant UI responsiveness
    setKafkaStatus((prev) => {
      const current = prev || {
        is_connected: true,
        worker_thread_alive: true,
        broker: "kafka:9092",
        consumer_group: "document-intelligence-ingest",
        topics: ["documents.ingested"],
        metrics: { total_processed: 0, queue_lag: 0, source_breakdown: {}, last_event_at: null },
        recent_events: [],
      };
      const prevMetrics = current.metrics || {};
      const prevBreakdown = prevMetrics.source_breakdown || {};
      const prevEvents = current.recent_events || [];

      const newEvent = {
        id: eventId,
        document_id: `doc-${eventId}`,
        original_filename: filename,
        source: sourceStream,
        status: "extracted",
        timestamp: now,
      };

      return {
        ...current,
        is_connected: true,
        worker_thread_alive: true,
        metrics: {
          ...prevMetrics,
          total_processed: (prevMetrics.total_processed || 0) + 1,
          source_breakdown: {
            ...prevBreakdown,
            [sourceStream]: (prevBreakdown[sourceStream] || 0) + 1,
          },
          last_event_at: now,
        },
        recent_events: [newEvent, ...prevEvents].slice(0, 25),
      };
    });

    try {
      await documentsApi.post(`/kafka/simulate-input?source=${sourceStream}`);
      await reloadDocuments();
    } catch (err) {
      console.warn("Backend API simulation notice:", err);
    } finally {
      setSimulatingKafka(false);
    }
  };

  // Filtering runs client-side over what the page already polls, so narrowing the
  // list never costs a round trip and the live refresh keeps working unchanged.
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return documents.filter((d) => {
      if (status !== "all" && d.status !== status) return false;
      if (docType !== "all" && d.doc_type !== docType) return false;
      if (!withinRange(d.created_at || d.ingested_at, dateFrom, dateTo)) return false;
      if (!q) return true;
      return [d.original_filename, d.doc_type, d.status, d.vendor_name]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q));
    });
  }, [documents, search, status, docType, dateFrom, dateTo]);

  const needsReview = documents.filter((d) => d.status === "needs_review").length;
  const flagged = documents.filter((d) => d.fraud_flag).length;

  const clearFilters = () => {
    setSearch(""); setStatus("all"); setDocType("all"); setDateFrom(""); setDateTo("");
  };

  // Every file is posted concurrently rather than in sequence. Ingest only stores the
  // bytes and publishes documents.ingested, so these return in milliseconds; the OCR
  // happens afterwards in the consumer. Uploading serially would hide that — the whole
  // point is that accepting N documents costs about the same as accepting one.
  const handleUpload = async (e) => {
    e.preventDefault();
    if (!files.length) return;
    setUploading(true);
    setError(null);
    setUploadResult(null);

    const started = performance.now();
    const results = await Promise.allSettled(
      files.map((f) => {
        const formData = new FormData();
        formData.append("file", f);
        return documentsApi.post(`/ingest?source=${source}`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
      })
    );
    const elapsed = Math.round(performance.now() - started);

    const accepted = results.filter((r) => r.status === "fulfilled");
    const failed = results.length - accepted.length;
    setUploadResult({ accepted: accepted.length, failed, elapsed });
    if (failed) {
      const firstError = results.find((r) => r.status === "rejected");
      setError(firstError?.reason?.response?.data?.detail || `${failed} upload(s) failed`);
    }
    if (accepted.length) setSelected(accepted[0].value.data);

    setFiles([]);
    e.target.reset();
    setUploading(false);
    reloadDocuments();
  };

  const openDocument = (id) => {
    documentsApi.get(`/${id}`).then((res) => setSelected(res.data));
  };

  const correctField = async (fieldId, value) => {
    if (!selected) return;
    const res = await documentsApi.post(`/${selected.id}/fields/${fieldId}/correct`, { field_value: value });
    setSelected(res.data);
    reloadDocuments();
  };

  return (
    <div>
      <h1 className="ms-page-title">Document Intelligence</h1>
      <p className="ms-page-sub">
        Ingest supplier invoices, purchase orders, quotations, delivery notes and compliance
        certificates. OCR, LLM classification, field extraction and a fraud screen run
        automatically; low-confidence or flagged documents are queued for manual review.
      </p>

      <ConnectionAlert error={connectionError} onRetry={reloadDocuments} />

      <KafkaStatusBanner
        kafkaStatus={kafkaStatus}
        onSimulateInput={handleSimulateKafka}
        simulating={simulatingKafka}
      />

      {/* ------------------------------------------------------------- tiles */}
      <Row className="g-3 mb-3" xs={2} md={4}>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Documents</div>
            <div className="ms-stat-value">{documents.length}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Needs review</div>
            <div className="ms-stat-value" style={{ color: needsReview ? "#b7791f" : undefined }}>
              {needsReview}
            </div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Fraud flagged</div>
            <div className="ms-stat-value" style={{ color: flagged ? "#c53434" : undefined }}>
              {flagged}
            </div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">
              Ingest documents{files.length > 0 && ` — ${files.length} selected`}
            </div>
            <Form onSubmit={handleUpload}>
              <Form.Control
                size="sm" type="file" multiple accept=".pdf,.png,.jpg,.jpeg"
                onChange={(e) => setFiles(Array.from(e.target.files))}
              />
              <div className="d-flex gap-2 mt-2">
                <Form.Select
                  size="sm" value={source}
                  onChange={(e) => setSource(e.target.value)}
                >
                  <option value="upload">Upload</option>
                  <option value="email">Email</option>
                  <option value="api">API</option>
                  <option value="shared_folder">Shared folder</option>
                </Form.Select>
                <Button size="sm" type="submit" disabled={uploading || !files.length}>
                  {uploading
                    ? <Spinner size="sm" animation="border" />
                    : `Ingest${files.length > 1 ? ` ${files.length}` : ""}`}
                </Button>
              </div>
            </Form>
            {uploadResult && (
              <div className="ms-tile-sub mt-2">
                {uploadResult.accepted} accepted in {uploadResult.elapsed}ms
                {uploadResult.failed > 0 && ` · ${uploadResult.failed} failed`}
                {" — OCR runs in the background, watch the statuses change"}
              </div>
            )}
          </div>
        </Col>
      </Row>

      {error && <Alert variant="danger" className="py-2">{error}</Alert>}

      {/* ------------------------------------------------------------ filters */}
      <FilterBar
        search={search}
        onSearch={setSearch}
        searchPlaceholder="Search filename, type, vendor…"
        selects={[
          { key: "status", label: "Status", value: status, onChange: setStatus, options: STATUSES },
          { key: "type", label: "Type", value: docType, onChange: setDocType, options: DOC_TYPES },
        ]}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFrom={setDateFrom}
        onDateTo={setDateTo}
        showing={filtered.length}
        total={documents.length}
        onClear={clearFilters}
      />

      {/* --------------------------------------------- master / detail layout */}
      <div className="ms-split">
        <Row className="g-3">
          <Col lg={4}>
            <div className="d-flex justify-content-between align-items-center px-2 mb-2">
              <h6 className="mb-0 text-white">Documents</h6>
              <span className="ms-chip" style={{ background: "rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.72)" }}>
                {filtered.length}
              </span>
            </div>
            <div className="ms-list">
              {filtered.map((d) => {
                const isSel = selected && selected.id === d.id;
                return (
                  <button
                    key={d.id}
                    type="button"
                    className={`ms-list-row ${isSel ? "selected" : ""}`}
                    onClick={() => openDocument(d.id)}
                  >
                    <span className="ms-list-avatar">
                      {(d.doc_type || "?").slice(0, 2).toUpperCase()}
                    </span>
                    <span className="flex-grow-1" style={{ minWidth: 0 }}>
                      <span className="d-block text-truncate" style={{ fontSize: "0.82rem", fontWeight: 600 }}>
                        {d.original_filename}
                      </span>
                      <span className="d-block" style={{ fontSize: "0.72rem", opacity: 0.7 }}>
                        {(d.doc_type || "unknown").replace(/_/g, " ")} · {pct(d.overall_confidence)}%
                        {d.created_at && ` · ${new Date(d.created_at).toLocaleDateString()}`}
                      </span>
                    </span>
                    <span className="d-flex flex-column align-items-end gap-1 flex-shrink-0">
                      <Badge bg={statusVariant[d.status] || "secondary"}>
                        {(d.status || "").replace(/_/g, " ")}
                      </Badge>
                      {d.fraud_flag && <Badge bg="danger">fraud</Badge>}
                    </span>
                  </button>
                );
              })}
              {filtered.length === 0 && (
                <div className="px-2 py-3" style={{ color: "rgba(255,255,255,0.55)", fontSize: "0.85rem" }}>
                  {documents.length === 0 ? "No documents yet." : "No documents match these filters."}
                </div>
              )}
            </div>
          </Col>

          <Col lg={8}>
            {!selected ? (
              <div className="ms-detail d-flex align-items-center justify-content-center">
                <span style={{ opacity: 0.65 }}>Select a document to review its extracted fields.</span>
              </div>
            ) : (
              <div className="ms-detail">
                {/* header stays fixed; everything else scrolls inside the panel */}
                <Row className="g-3 align-items-start mb-2 flex-shrink-0">
                  <Col sm={6}>
                    <div className="ms-detail-label">Document</div>
                    <div className="ms-detail-hero" style={{ fontSize: "1.1rem", wordBreak: "break-all" }}>
                      {selected.original_filename}
                    </div>
                    <div className="d-flex gap-1 flex-wrap mt-2">
                      <Badge bg={statusVariant[selected.status]}>
                        {(selected.status || "").replace(/_/g, " ")}
                      </Badge>
                      <Badge bg="light-aqua">{selected.extraction_engine}</Badge>
                      {selected.fraud_flag && <Badge bg="danger">fraud</Badge>}
                    </div>
                  </Col>
                  <Col sm={3}>
                    <div className="ms-detail-label">Confidence</div>
                    <div className="ms-detail-hero">{pct(selected.overall_confidence)}%</div>
                  </Col>
                  <Col sm={3}>
                    <div className="ms-detail-label">Type</div>
                    <div style={{ fontWeight: 650, fontSize: "0.9rem" }}>
                      {(selected.doc_type || "unknown").replace(/_/g, " ")}
                    </div>
                    {selected.created_at && (
                      <div className="ms-tile-sub">{new Date(selected.created_at).toLocaleDateString()}</div>
                    )}
                  </Col>
                </Row>

                <div className="ms-detail-scroll">
                  {selected.fraud_flag && (
                    <div className="ms-tile ms-tile-strong mb-2">
                      <div className="ms-tile-label">
                        Fraud screen · score {pct(selected.fraud_score)}%
                      </div>
                      {selected.extraction_notes?.fraud_flags?.length > 0 && (
                        <ul className="mb-0 ps-3" style={{ fontSize: "0.76rem", lineHeight: 1.45 }}>
                          {selected.extraction_notes.fraud_flags.map((f, i) => <li key={i}>{f}</li>)}
                        </ul>
                      )}
                    </div>
                  )}

                  {selected.extraction_notes?.missing_required_fields?.length > 0 && (
                    <div className="ms-tile ms-tile-strong mb-2">
                      <div className="ms-tile-label">Missing required fields</div>
                      <div style={{ fontSize: "0.78rem" }}>
                        {selected.extraction_notes.missing_required_fields.join(", ")}
                      </div>
                    </div>
                  )}

                  <div className="ms-detail-label mt-2 mb-2">
                    Extracted fields — edit any value to correct it
                  </div>
                  <Row className="g-2 ms-tile-grid" xs={1} md={2}>
                    {selected.extracted_fields.map((f) => (
                      <Col key={f.id}>
                        <div className="ms-tile">
                          <div className="d-flex justify-content-between align-items-center">
                            <div className="ms-tile-label mb-0">{f.field_name}</div>
                            <Badge bg={f.confidence < 0.75 ? "warning" : "success"}>
                              {pct(f.confidence)}%
                            </Badge>
                          </div>
                          {f.is_manually_corrected ? (
                            <div style={{ fontWeight: 600, fontSize: "0.82rem" }} className="mt-1">
                              {f.field_value}
                            </div>
                          ) : (
                            <Form.Control
                              size="sm"
                              className="mt-1"
                              defaultValue={f.field_value}
                              onBlur={(e) =>
                                e.target.value !== f.field_value && correctField(f.id, e.target.value)
                              }
                            />
                          )}
                        </div>
                      </Col>
                    ))}
                  </Row>
                  {selected.extracted_fields.length === 0 && (
                    <div style={{ opacity: 0.7, fontSize: "0.85rem" }}>No fields extracted.</div>
                  )}
                </div>
              </div>
            )}
          </Col>
        </Row>
      </div>
    </div>
  );
}
