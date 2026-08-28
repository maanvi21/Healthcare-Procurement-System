import React, { useMemo, useState } from "react";
import { Badge, Button, Card, Col, Form, Modal, Row, Table } from "react-bootstrap";
import { contractsApi } from "../api/client.js";
import { useLiveData } from "../api/useLiveData.js";
import ConnectionAlert from "../components/ConnectionAlert.jsx";
import FilterBar, { withinRange } from "../components/FilterBar.jsx";

const statusVariant = { draft: "secondary", sent_for_signature: "info", signed: "success", expired: "danger", terminated: "dark" };

export default function ContractRepository() {
  const [contracts, setContracts] = useState([]);
  const [form, setForm] = useState({
    template_type: "supply_agreement", vendor_id: "", request_id: "",
    vendor_name: "", total_value: "", effective_date: "", expiry_date: "",
  });
  const [docHtml, setDocHtml] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [templateFilter, setTemplateFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const loadContracts = () => contractsApi.get("").then((res) => setContracts(res.data));
  const { error: connectionError, refresh: reloadContracts } = useLiveData(loadContracts);

  const generate = async (e) => {
    e.preventDefault();
    await contractsApi.post("", {
      template_type: form.template_type,
      vendor_id: form.vendor_id,
      request_id: form.request_id || null,
      context: {
        hospital_name: "MediSource General Hospital",
        vendor_name: form.vendor_name,
        items: [],
        total_value: parseFloat(form.total_value || 0),
        currency: "INR",
      },
      effective_date: form.effective_date,
      expiry_date: form.expiry_date,
      renewal_reminder_days: 30,
    });
    reloadContracts();
  };

  const viewDocument = async (id) => {
    const res = await contractsApi.get(`/${id}/document`);
    setDocHtml(res.data.html);
  };

  const sendForSignature = async (id) => {
    const email = prompt("Signer email:");
    const name = prompt("Signer name:");
    if (!email || !name) return;
    await contractsApi.post(`/${id}/send-for-signature?signer_email=${encodeURIComponent(email)}&signer_name=${encodeURIComponent(name)}`);
    reloadContracts();
  };

  const markSigned = async (id) => {
    await contractsApi.post(`/${id}/webhook/signed`);
    reloadContracts();
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return contracts.filter((c) => {
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      if (templateFilter !== "all" && c.template_type !== templateFilter) return false;
      // filter on expiry, which is the date a contract manager actually searches by
      if (!withinRange(c.expiry_date, dateFrom, dateTo)) return false;
      if (!q) return true;
      return [c.vendor_id, c.template_type, c.status, c.contract_number]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q));
    });
  }, [contracts, search, statusFilter, templateFilter, dateFrom, dateTo]);

  const signed = contracts.filter((c) => c.status === "signed").length;
  const awaiting = contracts.filter((c) => c.status === "sent_for_signature").length;
  const expiringSoon = contracts.filter((c) => {
    if (!c.expiry_date || c.status === "terminated") return false;
    const days = (new Date(c.expiry_date) - Date.now()) / 86400000;
    return days >= 0 && days <= 60;
  }).length;

  const clearFilters = () => {
    setSearch(""); setStatusFilter("all"); setTemplateFilter("all"); setDateFrom(""); setDateTo("");
  };

  return (
    <div>
      <h1 className="ms-page-title">Contract Intelligence</h1>
      <ConnectionAlert error={connectionError} onRetry={reloadContracts} />
      <p className="ms-page-sub">
        Templated contracts (Supply Agreement, Biomedical Equipment AMC, Vendor Agreement,
        NDA) auto-populated and routed for e-signature, with version/renewal/expiry tracking.
      </p>

      <Row className="g-3 mb-3" xs={2} md={4}>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Contracts</div>
            <div className="ms-stat-value">{contracts.length}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Signed</div>
            <div className="ms-stat-value">{signed}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Awaiting signature</div>
            <div className="ms-stat-value" style={{ color: awaiting ? "#b7791f" : undefined }}>{awaiting}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Expiring ≤60 days</div>
            <div className="ms-stat-value" style={{ color: expiringSoon ? "#c53434" : undefined }}>{expiringSoon}</div>
          </div>
        </Col>
      </Row>

      <Row className="g-4">
        <Col md={5}>
          <Card>
            <Card.Body>
              <Card.Title>Generate a contract</Card.Title>
              <div className="ms-scroll-pane" style={{ maxHeight: 520 }}>
              <Form onSubmit={generate}>
                <Form.Group className="mb-2"><Form.Label>Template</Form.Label>
                  <Form.Select value={form.template_type} onChange={(e) => setForm({ ...form, template_type: e.target.value })}>
                    <option value="supply_agreement">Supply Agreement</option>
                    <option value="equipment_amc">Equipment AMC</option>
                    <option value="vendor_agreement">Vendor Agreement</option>
                    <option value="nda">NDA</option>
                  </Form.Select></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Vendor ID</Form.Label>
                  <Form.Control required value={form.vendor_id} onChange={(e) => setForm({ ...form, vendor_id: e.target.value })} placeholder="uuid from Vendors page" /></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Vendor name (for the document text)</Form.Label>
                  <Form.Control required value={form.vendor_name} onChange={(e) => setForm({ ...form, vendor_name: e.target.value })} /></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Total value (INR)</Form.Label>
                  <Form.Control type="number" value={form.total_value} onChange={(e) => setForm({ ...form, total_value: e.target.value })} /></Form.Group>
                <Row>
                  <Col><Form.Group className="mb-2"><Form.Label>Effective date</Form.Label>
                    <Form.Control type="date" required value={form.effective_date} onChange={(e) => setForm({ ...form, effective_date: e.target.value })} /></Form.Group></Col>
                  <Col><Form.Group className="mb-2"><Form.Label>Expiry date</Form.Label>
                    <Form.Control type="date" required value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} /></Form.Group></Col>
                </Row>
                <Button type="submit" className="mt-2">Generate</Button>
              </Form>
              </div>
            </Card.Body>
          </Card>
        </Col>

        <Col md={7}>
          <h5>Contract repository</h5>
          <FilterBar
            search={search} onSearch={setSearch}
            searchPlaceholder="Search vendor, template, contract no…"
            selects={[
              { key: "status", label: "Status", value: statusFilter, onChange: setStatusFilter,
                options: ["draft", "sent_for_signature", "signed", "expired", "terminated"] },
              { key: "template", label: "Template", value: templateFilter, onChange: setTemplateFilter,
                options: ["supply_agreement", "equipment_amc", "vendor_agreement", "nda"] },
            ]}
            dateFrom={dateFrom} dateTo={dateTo}
            onDateFrom={setDateFrom} onDateTo={setDateTo}
            showing={filtered.length} total={contracts.length}
            onClear={clearFilters}
          />
          <div className="ms-table-card ms-scroll-pane" style={{ maxHeight: 520 }}>
          <Table hover size="sm">
            <thead><tr><th>Vendor</th><th>Template</th><th>Status</th><th>Expiry</th><th></th></tr></thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id}>
                  <td className="text-truncate" style={{ maxWidth: 130 }}>{c.vendor_id}</td>
                  <td className="text-muted" style={{ fontSize: "0.78rem" }}>
                    {(c.template_type || "").replace(/_/g, " ")}
                  </td>
                  <td><Badge bg={statusVariant[c.status]}>{(c.status || "").replace(/_/g, " ")}</Badge></td>
                  <td>{c.expiry_date}</td>
                  <td className="d-flex gap-1">
                    <Button size="sm" variant="outline-secondary" onClick={() => viewDocument(c.id)}>View</Button>
                    {c.status === "draft" && <Button size="sm" variant="outline-primary" onClick={() => sendForSignature(c.id)}>Send</Button>}
                    {c.status === "sent_for_signature" && <Button size="sm" variant="outline-success" onClick={() => markSigned(c.id)}>Mark signed</Button>}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={5} className="text-muted">
                  {contracts.length === 0 ? "No contracts yet." : "No contracts match these filters."}
                </td></tr>
              )}
            </tbody>
          </Table>
          </div>
        </Col>
      </Row>

      <Modal show={!!docHtml} onHide={() => setDocHtml(null)} size="lg">
        <Modal.Header closeButton><Modal.Title>Contract document</Modal.Title></Modal.Header>
        <Modal.Body dangerouslySetInnerHTML={{ __html: docHtml || "" }} />
      </Modal>
    </div>
  );
}
