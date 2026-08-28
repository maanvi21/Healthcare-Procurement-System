import React, { useEffect, useMemo, useRef, useState } from "react";
import { Badge, Button, Card, Col, Form, Row, Table } from "react-bootstrap";
import { approvalsApi } from "../api/client.js";
import { useLiveData } from "../api/useLiveData.js";
import ConnectionAlert from "../components/ConnectionAlert.jsx";
import FilterBar, { withinRange } from "../components/FilterBar.jsx";

const statusVariant = { pending: "warning", approved: "success", rejected: "danger", escalated: "info" };

const money = (value, currency = "INR") => {
  const n = Number(value);
  if (Number.isNaN(n)) return `${value}`;
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(n);
};

const itemLabel = (item) =>
  item.description || item.name || item.sku || "item";

// An SLA deadline is only useful as time remaining — "2026-08-29T11:00" makes the reader
// do the arithmetic that decides whether this is urgent.
const slaRemaining = (deadline) => {
  if (!deadline) return null;
  const ms = new Date(deadline).getTime() - Date.now();
  if (Number.isNaN(ms)) return null;
  const overdue = ms < 0;
  const hours = Math.floor(Math.abs(ms) / 3600000);
  const mins = Math.floor((Math.abs(ms) % 3600000) / 60000);
  const text = hours >= 1 ? `${hours}h ${mins}m` : `${mins}m`;
  return { overdue, text: overdue ? `${text} overdue` : `${text} left` };
};

