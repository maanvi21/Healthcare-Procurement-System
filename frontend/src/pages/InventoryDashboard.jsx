import React, { useEffect, useState } from "react";
import { Badge, Button, Card, Col, Form, Row, Table } from "react-bootstrap";
import { inventoryApi } from "../api/client.js";

export default function InventoryDashboard() {
  const [items, setItems] = useState([]);
  const [backorders, setBackorders] = useState([]);
  const [itemForm, setItemForm] = useState({ sku: "", name: "", category: "drug", unit: "unit", cold_chain: false, reorder_point: 10, reorder_qty: 50 });
  const [batchForm, setBatchForm] = useState({ stock_item_id: "", batch_no: "", expiry_date: "", quantity_on_hand: "" });

  const loadItems = () => inventoryApi.get("/stock-items").then((res) => setItems(res.data)).catch(() => {});
  const loadBackorders = () => inventoryApi.get("/backorders").then((res) => setBackorders(res.data)).catch(() => {});

  useEffect(() => { loadItems(); loadBackorders(); }, []);

  const createItem = async (e) => {
    e.preventDefault();
    await inventoryApi.post("/stock-items", itemForm);
    setItemForm({ sku: "", name: "", category: "drug", unit: "unit", cold_chain: false, reorder_point: 10, reorder_qty: 50 });
    loadItems();
  };

  const addBatch = async (e) => {
    e.preventDefault();
    if (!batchForm.stock_item_id) return;
    await inventoryApi.post(`/stock-items/${batchForm.stock_item_id}/batches`, {
      batch_no: batchForm.batch_no,
      expiry_date: batchForm.expiry_date || null,
      quantity_on_hand: parseInt(batchForm.quantity_on_hand, 10),
    });
    setBatchForm({ stock_item_id: "", batch_no: "", expiry_date: "", quantity_on_hand: "" });
    loadItems();
  };

  return (
    <div>
      <h2>Inventory Intelligence</h2>
      <p className="text-muted">
        Ward/pharmacy stock with expiry- and cold-chain-aware reservation. Reservations are
        auto-created when a procurement request is submitted (see Approvals page).
      </p>

      <Row className="g-4">
        <Col md={5}>
          <Card className="mb-4">
            <Card.Body>
              <Card.Title>Add stock item</Card.Title>
              <Form onSubmit={createItem}>
                <Form.Group className="mb-2"><Form.Label>SKU</Form.Label>
                  <Form.Control required value={itemForm.sku} onChange={(e) => setItemForm({ ...itemForm, sku: e.target.value })} /></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Name</Form.Label>
                  <Form.Control required value={itemForm.name} onChange={(e) => setItemForm({ ...itemForm, name: e.target.value })} /></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Category</Form.Label>
                  <Form.Select value={itemForm.category} onChange={(e) => setItemForm({ ...itemForm, category: e.target.value })}>
                    <option value="drug">Drug</option>
                    <option value="consumable">Consumable</option>
                    <option value="ppe">PPE</option>
                    <option value="implant">Implant</option>
                    <option value="equipment">Equipment</option>
                  </Form.Select></Form.Group>
                <Form.Check className="mb-2" label="Cold-chain item" checked={itemForm.cold_chain}
                  onChange={(e) => setItemForm({ ...itemForm, cold_chain: e.target.checked })} />
                <Button type="submit">Add item</Button>
              </Form>
            </Card.Body>
          </Card>

          <Card>
            <Card.Body>
              <Card.Title>Add batch</Card.Title>
              <Form onSubmit={addBatch}>
                <Form.Group className="mb-2"><Form.Label>Stock item</Form.Label>
                  <Form.Select value={batchForm.stock_item_id} onChange={(e) => setBatchForm({ ...batchForm, stock_item_id: e.target.value })}>
                    <option value="">Select…</option>
                    {items.map((i) => <option key={i.id} value={i.id}>{i.sku} — {i.name}</option>)}
                  </Form.Select></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Batch no.</Form.Label>
                  <Form.Control required value={batchForm.batch_no} onChange={(e) => setBatchForm({ ...batchForm, batch_no: e.target.value })} /></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Expiry date</Form.Label>
                  <Form.Control type="date" value={batchForm.expiry_date} onChange={(e) => setBatchForm({ ...batchForm, expiry_date: e.target.value })} /></Form.Group>
                <Form.Group className="mb-2"><Form.Label>Quantity on hand</Form.Label>
                  <Form.Control type="number" required value={batchForm.quantity_on_hand} onChange={(e) => setBatchForm({ ...batchForm, quantity_on_hand: e.target.value })} /></Form.Group>
                <Button type="submit">Add batch</Button>
              </Form>
            </Card.Body>
          </Card>
        </Col>

        <Col md={7}>
          <h5>Stock items</h5>
          <Table hover size="sm">
            <thead><tr><th>SKU</th><th>Name</th><th>Category</th><th>Cold-chain</th></tr></thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id}>
                  <td>{i.sku}</td><td>{i.name}</td><td>{i.category}</td>
                  <td>{i.cold_chain ? <Badge bg="info">yes</Badge> : "no"}</td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={4} className="text-muted">No stock items yet.</td></tr>}
            </tbody>
          </Table>

          <h5 className="mt-4">Backorders</h5>
          <Table hover size="sm">
            <thead><tr><th>Stock item</th><th>Short by</th><th>Suggested reorder qty</th></tr></thead>
            <tbody>
              {backorders.map((b) => (
                <tr key={b.id}><td>{b.stock_item_id}</td><td>{b.quantity_short}</td><td>{b.suggested_reorder_qty}</td></tr>
              ))}
              {backorders.length === 0 && <tr><td colSpan={3} className="text-muted">No backorders.</td></tr>}
            </tbody>
          </Table>
        </Col>
      </Row>
    </div>
  );
}
