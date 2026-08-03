import React, { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, Form, ListGroup, Spinner, Table } from "react-bootstrap";
import { documentsApi } from "../api/client.js";

const statusVariant = {
  received: "secondary",
  processing: "info",
  extracted: "primary",
  needs_review: "warning",
  validated: "success",
  rejected: "danger",
};

export default function DocumentUpload() {
  const [file, setFile] = useState(null);
  const [source, setSource] = useState("upload");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selected, setSelected] = useState(null);

  const loadDocuments = () => {
    documentsApi.get("").then((res) => setDocuments(res.data)).catch(() => {});
  };

  useEffect(loadDocuments, []);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await documentsApi.post(`/ingest?source=${source}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setSelected(res.data);
      loadDocuments();
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const openDocument = (id) => {
    documentsApi.get(`/${id}`).then((res) => setSelected(res.data));
  };

  const correctField = async (fieldId, value) => {
    if (!selected) return;
    const res = await documentsApi.post(`/${selected.id}/fields/${fieldId}/correct`, { field_value: value });
    setSelected(res.data);
    loadDocuments();
  };

  return (
    <div>
      <h2>Document Intelligence</h2>
      <p className="text-muted">
        Ingest supplier invoices, purchase orders, quotations and compliance certificates.
        OCR + extraction run automatically; low-confidence fields are queued for manual review.
      </p>

      <Card className="mb-4">
        <Card.Body>
          <Form onSubmit={handleUpload} className="d-flex gap-3 align-items-end flex-wrap">
            <Form.Group>
              <Form.Label>Document file (PDF or image)</Form.Label>
              <Form.Control type="file" onChange={(e) => setFile(e.target.files[0])} accept=".pdf,.png,.jpg,.jpeg" />
            </Form.Group>
            <Form.Group>
              <Form.Label>Source</Form.Label>
              <Form.Select value={source} onChange={(e) => setSource(e.target.value)}>
                <option value="upload">Upload</option>
                <option value="email">Email</option>
                <option value="api">API</option>
                <option value="shared_folder">Shared folder</option>
              </Form.Select>
            </Form.Group>
            <Button type="submit" disabled={uploading || !file}>
              {uploading ? <Spinner size="sm" animation="border" /> : "Ingest document"}
            </Button>
          </Form>
          {error && <Alert variant="danger" className="mt-3">{error}</Alert>}
        </Card.Body>
      </Card>

      <div className="row g-4">
        <div className="col-md-6">
          <h5>Recent documents</h5>
          <Table hover size="sm">
            <thead>
              <tr><th>Filename</th><th>Type</th><th>Status</th></tr>
            </thead>
            <tbody>
              {documents.map((d) => (
                <tr key={d.id} onClick={() => openDocument(d.id)} style={{ cursor: "pointer" }}>
                  <td>{d.original_filename}</td>
                  <td>{d.doc_type}</td>
                  <td><Badge bg={statusVariant[d.status] || "secondary"}>{d.status}</Badge></td>
                </tr>
              ))}
              {documents.length === 0 && <tr><td colSpan={3} className="text-muted">No documents yet.</td></tr>}
            </tbody>
          </Table>
        </div>

        <div className="col-md-6">
          <h5>Extracted fields</h5>
          {!selected && <p className="text-muted">Select a document to review its extracted fields.</p>}
          {selected && (
            <>
              <p><strong>{selected.original_filename}</strong> — <Badge bg={statusVariant[selected.status]}>{selected.status}</Badge></p>
              <ListGroup>
                {selected.extracted_fields.map((f) => (
                  <ListGroup.Item key={f.id} className="d-flex justify-content-between align-items-center">
                    <div>
                      <div className="text-muted small">{f.field_name}</div>
                      {f.is_manually_corrected ? (
                        <div>{f.field_value}</div>
                      ) : (
                        <Form.Control
                          size="sm"
                          defaultValue={f.field_value}
                          onBlur={(e) => e.target.value !== f.field_value && correctField(f.id, e.target.value)}
                        />
                      )}
                    </div>
                    <Badge bg={f.confidence < 0.75 ? "warning" : "success"}>{Math.round(f.confidence * 100)}%</Badge>
                  </ListGroup.Item>
                ))}
                {selected.extracted_fields.length === 0 && (
                  <ListGroup.Item className="text-muted">No fields extracted.</ListGroup.Item>
                )}
              </ListGroup>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
