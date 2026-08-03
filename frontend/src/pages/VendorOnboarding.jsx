import React, { useEffect, useState } from "react";
import { Badge, Button, Card, Col, Form, Row, Table } from "react-bootstrap";
import { vendorsApi } from "../api/client.js";

const statusVariant = { pending_review: "warning", approved: "success", rejected: "danger", suspended: "secondary" };
const riskVariant = { low: "success", medium: "warning", high: "danger" };

const emptyForm = {
  legal_name: "", vendor_type: "pharma_distributor", gst_number: "", drug_license_number: "",
  drug_license_expiry: "", fda_cdsco_registration_id: "", contact_email: "", contact_phone: "",
};

export default function VendorOnboarding() {
  const [vendors, setVendors] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [result, setResult] = useState(null);

  const loadVendors = () => vendorsApi.get("").then((res) => setVendors(res.data)).catch(() => {});
  useEffect(loadVendors, []);

  const submit = async (e) => {
    e.preventDefault();
    const payload = { ...form };
    if (!payload.drug_license_expiry) delete payload.drug_license_expiry;
    if (!payload.drug_license_number) delete payload.drug_license_number;
    if (!payload.fda_cdsco_registration_id) delete payload.fda_cdsco_registration_id;
    if (!payload.gst_number) delete payload.gst_number;
    const res = await vendorsApi.post("", payload);
    setResult(res.data);
    setForm(emptyForm);
    loadVendors();
  };

  return (
    <div>
      <h2>Vendor Intelligence</h2>
      <p className="text-muted">
        Onboard medical suppliers, pharma distributors and biomedical AMC contractors with
        healthcare-specific KYC: drug-license validity, FDA/CDSCO registration, GSTIN, and
        sanctions/watchlist screening.
      </p>

      <Row className="g-4">
        <Col md={5}>
          <Card>
            <Card.Body>
              <Card.Title>Onboard a vendor</Card.Title>
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
                  <Form.Control type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} />
                </Form.Group>
                <Button type="submit" className="mt-2">Submit for onboarding</Button>
              </Form>
              {result && (
                <div className="mt-3">
                  <Badge bg={statusVariant[result.status]}>{result.status}</Badge>
                  {result.review_reason && <div className="text-muted small mt-1">{result.review_reason}</div>}
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>

        <Col md={7}>
          <h5>Vendor master</h5>
          <Table hover size="sm">
            <thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Risk</th></tr></thead>
            <tbody>
              {vendors.map((v) => (
                <tr key={v.id}>
                  <td>{v.legal_name}</td>
                  <td>{v.vendor_type}</td>
                  <td><Badge bg={statusVariant[v.status]}>{v.status}</Badge></td>
                  <td>{v.risk_band ? <Badge bg={riskVariant[v.risk_band]}>{v.risk_band}</Badge> : <span className="text-muted">n/a</span>}</td>
                </tr>
              ))}
              {vendors.length === 0 && <tr><td colSpan={4} className="text-muted">No vendors yet.</td></tr>}
            </tbody>
          </Table>
        </Col>
      </Row>
    </div>
  );
}
