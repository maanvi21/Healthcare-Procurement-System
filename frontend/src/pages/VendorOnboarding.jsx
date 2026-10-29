import React, { useMemo, useState } from "react";
import { Alert, Badge, Button, Card, Col, Form, Row, Table } from "react-bootstrap";
import { riskApi, vendorsApi } from "../api/client.js";
import { useLiveData } from "../api/useLiveData.js";
import ConnectionAlert from "../components/ConnectionAlert.jsx";
import FilterBar from "../components/FilterBar.jsx";
import { ShapModal } from "./RiskDashboard.jsx";

const statusVariant = { pending_review: "warning", approved: "success", rejected: "danger", suspended: "secondary" };
const riskVariant = { low: "success", medium: "warning", high: "danger" };
const gstinFormat = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;

const emptyForm = {
  legal_name: "", vendor_type: "pharma_distributor", gst_number: "", drug_license_number: "",
  drug_license_expiry: "", fda_cdsco_registration_id: "", contact_email: "", contact_phone: "",
  address_line1: "", address_line2: "", city: "", state: "", postal_code: "", country: "India",
};

export default function VendorOnboarding() {
  const [vendors, setVendors] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [shap, setShap] = useState({ open: false, loading: false, data: null, error: null });
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");

  const openShap = async (vendorId) => {
    setShap({ open: true, loading: true, data: null, error: null });
    try {
      const res = await riskApi.get(`/vendors/${vendorId}/explain?top_n=6`);
      setShap({ open: true, loading: false, data: res.data, error: null });
    } catch (err) {
      setShap({
        open: true, loading: false, data: null,
        error: err.response?.data?.detail
          || "No risk assessment for this vendor yet — run one from the Risk page first.",
      });
    }
  };

  const loadVendors = () => vendorsApi.get("").then((res) => setVendors(res.data));
  const { error: connectionError, refresh: reloadVendors } = useLiveData(loadVendors);

  const submit = async (e) => {
    e.preventDefault();
    setActionError(null);
    const payload = { ...form };
    if (!payload.drug_license_expiry) delete payload.drug_license_expiry;
    if (!payload.drug_license_number) delete payload.drug_license_number;
    if (!payload.fda_cdsco_registration_id) delete payload.fda_cdsco_registration_id;
    if (!payload.gst_number) delete payload.gst_number;
    try {
      const res = await vendorsApi.post("", payload);
      setResult(res.data);
      setForm(emptyForm);
      reloadVendors();
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to onboard vendor";
      setActionError(typeof msg === "object" ? JSON.stringify(msg) : msg);
    }
  };

  // Filtering is local to what the page already polls, so narrowing never costs a
  // round trip and the live refresh keeps working unchanged.
  const filteredVendors = useMemo(() => {
    const q = search.trim().toLowerCase();
    return vendors.filter((v) => {
      if (typeFilter !== "all" && v.vendor_type !== typeFilter) return false;
      if (statusFilter !== "all" && v.status !== statusFilter) return false;
      if (riskFilter !== "all" && (v.risk_band || "none") !== riskFilter) return false;
      if (!q) return true;
      return [v.legal_name, v.city, v.state, v.gst_number, v.contact_email, v.vendor_type]
        .filter(Boolean)
        .some((x) => String(x).toLowerCase().includes(q));
    });
  }, [vendors, search, typeFilter, statusFilter, riskFilter]);

  const clearFilters = () => {
    setSearch(""); setTypeFilter("all"); setStatusFilter("all"); setRiskFilter("all");
  };

  return (
    <div>
      <h1 className="ms-page-title">Vendor Intelligence</h1>
      <ConnectionAlert error={connectionError} onRetry={reloadVendors} />
      <p className="ms-page-sub">
        Onboard medical suppliers, pharma distributors and biomedical AMC contractors with
        healthcare-specific KYC: drug-license validity, FDA/CDSCO registration, GSTIN,
        sanctions/watchlist screening, and contact &amp; registered-address validation.
        Anything that fails routes to <em>pending review</em> with the reason shown, rather
        than being approved or rejected outright. The risk score is a model assessment; it does not clear a vendor with an outstanding KYC hold.
      </p>

      <Row className="g-4">
        <Col lg={5}>
          <Card>
            <Card.Body>
              <Card.Title>Onboard a vendor</Card.Title>
              {actionError && <Alert variant="danger" dismissible onClose={() => setActionError(null)}>{actionError}</Alert>}
              <div className="ms-scroll-pane" style={{ maxHeight: 560 }}>
              <Form onSubmit={submit}>
                <Form.Group className="mb-2">
                  <Form.Label>Legal name</Form.Label>
                  <Form.Control required value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} />
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Vendor type</Form.Label>
                  <Form.Select value={form.vendor_type} onChange={(e) => setForm({ ...form, vendor_type: e.target.value })}>
                    <option value="pharma_distributor">Pharma distributor</option>
                    <option value="equipment_supplier">Equipment supplier</option>
                    <option value="amc_contractor">AMC contractor</option>
                    <option value="consumables_supplier">Consumables supplier</option>
                  </Form.Select>
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>GSTIN</Form.Label>
                  <Form.Control value={form.gst_number} onChange={(e) => setForm({ ...form, gst_number: e.target.value })} placeholder="22AAAAA0000A1Z5" />
                </Form.Group>
                {form.vendor_type === "pharma_distributor" && (
                  <>
                    <Form.Group className="mb-2">
                      <Form.Label>Drug license number</Form.Label>
                      <Form.Control value={form.drug_license_number} onChange={(e) => setForm({ ...form, drug_license_number: e.target.value })} />
                    </Form.Group>
                    <Form.Group className="mb-2">
                      <Form.Label>Drug license expiry</Form.Label>
                      <Form.Control type="date" value={form.drug_license_expiry} onChange={(e) => setForm({ ...form, drug_license_expiry: e.target.value })} />
                    </Form.Group>
                  </>
                )}
                <Form.Group className="mb-2">
                  <Form.Label>FDA / CDSCO registration ID</Form.Label>
                  <Form.Control value={form.fda_cdsco_registration_id} onChange={(e) => setForm({ ...form, fda_cdsco_registration_id: e.target.value })} placeholder="CDSCO-12345" />
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Contact email</Form.Label>
                  <Form.Control type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
                    placeholder="orders@vendor.co.in" />
                  <Form.Text className="text-muted">A business domain — personal providers route to review.</Form.Text>
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label>Contact phone</Form.Label>
                  <Form.Control value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
                    placeholder="+91 9876543210" />
                </Form.Group>

                <hr className="my-3" />
                <div className="fw-semibold small mb-2">Registered business address</div>
                <Form.Group className="mb-2">
                  <Form.Label className="small">Address line 1</Form.Label>
                  <Form.Control value={form.address_line1} onChange={(e) => setForm({ ...form, address_line1: e.target.value })} />
                </Form.Group>
                <Form.Group className="mb-2">
                  <Form.Label className="small">Address line 2 (optional)</Form.Label>
                  <Form.Control value={form.address_line2} onChange={(e) => setForm({ ...form, address_line2: e.target.value })} />
                </Form.Group>
                <Row>
                  <Col sm={6}>
                    <Form.Group className="mb-2">
                      <Form.Label className="small">City</Form.Label>
                      <Form.Control value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
                    </Form.Group>
                  </Col>
                  <Col sm={6}>
                    <Form.Group className="mb-2">
                      <Form.Label className="small">State</Form.Label>
                      <Form.Control value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} />
                    </Form.Group>
                  </Col>
                </Row>
                <Row>
                  <Col sm={6}>
                    <Form.Group className="mb-2">
                      <Form.Label className="small">PIN code</Form.Label>
                      <Form.Control value={form.postal_code} onChange={(e) => setForm({ ...form, postal_code: e.target.value })}
                        placeholder="400001" />
                    </Form.Group>
                  </Col>
                  <Col sm={6}>
                    <Form.Group className="mb-2">
                      <Form.Label className="small">Country</Form.Label>
                      <Form.Control value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} />
                    </Form.Group>
                  </Col>
                </Row>
                <Button type="submit" className="mt-2">Submit for onboarding</Button>
              </Form>
              </div>
              {result && (
                <div className="mt-3">
                  <Badge bg={statusVariant[result.status]}>{result.status}</Badge>
                  {result.review_reason && <div className="text-muted small mt-1">{result.review_reason}</div>}
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>

        <Col lg={7}>
          <div className="d-flex justify-content-between align-items-center mb-2">
            <h5 className="mb-0">Vendor master</h5>
          </div>
          <FilterBar
            search={search} onSearch={setSearch}
            searchPlaceholder="Search name, city, GSTIN, email…"
            selects={[
              { key: "type", label: "Type", value: typeFilter, onChange: setTypeFilter,
                options: ["pharma_distributor", "equipment_supplier", "amc_contractor", "consumables_supplier"] },
              { key: "status", label: "Status", value: statusFilter, onChange: setStatusFilter,
                options: ["approved", "pending_review", "rejected", "suspended"] },
              { key: "risk", label: "Risk", value: riskFilter, onChange: setRiskFilter,
                options: [{ value: "low", label: "low" }, { value: "medium", label: "medium" },
                          { value: "high", label: "high" }, { value: "none", label: "not assessed" }] },
            ]}
            showing={filteredVendors.length} total={vendors.length}
            onClear={clearFilters}
          />
          <div className="ms-table-card ms-scroll-pane" style={{ maxHeight: 560 }}>
            <Table hover size="sm" responsive>
              <thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Risk</th><th></th></tr></thead>
              <tbody>
                {filteredVendors.map((v) => (
                  <tr key={v.id}>
                    <td>
                      <div style={{ fontWeight: 550 }}>{v.legal_name}</div>
                      {(v.city || v.state) && (
                        <div className="text-muted" style={{ fontSize: "0.75rem" }}>
                          {[v.city, v.state].filter(Boolean).join(", ")}
                        </div>
                      )}
                    </td>
                    <td className="text-muted" style={{ fontSize: "0.8rem" }}>
                      {v.vendor_type.replace(/_/g, " ")}
                    </td>
                    <td>
                      <Badge bg={statusVariant[v.status]}>{v.status.replace(/_/g, " ")}</Badge>
                      {v.status === "pending_review" && (
                        <div className="mt-1"><Badge bg="danger">KYC hold</Badge></div>
                      )}
                      {v.gstin_valid === false || (v.gstin_valid == null && !gstinFormat.test((v.gst_number || "").trim().toUpperCase())) ? (
                        <div className="mt-1"><Badge bg="warning" text="dark">GSTIN needs review</Badge></div>
                      ) : null}
                      {v.review_reason && (
                        <div className="text-muted mt-1" style={{ fontSize: "0.75rem", maxWidth: 280, overflowWrap: "anywhere" }}>
                          {v.review_reason}
                        </div>
                      )}
                    </td>
                    <td>
                      {v.risk_band
                        ? <Badge bg={riskVariant[v.risk_band]}>{v.risk_band}</Badge>
                        : <span className="text-muted">n/a</span>}
                      {v.status === "pending_review" && (
                        <div className="text-danger fw-semibold mt-1" style={{ fontSize: "0.7rem" }}>KYC hold overrides clearance</div>
                      )}
                    </td>
                    <td className="text-end">
                      {/* The risk badge on its own says low/medium/high and nothing else.
                          This pulls the model's own SHAP attribution for that band. */}
                      <Button
                        size="sm" variant="outline-dark"
                        onClick={() => openShap(v.id)}
                      >
                        Why?
                      </Button>
                    </td>
                  </tr>
                ))}
                {filteredVendors.length === 0 && (
                  <tr><td colSpan={5} className="text-muted">
                    {vendors.length === 0 ? "No vendors yet." : "No vendors match these filters."}
                  </td></tr>
                )}
              </tbody>
            </Table>
          </div>
        </Col>
      </Row>

      <ShapModal shap={shap} onClose={() => setShap((s) => ({ ...s, open: false }))} />
    </div>
  );
}
