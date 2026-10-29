import React, { useMemo, useState } from "react";
import { Alert, Badge, Button, Card, Col, Form, Modal, Row, Spinner, Table } from "react-bootstrap";
import { contractsApi } from "../api/client.js";
import { useLiveData } from "../api/useLiveData.js";
import ConnectionAlert from "../components/ConnectionAlert.jsx";
import FilterBar, { withinRange } from "../components/FilterBar.jsx";
import { useAuth } from "../context/AuthContext.jsx";

const statusVariant = { draft: "secondary", sent_for_signature: "info", signed: "success", declined: "danger", expired: "danger", terminated: "dark" };

export default function ContractRepository() {
  const { currentUser } = useAuth();
  const canManageContracts = currentUser?.role === "procurement_director";
  const [contracts, setContracts] = useState([]);
  const [form, setForm] = useState({
    template_type: "supply_agreement", vendor_id: "", request_id: "",
    vendor_name: "", total_value: "", effective_date: "", expiry_date: "",
  });
  const [docPdf, setDocPdf] = useState(null);
  const [docTitle, setDocTitle] = useState("Contract document");
  const [docLoading, setDocLoading] = useState(false);
  const [signingContract, setSigningContract] = useState(null);
  const [signer, setSigner] = useState({ name: "", email: "" });
  const [signing, setSigning] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [signingStatus, setSigningStatus] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [templateFilter, setTemplateFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const errorMessage = async (err, fallback) => {
    const data = err.response?.data;
    if (data instanceof Blob) {
      try {
        const parsed = JSON.parse(await data.text());
        const detail = parsed.detail || parsed.message;
        return typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : fallback;
      } catch { return fallback; }
    }
    const detail = data?.detail || data?.message;
    return typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : fallback;
  };

  const loadContracts = () => contractsApi.get("").then((res) => setContracts(res.data));
  const { error: connectionError, refresh: reloadContracts } = useLiveData(loadContracts);
  const loadSigningStatus = () => contractsApi.get("/signing-status").then((res) => setSigningStatus(res.data));
  const { error: signingStatusError } = useLiveData(loadSigningStatus, { intervalMs: 30000 });

  const generate = async (e) => {
    e.preventDefault();
    setActionError(null);
    try {
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
    } catch (err) {
      const msg = err.response?.data?.detail || "Contract generation failed";
      setActionError(typeof msg === "object" ? JSON.stringify(msg) : msg);
    }
  };

  const viewDocument = async (id) => {
    setActionError(null);
    setDocLoading(true);
    try {
      const res = await contractsApi.get("/" + id + "/document", { responseType: "blob" });
      if (docPdf) URL.revokeObjectURL(docPdf);
      setDocPdf(URL.createObjectURL(res.data));
      setDocTitle("Contract document");
    } catch (err) {
      setActionError(await errorMessage(err, "Could not view document. Check that the contract file is available in storage."));
    } finally {
      setDocLoading(false);
    }
  };

  const viewSignedDocument = async (id) => {
    setActionError(null);
    setDocLoading(true);
    try {
      const res = await contractsApi.get(`/${id}/signed-document`, { responseType: "blob" });
      if (docPdf) URL.revokeObjectURL(docPdf);
      setDocPdf(URL.createObjectURL(res.data));
      setDocTitle("Signed contract");
    } catch (err) {
      setActionError(await errorMessage(err, "Could not load the signed document."));
    } finally {
      setDocLoading(false);
    }
  };

  const sendForSignature = async (e) => {
    e.preventDefault();
    if (!signingContract) return;
    setActionError(null);
    setSigning(true);
    try {
      await contractsApi.post(`/${signingContract.id}/send-for-signature?signer_email=${encodeURIComponent(signer.email)}&signer_name=${encodeURIComponent(signer.name)}`);
      setSigningContract(null);
      setSigner({ name: "", email: "" });
      reloadContracts();
    } catch (err) {
      setActionError(await errorMessage(err, "Failed to send contract for signature."));
    } finally {
      setSigning(false);
    }
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
      {actionError && <Alert variant="danger" dismissible onClose={() => setActionError(null)}>{actionError}</Alert>}
      {signingStatus && !signingStatus.ready && <Alert variant="warning">
        <strong>DocuSign setup is incomplete.</strong>
        {!signingStatus.email_invites_enabled && <div>Set the Integration Key, User ID, and RSA private key in the project environment.</div>}
        {!signingStatus.completion_tracking_enabled && <div>Set a public HTTPS Connect callback URL and HMAC key; the callback path is <code>/api/contracts/webhooks/docusign</code>.</div>}
        <div>Restart the contract service after updating configuration. Existing contracts remain available here.</div>
      </Alert>}
      {signingStatusError && <Alert variant="secondary">E-signature integration status is unavailable. Contract records and document links are still shown below.</Alert>}
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
        <Col xl={5}>
          <Card className="ms-bento-card">
            <Card.Body>
              <Card.Title>{canManageContracts ? "Generate a contract" : "Contract access"}</Card.Title>
              {canManageContracts ? <>
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
              </> : <Alert variant="info" className="mb-0">You have read access to the contract repository. Contract generation and signature actions are available to the Procurement Director.</Alert>}
            </Card.Body>
          </Card>
        </Col>

        <Col xl={7}>
          <Card className="ms-bento-card">
          <Card.Body>
          <Card.Title>Contract repository</Card.Title>
          <FilterBar
            search={search} onSearch={setSearch}
            searchPlaceholder="Search vendor, template, contract no…"
            selects={[
              { key: "status", label: "Status", value: statusFilter, onChange: setStatusFilter,
                options: ["draft", "sent_for_signature", "signed", "declined", "expired", "terminated"] },
              { key: "template", label: "Template", value: templateFilter, onChange: setTemplateFilter,
                options: ["supply_agreement", "equipment_amc", "vendor_agreement", "nda"] },
            ]}
            dateFrom={dateFrom} dateTo={dateTo}
            onDateFrom={setDateFrom} onDateTo={setDateTo}
            showing={filtered.length} total={contracts.length}
            onClear={clearFilters}
          />
          <div className="ms-table-card ms-scroll-pane" style={{ maxHeight: 520 }}>
          <Table hover size="sm" responsive>
          <thead><tr><th>Vendor</th><th>Template</th><th>Document / signature status</th><th>Expiry</th><th>Documents and actions</th></tr></thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id}>
                  <td className="text-truncate" style={{ maxWidth: 130 }}>{c.vendor_id}</td>
                  <td className="text-muted" style={{ fontSize: "0.78rem" }}>
                    {(c.template_type || "").replace(/_/g, " ")}
                  </td>
                  <td>
                    <Badge bg={statusVariant[c.status] || "secondary"}>{c.status === "signed" ? "E-Signature Complete" : c.status === "sent_for_signature" ? "Pending E-Signature" : (c.status || "").replace(/_/g, " ")}</Badge>
                    <div className="small mt-1">{c.status === "signed" ? "Signed contract PDF" : "Unsigned contract PDF"}</div>
                    {c.signing_error && <div className="small text-danger mt-1">{c.signing_error}</div>}
                  </td>
                  <td>{c.expiry_date}</td>
                  <td className="d-flex gap-1">
                    <Button size="sm" variant="outline-secondary" onClick={() => c.status === "signed" ? viewSignedDocument(c.id) : viewDocument(c.id)} disabled={docLoading}>{docLoading ? <Spinner size="sm" /> : c.status === "signed" ? "View signed PDF" : "View unsigned PDF"}</Button>
                    {canManageContracts && c.status === "draft" && <Button size="sm" variant="outline-primary" onClick={() => setSigningContract(c)}>Send for e-signature</Button>}
                    {c.status === "sent_for_signature" && c.signing_url && <Button size="sm" variant="outline-primary" href={c.signing_url} target="_blank" rel="noreferrer">Open signer</Button>}
                    {c.status === "signed" && c.signed_object_key && <Button size="sm" variant="outline-success" onClick={() => viewSignedDocument(c.id)} disabled={docLoading}>Open signed contract</Button>}
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
          {contracts.some((c) => ["sent_for_signature", "signed", "declined"].includes(c.status)) && (
            <Card className="mt-3">
              <Card.Body>
                <Card.Title className="mb-1">Digital signature activity</Card.Title>
                <div className="text-muted small mb-3">Envelope tracking from the e-signature provider</div>
                {contracts.filter((c) => ["sent_for_signature", "signed", "declined"].includes(c.status)).map((c) => (
                  <div key={c.id} className="border rounded-3 p-3 mb-2">
                    <div className="d-flex flex-wrap justify-content-between gap-2 align-items-center">
                      <strong>Contract {String(c.id).slice(0, 8)}</strong>
                      <Badge bg={statusVariant[c.status] || "secondary"}>{c.status === "signed" ? "E-signature complete" : c.status === "declined" ? "Signature declined" : "Awaiting signer"}</Badge>
                    </div>
                    <div className="small mt-2"><strong>Provider:</strong> {c.signing_provider || "Not sent"} · <strong>Signer:</strong> {c.signer_name || "—"}{c.signer_email ? " (" + c.signer_email + ")" : ""}</div>
                    <div className="small"><strong>Envelope ID:</strong> <code>{c.esign_envelope_id || "Pending provider response"}</code></div>
                    {c.signing_url && c.status === "sent_for_signature" && <a className="small" href={c.signing_url} target="_blank" rel="noreferrer">Open signing request</a>}
                    {c.signed_object_key && <div className="small mt-1"><Button size="sm" variant="link" className="p-0" onClick={() => viewSignedDocument(c.id)}>View signed contract PDF</Button></div>}
                    {c.signing_error && <Alert variant="warning" className="small mt-2 mb-0">{c.signing_error}</Alert>}
                    {c.events?.length > 0 && <div className="small text-muted mt-1">{c.events.map((event) => `${event.event.replace(/_/g, " ")} · ${new Date(event.at).toLocaleString()}`).join("  →  ")}</div>}
                    {c.signing_provider === "demo" && <div className="small text-warning mt-2">Demo envelope only. No real signature request was sent.</div>}
                  </div>
                ))}
              </Card.Body>
            </Card>
          )}
          </Card.Body>
          </Card>
        </Col>
      </Row>

      <Modal show={!!docPdf} onHide={() => { if (docPdf) URL.revokeObjectURL(docPdf); setDocPdf(null); }} size="lg">
        <Modal.Header closeButton><Modal.Title>{docTitle}</Modal.Title></Modal.Header>
        <Modal.Body className="p-0"><iframe title="Contract PDF preview" src={docPdf || undefined} style={{ width: "100%", height: "75vh", border: 0 }} /></Modal.Body>
      </Modal>
      <Modal show={!!signingContract} onHide={() => !signing && setSigningContract(null)} centered>
        <Form onSubmit={sendForSignature}>
          <Modal.Header closeButton><Modal.Title>Send contract for digital signature</Modal.Title></Modal.Header>
          <Modal.Body>
            <Alert variant="info" className="small">The contract will be sent to the signer through the configured e-signature provider. You can track its envelope and signing status here.</Alert>
            <Form.Group className="mb-3"><Form.Label>Signer name</Form.Label><Form.Control required value={signer.name} onChange={(e) => setSigner({ ...signer, name: e.target.value })} placeholder="Full name" /></Form.Group>
            <Form.Group><Form.Label>Signer email</Form.Label><Form.Control required type="email" value={signer.email} onChange={(e) => setSigner({ ...signer, email: e.target.value })} placeholder="name@company.com" /></Form.Group>
          </Modal.Body>
          <Modal.Footer><Button variant="secondary" onClick={() => setSigningContract(null)} disabled={signing}>Cancel</Button><Button type="submit" disabled={signing}>{signing ? <><Spinner size="sm" className="me-2" />Sending…</> : "Send for digital signature"}</Button></Modal.Footer>
        </Form>
      </Modal>
    </div>
  );
}