export default function ApproverInbox() {
  const [role, setRole] = useState("department_manager");
  const [inbox, setInbox] = useState([]);
  // decisions in flight, keyed "requestId:stepOrder" -> "approved" | "rejected"
  const [deciding, setDeciding] = useState({});
  const [requests, setRequests] = useState([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [deptFilter, setDeptFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [form, setForm] = useState({
    requested_by: "", title: "", description: "", department: "pharmacy", category: "pharma",
    vendor_id: "", vendor_risk_band: "", total_value: "", sku: "", quantity: "",
  });

  const loadInbox = () => approvalsApi.get(`/inbox?approver_role=${role}`).then((res) => setInbox(res.data));

  // the polling loop in decide() needs the freshest inbox, not the value captured when it
  // started, so mirror it into a ref
  const inboxRef = useRef(inbox);
  useEffect(() => { inboxRef.current = inbox; }, [inbox]);

  const pendingStep = (req) => req.steps.find((s) => s.approver_role === role && s.status === "pending");
  const approvedCount = (req) => req.steps.filter((s) => s.status === "approved").length;
  const loadRequests = () => approvalsApi.get("/requests").then((res) => setRequests(res.data));

  // `role` is a dep so switching approver refetches the inbox immediately rather than
  // waiting out the poll interval
  const { error: connectionError, refresh: reloadInbox } = useLiveData(
    () => Promise.all([loadInbox(), loadRequests()]),
    { deps: [role] }
  );

  const submitRequest = async (e) => {
    e.preventDefault();
    // vendor_id must be a UUID string or null — plain integers are not valid
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const vendorId = form.vendor_id && uuidPattern.test(form.vendor_id.trim())
      ? form.vendor_id.trim()
      : null;
    const payload = {
      requested_by: form.requested_by,
      title: form.title || null,
      description: form.description || null,
      department: form.department,
      category: form.category,
      vendor_id: vendorId,
      // "" means let the service look the band up from risk_intelligence;
      // sending "low" by default asserted a band nobody had measured.
      vendor_risk_band: form.vendor_risk_band || null,
      total_value: parseFloat(form.total_value || 0),
      items: form.sku
        ? [{ sku: form.sku, quantity: parseInt(form.quantity || 0, 10), description: form.title || form.sku }]
        : [],
    };
    await approvalsApi.post("/requests", payload);
    reloadInbox();
  };

  // A decision is a Temporal signal, not a synchronous write: the API returns as soon as
  // the signal is delivered, and the workflow updates the step a few seconds later. A
  // single refetch at 500ms therefore read the database *before* anything had changed, so
  // the row sat there unchanged and the approval looked like it had failed. Poll briefly
  // until the step actually leaves the inbox instead.
  const decide = async (requestId, stepOrder, decision) => {
    const key = `${requestId}:${stepOrder}`;
    setDeciding((d) => ({ ...d, [key]: decision }));
    try {
      await approvalsApi.post(`/requests/${requestId}/decide`, {
        step_order: stepOrder, decision, actor: role,
      });
      for (let attempt = 0; attempt < 10; attempt += 1) {
        await new Promise((r) => setTimeout(r, 1000));
        const settled = await reloadInbox();
        if (settled !== false) {
          const stillThere = inboxRef.current.some(
            (req) => req.id === requestId && pendingStep(req)?.step_order === stepOrder
          );
          if (!stillThere) break;
        }
      }
    } finally {
      setDeciding((d) => {
        const next = { ...d };
        delete next[key];
        return next;
      });
    }
  };

  const departments = [...new Set(requests.map((r) => r.department).filter(Boolean))];
  const filteredRequests = useMemo(() => {
    const q = search.trim().toLowerCase();
    return requests.filter((r) => {
      if (statusFilter !== "all" && r.status !== statusFilter) return false;
      if (deptFilter !== "all" && r.department !== deptFilter) return false;
      if (!withinRange(r.created_at, dateFrom, dateTo)) return false;
      if (!q) return true;
      return [r.title, r.description, r.department, r.category, r.requested_by]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q));
    });
  }, [requests, search, statusFilter, deptFilter, dateFrom, dateTo]);

  const clearFilters = () => {
    setSearch(""); setStatusFilter("all"); setDeptFilter("all"); setDateFrom(""); setDateTo("");
  };

  return (
    <div>
      <h1 className="ms-page-title">Approval Workflow</h1>
      <ConnectionAlert error={connectionError} onRetry={reloadInbox} />
      <p className="ms-page-sub">
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
                  <Form.Label>Title</Form.Label>
                  <Form.Control value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                    placeholder="e.g. Paracetamol 500mg restock" />
                  <Form.Text className="text-muted">Shown in the approver's inbox. Auto-derived from items if blank.</Form.Text>
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Description</Form.Label>
                  <Form.Control as="textarea" rows={2} value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    placeholder="Why this purchase is needed" />
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
                  <Form.Control value={form.vendor_id} onChange={(e) => setForm({ ...form, vendor_id: e.target.value })} placeholder="Paste vendor UUID from Vendors page (optional)" />
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Vendor risk band</Form.Label>
                  <Form.Select value={form.vendor_risk_band} onChange={(e) => setForm({ ...form, vendor_risk_band: e.target.value })}>
                    <option value="">Auto — look up from Risk service</option>
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
          <div style={{ maxHeight: 620, overflowY: "auto", paddingRight: 4 }}>
          {inbox.map((req) => {
            const step = req.steps.find((s) => s.approver_role === role && s.status === "pending");
            if (!step) return null;
            const busy = deciding[`${req.id}:${step.step_order}`];
            const sla = slaRemaining(step.sla_deadline);
            const items = (req.items || []).filter((i) => i && typeof i === "object");
            const priorSteps = req.steps.filter((s) => s.step_order < step.step_order);
            return (
              <Card key={req.id} className="mb-3 shadow-sm" style={{ borderLeft: "4px solid var(--bs-warning)" }}>
                <Card.Body>
                  <div className="d-flex justify-content-between align-items-start">
                    <div className="pe-3">
                      <Card.Title style={{ fontSize: "1.05rem" }} className="mb-1">
                        {req.title || `${req.category} purchase for ${req.department}`}
                      </Card.Title>
                      <div className="text-muted small">
                        {req.department} · {req.category} · requested by {req.requested_by}
                      </div>
                    </div>
                    <div className="text-end flex-shrink-0">
                      <div className="fw-bold" style={{ fontSize: "1.15rem" }}>
                        {money(req.total_value, req.currency)}
                      </div>
                      {sla && (
                        <Badge bg={sla.overdue ? "danger" : "secondary"} className="mt-1">
                          {sla.text}
                        </Badge>
                      )}
                    </div>
                  </div>

                  {req.description && (
                    <p className="small text-body-secondary mt-2 mb-2">{req.description}</p>
                  )}

                  {items.length > 0 && (
                    <Table size="sm" className="mt-2 mb-2">
                      <thead>
                        <tr className="text-muted" style={{ fontSize: "0.75rem" }}>
                          <th>Item</th><th>SKU</th><th className="text-end">Qty</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((item, i) => (
                          <tr key={i} style={{ fontSize: "0.85rem" }}>
                            <td>{itemLabel(item)}</td>
                            <td className="text-muted">{item.sku || "—"}</td>
                            <td className="text-end">{item.quantity ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  )}

                  <div className="small text-muted mb-2">
                    Your step: <strong>#{step.step_order + 1} of {req.steps.length}</strong>{" "}
                    ({step.approver_role.replace(/_/g, " ")}, {step.sla_hours}h SLA)
                    {priorSteps.length > 0 && (
                      <> · already approved by{" "}
                        {priorSteps.map((s) => s.approver_role.replace(/_/g, " ")).join(", ")}</>
                    )}
                    {req.vendor_id && <> · vendor <code>{req.vendor_id.slice(0, 8)}</code></>}
                  </div>

                  <Button
                    size="sm" variant="success" className="me-2"
                    disabled={!!busy}
                    onClick={() => decide(req.id, step.step_order, "approved")}
                  >
                    {busy === "approved" ? "Approving…" : "Approve"}
                  </Button>
                  <Button
                    size="sm" variant="outline-danger"
                    disabled={!!busy}
                    onClick={() => decide(req.id, step.step_order, "rejected")}
                  >
                    {busy === "rejected" ? "Rejecting…" : "Reject"}
                  </Button>
                </Card.Body>
              </Card>
            );
          })}
          {inbox.length === 0 && <p className="text-muted">Inbox is empty.</p>}
          </div>

          <h5 className="mt-4">All requests</h5>
          <FilterBar
            search={search} onSearch={setSearch}
            searchPlaceholder="Search title, requester, category…"
            selects={[
              { key: "status", label: "Status", value: statusFilter, onChange: setStatusFilter,
                options: ["pending", "approved", "rejected", "escalated"] },
              { key: "dept", label: "Dept", value: deptFilter, onChange: setDeptFilter,
                options: departments },
            ]}
            dateFrom={dateFrom} dateTo={dateTo}
            onDateFrom={setDateFrom} onDateTo={setDateTo}
            showing={filteredRequests.length} total={requests.length}
            onClear={clearFilters}
          />
          <Table hover size="sm">
            <thead><tr><th>Request</th><th>Department</th><th>Value</th><th>Approvals</th><th>Status</th></tr></thead>
            <tbody>
              {filteredRequests.map((r) => (
                <tr key={r.id}>
                  <td>
                    <div>{r.title || `${r.category} purchase`}</div>
                    <div className="text-muted" style={{ fontSize: "0.75rem" }}>{r.category}</div>
                  </td>
                  <td>{r.department}</td>
                  <td>{money(r.total_value, r.currency)}</td>
                  <td className="small text-muted">
                    {approvedCount(r)} of {r.steps.length}
                    {r.status === "pending" && r.steps.length > approvedCount(r) &&
                      ` · waiting on ${r.steps.find((s) => s.status === "pending")?.approver_role.replace(/_/g, " ") ?? "—"}`}
                  </td>
                  <td><Badge bg={statusVariant[r.status]}>{r.status}</Badge></td>
                </tr>
              ))}
              {filteredRequests.length === 0 && <tr><td colSpan={5} className="text-muted">No requests match these filters.</td></tr>}
            </tbody>
          </Table>
        </Col>
      </Row>
    </div>
  );
}
