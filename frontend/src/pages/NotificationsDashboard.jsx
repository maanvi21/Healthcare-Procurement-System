import React, { useState } from "react";
import { Badge, Button, Card, Col, Form, Row, Table } from "react-bootstrap";
import { notificationsApi } from "../api/client.js";
import { useLiveData } from "../api/useLiveData.js";
import ConnectionAlert from "../components/ConnectionAlert.jsx";

const statusBadge = { queued: "secondary", sent: "success", failed: "danger" };

export default function NotificationsDashboard() {
  const [notifications, setNotifications] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [filters, setFilters] = useState({ recipient: "", event_type: "" });
  const [sendForm, setSendForm] = useState({ channel: "email", recipient: "", subject: "", body: "" });
  const [digest, setDigest] = useState(null);
  const [digestRecipient, setDigestRecipient] = useState("");

  const loadNotifications = () =>
    notificationsApi
      .get("", {
        params: {
          recipient: filters.recipient || undefined,
          event_type: filters.event_type || undefined,
        },
      })
      .then((res) => setNotifications(res.data));
  const loadTemplates = () => notificationsApi.get("/templates").then((res) => setTemplates(res.data));

  const { error: connectionError, refresh: reloadAll } = useLiveData(
    () => Promise.all([loadNotifications(), loadTemplates()]),
    { deps: [filters.recipient, filters.event_type] }
  );

  const sendNotification = async (e) => {
    e.preventDefault();
    await notificationsApi.post("/send", sendForm);
    setSendForm({ channel: sendForm.channel, recipient: "", subject: "", body: "" });
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
      <h2>Notification Agent</h2>
      <ConnectionAlert error={connectionError} onRetry={reloadAll} />
      <p className="text-muted">
        Multi-channel notifications rendered from platform events — vendor onboarding, document
        processing, approval decisions, risk assessments, backorders and signed contracts.
      </p>

      <Row className="g-4">
        <Col md={5}>
          <Card className="mb-4">
            <Card.Body>
              <Card.Title>Send a notification</Card.Title>
              <Form onSubmit={sendNotification}>
                <Form.Group className="mb-2">
                  <Form.Label>Channel</Form.Label>
                  <Form.Select
                    value={sendForm.channel}
                    onChange={(e) => setSendForm({ ...sendForm, channel: e.target.value })}
                  >
                    <option value="email">Email</option>
                    <option value="sms">SMS</option>
                    <option value="teams">Teams</option>
                    <option value="slack">Slack</option>
                  </Form.Select>
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Recipient</Form.Label>
                  <Form.Control
                    required
                    value={sendForm.recipient}
                    onChange={(e) => setSendForm({ ...sendForm, recipient: e.target.value })}
                  />
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Subject</Form.Label>
                  <Form.Control
                    value={sendForm.subject}
                    onChange={(e) => setSendForm({ ...sendForm, subject: e.target.value })}
                  />
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Body</Form.Label>
                  <Form.Control
                    as="textarea"
                    rows={3}
                    required
                    value={sendForm.body}
                    onChange={(e) => setSendForm({ ...sendForm, body: e.target.value })}
                  />
                </Form.Group>
                <Button type="submit">Send</Button>
              </Form>
            </Card.Body>
          </Card>

          <Card className="mb-4">
            <Card.Body>
              <Card.Title>Recipient digest (24h)</Card.Title>
              <Form onSubmit={lookupDigest}>
                <Form.Group className="mb-2">
                  <Form.Label>Recipient</Form.Label>
                  <Form.Control
                    required
                    value={digestRecipient}
                    onChange={(e) => setDigestRecipient(e.target.value)}
                  />
                </Form.Group>
                <Button type="submit" variant="outline-dark">Look up</Button>
              </Form>
              {digest && (
                <div className="mt-3 small">
                  <div className="fw-semibold">{digest.count} notification(s) in the last {digest.hours}h</div>
                  <div className="text-muted">{digest.summary}</div>
                </div>
              )}
            </Card.Body>
          </Card>

          <Card>
            <Card.Body>
              <Card.Title>Templates</Card.Title>
              <Table hover size="sm">
                <thead><tr><th>Name</th><th>Event</th><th>Channel</th></tr></thead>
                <tbody>
                  {templates.map((t) => (
                    <tr key={t.id}><td>{t.name}</td><td>{t.event_type}</td><td>{t.channel}</td></tr>
                  ))}
                  {templates.length === 0 && (
                    <tr><td colSpan={3} className="text-muted">No templates yet.</td></tr>
                  )}
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>

        <Col md={7}>
          <div className="d-flex gap-2 mb-2">
            <Form.Control
              size="sm"
              placeholder="Filter by recipient"
              value={filters.recipient}
              onChange={(e) => setFilters({ ...filters, recipient: e.target.value })}
            />
            <Form.Control
              size="sm"
              placeholder="Filter by event type"
              value={filters.event_type}
              onChange={(e) => setFilters({ ...filters, event_type: e.target.value })}
            />
          </div>
          <Table hover size="sm">
            <thead>
              <tr><th>When</th><th>Channel</th><th>Recipient</th><th>Event</th><th>Subject</th><th>Status</th></tr>
            </thead>
            <tbody>
              {notifications.map((n) => (
                <tr key={n.id}>
                  <td>{new Date(n.created_at).toLocaleString()}</td>
                  <td>{n.channel}</td>
                  <td>{n.recipient}</td>
                  <td>{n.event_type || "—"}</td>
                  <td>{n.subject || "—"}</td>
                  <td><Badge bg={statusBadge[n.status] || "secondary"}>{n.status}</Badge></td>
                </tr>
              ))}
              {notifications.length === 0 && (
                <tr><td colSpan={6} className="text-muted">No notifications yet.</td></tr>
              )}
            </tbody>
          </Table>
        </Col>
      </Row>
    </div>
  );
}
