import React, { useMemo, useState } from "react";
import { Alert, Badge, Button, Card, Col, Form, Row, Table } from "react-bootstrap";
import { notificationsApi } from "../api/client.js";
import { useLiveData } from "../api/useLiveData.js";
import ConnectionAlert from "../components/ConnectionAlert.jsx";
import FilterBar, { withinRange } from "../components/FilterBar.jsx";

const statusBadge = { queued: "secondary", sent: "success", failed: "danger" };
const CHANNELS = ["email", "sms", "teams", "slack"];
const STATUSES = ["queued", "sent", "failed"];

export default function NotificationsDashboard() {
  const [notifications, setNotifications] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [sendForm, setSendForm] = useState({ channel: "email", recipient: "", subject: "", body: "" });
  const [sendResult, setSendResult] = useState(null);
  const [digest, setDigest] = useState(null);
  const [digestRecipient, setDigestRecipient] = useState("");

  const [search, setSearch] = useState("");
  const [channel, setChannel] = useState("all");
  const [status, setStatus] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // Pull a generous page once and filter locally — the previous version refetched on
  // every keystroke of the recipient filter, which made typing feel laggy.
  const loadNotifications = () =>
    notificationsApi.get("", { params: { limit: 200 } }).then((res) => setNotifications(res.data));
  const loadTemplates = () => notificationsApi.get("/templates").then((res) => setTemplates(res.data));

  const { error: connectionError, refresh: reloadAll } = useLiveData(() =>
    Promise.all([loadNotifications(), loadTemplates()])
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return notifications.filter((n) => {
      if (channel !== "all" && n.channel !== channel) return false;
      if (status !== "all" && n.status !== status) return false;
      if (!withinRange(n.created_at, dateFrom, dateTo)) return false;
      if (!q) return true;
      return [n.recipient, n.subject, n.body, n.event_type]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q));
    });
  }, [notifications, search, channel, status, dateFrom, dateTo]);

  const selected = filtered.find((n) => n.id === selectedId) || filtered[0] || null;
  const failedCount = notifications.filter((n) => n.status === "failed").length;

  const clearFilters = () => {
    setSearch(""); setChannel("all"); setStatus("all"); setDateFrom(""); setDateTo("");
  };

  // The API answers 200 with status="failed" when a channel is configured but delivery
  // fails (e.g. SendGrid rejects the key) — the service records the failure rather than
  // raising, so an unchecked `await` here would clear the form and look like success.
  const sendNotification = async (e) => {
    e.preventDefault();
    setSendResult(null);
    try {
      const res = await notificationsApi.post("/send", sendForm);
      if (res.data?.status === "failed") {
        setSendResult({
          variant: "danger",
          text: `Delivery failed on the ${res.data.channel} channel — recorded as failed. Check the service logs and channel credentials.`,
        });
      } else {
        setSendResult({ variant: "success", text: `Sent on ${res.data.channel}.` });
        setSendForm({ channel: sendForm.channel, recipient: "", subject: "", body: "" });
      }
    } catch (err) {
      setSendResult({
        variant: "danger",
        text: err.response?.data?.detail || "Request failed before the notification could be queued.",
      });
    }
    reloadAll();
  };

  const lookupDigest = async (e) => {
    e.preventDefault();
    if (!digestRecipient) return;
    const res = await notificationsApi.get("/digest", { params: { recipient: digestRecipient, hours: 24 } });
    setDigest(res.data);
  };

  return (
    <div>
      <h1 className="ms-page-title">Notification Agent</h1>
      <p className="ms-page-sub">
        Multi-channel notifications rendered from platform events — vendor onboarding, document
        processing, approval decisions, risk assessments, backorders and signed contracts.
      </p>

      <ConnectionAlert error={connectionError} onRetry={reloadAll} />

      <Row className="g-3 mb-3" xs={2} md={4}>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Notifications</div>
            <div className="ms-stat-value">{notifications.length}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Failed</div>
            <div className="ms-stat-value" style={{ color: failedCount ? "#c53434" : undefined }}>
              {failedCount}
            </div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Templates</div>
            <div className="ms-stat-value">{templates.length}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Channels</div>
            <div className="ms-stat-value">{new Set(notifications.map((n) => n.channel)).size}</div>
          </div>
        </Col>
      </Row>

      <FilterBar
        search={search}
        onSearch={setSearch}
        searchPlaceholder="Search recipient, subject, body, event…"
        selects={[
          { key: "channel", label: "Channel", value: channel, onChange: setChannel, options: CHANNELS },
          { key: "status", label: "Status", value: status, onChange: setStatus, options: STATUSES },
        ]}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFrom={setDateFrom}
        onDateTo={setDateTo}
        showing={filtered.length}
        total={notifications.length}
        onClear={clearFilters}
      />

      {/* --------------------------------------------- master / detail layout */}
      <div className="ms-split mb-4">
        <Row className="g-3">
          <Col lg={4}>
            <div className="d-flex justify-content-between align-items-center px-2 mb-2">
              <h6 className="mb-0 text-white">Sent notifications</h6>
              <span className="ms-chip" style={{ background: "rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.72)" }}>
                {filtered.length}
              </span>
            </div>
            <div className="ms-list">
              {filtered.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  className={`ms-list-row ${selected && selected.id === n.id ? "selected" : ""}`}
                  onClick={() => setSelectedId(n.id)}
                >
                  <span className="ms-list-avatar">{n.channel.slice(0, 2).toUpperCase()}</span>
                  <span className="flex-grow-1" style={{ minWidth: 0 }}>
                    <span className="d-block text-truncate" style={{ fontSize: "0.82rem", fontWeight: 600 }}>
                      {n.subject || n.event_type || n.channel}
                    </span>
                    <span className="d-block text-truncate" style={{ fontSize: "0.72rem", opacity: 0.7 }}>
                      {n.recipient} · {new Date(n.created_at).toLocaleDateString()}
                    </span>
                  </span>
                  <Badge bg={statusBadge[n.status] || "secondary"} className="flex-shrink-0">
                    {n.status}
                  </Badge>
                </button>
              ))}
              {filtered.length === 0 && (
                <div className="px-2 py-3" style={{ color: "rgba(255,255,255,0.55)", fontSize: "0.85rem" }}>
                  {notifications.length === 0 ? "No notifications yet." : "None match these filters."}
                </div>
              )}
            </div>
          </Col>

          <Col lg={8}>
            {!selected ? (
              <div className="ms-detail d-flex align-items-center justify-content-center">
                <span style={{ opacity: 0.65 }}>Select a notification to see its full content.</span>
              </div>
            ) : (
              <div className="ms-detail">
                <Row className="g-3 align-items-start mb-2 flex-shrink-0">
                  <Col sm={6}>
                    <div className="ms-detail-label">Notification</div>
                    <div className="ms-detail-hero" style={{ fontSize: "1.2rem" }}>
                      {selected.subject || selected.event_type || "(no subject)"}
                    </div>
                    <div className="d-flex gap-1 flex-wrap mt-2">
                      <Badge bg={statusBadge[selected.status]}>{selected.status}</Badge>
                      <Badge bg="light-aqua">{selected.channel}</Badge>
                    </div>
                  </Col>
                  <Col sm={6}>
                    <div className="ms-tile">
                      <div className="ms-tile-label">Recipient</div>
                      <div style={{ fontWeight: 650, fontSize: "0.9rem", wordBreak: "break-all" }}>
                        {selected.recipient}
                      </div>
                      <div className="ms-tile-sub">
                        {new Date(selected.created_at).toLocaleString()}
                      </div>
                    </div>
                  </Col>
                </Row>

                <div className="ms-detail-scroll">
                <Row className="g-2 mb-3 ms-tile-grid" xs={1} sm={3}>
                  <Col>
                    <div className="ms-tile">
                      <div className="ms-tile-label">Event type</div>
                      <div className="ms-tile-value" style={{ fontSize: "0.9rem" }}>
                        {selected.event_type || "—"}
                      </div>
                    </div>
                  </Col>
                  <Col>
                    <div className="ms-tile">
                      <div className="ms-tile-label">Event key</div>
                      <div className="ms-tile-value" style={{ fontSize: "0.9rem", wordBreak: "break-all" }}>
                        {selected.event_key ? String(selected.event_key).slice(0, 12) : "—"}
                      </div>
                    </div>
                  </Col>
                  <Col>
                    <div className="ms-tile">
                      <div className="ms-tile-label">Template</div>
                      <div className="ms-tile-value" style={{ fontSize: "0.9rem" }}>
                        {selected.template_id ? "from template" : "direct send"}
                      </div>
                    </div>
                  </Col>
                </Row>

                <div className="ms-tile ms-tile-strong">
                  <div className="ms-tile-label">Message body</div>
                  <pre
                    className="mb-0"
                    style={{
                      whiteSpace: "pre-wrap", wordBreak: "break-word",
                      fontSize: "0.82rem", fontFamily: "inherit", maxHeight: 220, overflowY: "auto",
                    }}
                  >
                    {selected.body}
                  </pre>
                </div>
                </div>
              </div>
            )}
          </Col>
        </Row>
      </div>

      {/* ------------------------------------------------ send / digest / tmpl */}
      <Row className="g-4">
        <Col lg={5}>
          <Card className="h-100">
            <Card.Body>
              <Card.Title style={{ fontSize: "1rem" }}>Send a notification</Card.Title>
              <Form onSubmit={sendNotification}>
                <Row className="g-2">
                  <Col sm={6}>
                    <Form.Group>
                      <Form.Label>Channel</Form.Label>
                      <Form.Select
                        value={sendForm.channel}
                        onChange={(e) => setSendForm({ ...sendForm, channel: e.target.value })}
                      >
                        {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
                      </Form.Select>
                    </Form.Group>
                  </Col>
                  <Col sm={6}>
                    <Form.Group>
                      <Form.Label>Recipient</Form.Label>
                      <Form.Control
                        required value={sendForm.recipient}
                        onChange={(e) => setSendForm({ ...sendForm, recipient: e.target.value })}
                      />
                    </Form.Group>
                  </Col>
                </Row>
                <Form.Group className="mt-2">
                  <Form.Label>Subject</Form.Label>
                  <Form.Control
                    value={sendForm.subject}
                    onChange={(e) => setSendForm({ ...sendForm, subject: e.target.value })}
                  />
                </Form.Group>
                <Form.Group className="mt-2">
                  <Form.Label>Body</Form.Label>
                  <Form.Control
                    as="textarea" rows={3} required value={sendForm.body}
                    onChange={(e) => setSendForm({ ...sendForm, body: e.target.value })}
                  />
                </Form.Group>
                <Button type="submit" className="mt-3">Send</Button>
              </Form>
              {sendResult && (
                <Alert variant={sendResult.variant} className="mt-3 py-2 small mb-0">
                  {sendResult.text}
                </Alert>
              )}
            </Card.Body>
          </Card>
        </Col>

        <Col lg={7}>
          <Card className="h-100">
            <Card.Body>
              <Card.Title style={{ fontSize: "1rem" }}>Templates &amp; digest</Card.Title>
              <Form onSubmit={lookupDigest} className="d-flex gap-2 align-items-end mb-3">
                <Form.Group className="flex-grow-1">
                  <Form.Label>24h digest for recipient</Form.Label>
                  <Form.Control
                    required value={digestRecipient}
                    onChange={(e) => setDigestRecipient(e.target.value)}
                    placeholder="procurement@medisource.local"
                  />
                </Form.Group>
                <Button type="submit" variant="outline-dark">Look up</Button>
              </Form>
              {digest && (
                <Alert variant="light" className="py-2 small">
                  <strong>{digest.count} notification(s)</strong> in the last {digest.hours}h
                </Alert>
              )}
              <div style={{ maxHeight: 240, overflowY: "auto" }}>
                <Table hover size="sm">
                  <thead><tr><th>Template</th><th>Event</th><th>Channel</th></tr></thead>
                  <tbody>
                    {templates.map((t) => (
                      <tr key={t.id}>
                        <td>{t.name}</td>
                        <td className="text-muted" style={{ fontSize: "0.78rem" }}>{t.event_type}</td>
                        <td><Badge bg="secondary">{t.channel}</Badge></td>
                      </tr>
                    ))}
                    {templates.length === 0 && (
                      <tr><td colSpan={3} className="text-muted">No templates yet.</td></tr>
                    )}
                  </tbody>
                </Table>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
