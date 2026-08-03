import React, { useEffect, useState } from "react";
import { Badge, Button, Card, Col, Form, Row, Table } from "react-bootstrap";
import { approvalsApi } from "../api/client.js";

const statusVariant = { pending: "warning", approved: "success", rejected: "danger", escalated: "info" };

export default function ApproverInbox() {
  const [role, setRole] = useState("department_manager");
  const [inbox, setInbox] = useState([]);
  const [requests, setRequests] = useState([]);
  const [form, setForm] = useState({
    requested_by: "", department: "pharmacy", category: "pharma", vendor_id: "",
    vendor_risk_band: "low", total_value: "", sku: "", quantity: "",
  });

  const loadInbox = () => approvalsApi.get(`/inbox?approver_role=${role}`).then((res) => setInbox(res.data)).catch(() => setInbox([]));
  const loadRequests = () => approvalsApi.get("/requests").then((res) => setRequests(res.data)).catch(() => {});

  useEffect(loadInbox, [role]);
  useEffect(loadRequests, []);

  const submitRequest = async (e) => {
    e.preventDefault();
    const payload = {
      requested_by: form.requested_by,
      department: form.department,
      category: form.category,
      vendor_id: form.vendor_id || null,
      vendor_risk_band: form.vendor_risk_band,
      total_value: parseFloat(form.total_value || 0),
      items: form.sku ? [{ sku: form.sku, quantity: parseInt(form.quantity || 0, 10) }] : [],
    };
    await approvalsApi.post("/requests", payload);
    loadRequests();
    loadInbox();
  };

  const decide = async (requestId, stepOrder, decision) => {
    await approvalsApi.post(`/requests/${requestId}/decide`, {
      step_order: stepOrder, decision, actor: role,
    });
    setTimeout(() => { loadInbox(); loadRequests(); }, 500); // Temporal signal processing is async
  };

  return (
    <div>
      <h2>Approval Workflow</h2>
      <p className="text-muted">
        Policy-driven approval routing (Open Policy Agent) with Temporal-orchestrated SLA
        tracking and automatic escalation on timeout.
      </p>

      <Row className="g-4">
        <Col md={5}>
          <Card>
            <Card.Body>
              <Card.Title>Submit a procurement request</Card.Title>
              <Form onSubmit={submitRequest}>
                <Form.Group className="mb-2">
                  <Form.Label>Requested by</Form.Label>
                  <Form.Control required value={form.requested_by} onChange={(e) => setForm({ ...form, requested_by: e.target.value })} />
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Department</Form.Label>
                  <Form.Control value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Category</Form.Label>
                  <Form.Select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                    <option value="pharma">Pharma</option>
                    <option value="controlled_substance">Controlled substance</option>
                    <option value="equipment">Equipment</option>
                    <option value="consumable">Consumable</option>
                    <option value="ppe">PPE</option>
                  </Form.Select>
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Vendor ID (optional)</Form.Label>
                  <Form.Control value={form.vendor_id} onChange={(e) => setForm({ ...form, vendor_id: e.target.value })} placeholder="uuid from Vendors page" />
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Vendor risk band</Form.Label>
                  <Form.Select value={form.vendor_risk_band} onChange={(e) => setForm({ ...form, vendor_risk_band: e.target.value })}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </Form.Select>
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Total value (INR)</Form.Label>
                  <Form.Control type="number" required value={form.total_value} onChange={(e) => setForm({ ...form, total_value: e.target.value })} />
                </Form.Group>
                <Row>
                  <Col>
                    <Form.Group className="mb-2">
                      <Form.Label>SKU (optional)</Form.Label>
                      <Form.Control value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} />
                    </Form.Group>
                  </Col>
                  <Col>
                    <Form.Group className="mb-2">
                      <Form.Label>Quantity</Form.Label>
                      <Form.Control type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
                    </Form.Group>
                  </Col>
                </Row>
                <Button type="submit" className="mt-2">Submit request</Button>
              </Form>
            </Card.Body>
          </Card>
        </Col>

        <Col md={7}>
          <div className="d-flex justify-content-between align-items-center mb-2">
            <h5 className="mb-0">Approver inbox</h5>
            <Form.Select style={{ width: 220 }} value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="department_manager">Department manager</option>
              <option value="finance_manager">Finance manager</option>
              <option value="compliance_officer">Compliance officer</option>
              <option value="procurement_director">Procurement director</option>
            </Form.Select>
          </div>
          <Table hover size="sm">
            <thead><tr><th>Department</th><th>Value</th><th>Step</th><th></th></tr></thead>
            <tbody>
              {inbox.map((req) => {
                const step = req.steps.find((s) => s.approver_role === role && s.status === "pending");
                if (!step) return null;
                return (
                  <tr key={req.id}>
                    <td>{req.department}</td>
                    <td>₹{req.total_value}</td>
                    <td>#{step.step_order + 1} ({step.sla_hours}h SLA)</td>
                    <td>
                      <Button size="sm" variant="success" className="me-1" onClick={() => decide(req.id, step.step_order, "approved")}>Approve</Button>
                      <Button size="sm" variant="danger" onClick={() => decide(req.id, step.step_order, "rejected")}>Reject</Button>
                    </td>
                  </tr>
                );
              })}
              {inbox.length === 0 && <tr><td colSpan={4} className="text-muted">Inbox is empty.</td></tr>}
            </tbody>
          </Table>

          <h5 className="mt-4">All requests</h5>
          <Table hover size="sm">
            <thead><tr><th>Department</th><th>Category</th><th>Value</th><th>Status</th></tr></thead>
            <tbody>
              {requests.map((r) => (
                <tr key={r.id}>
                  <td>{r.department}</td>
                  <td>{r.category}</td>
                  <td>₹{r.total_value}</td>
                  <td><Badge bg={statusVariant[r.status]}>{r.status}</Badge></td>
                </tr>
              ))}
              {requests.length === 0 && <tr><td colSpan={4} className="text-muted">No requests yet.</td></tr>}
            </tbody>
          </Table>
        </Col>
      </Row>
    </div>
  );
}
