import React, { useMemo, useState } from "react";
import { Badge, Button, Card, Col, Form, Row, Table } from "react-bootstrap";
import { inventoryApi } from "../api/client.js";
import { useLiveData } from "../api/useLiveData.js";
import ConnectionAlert from "../components/ConnectionAlert.jsx";
import FilterBar from "../components/FilterBar.jsx";

export default function InventoryDashboard() {
  const [items, setItems] = useState([]);
  const [backorders, setBackorders] = useState([]);
  const [itemForm, setItemForm] = useState({ sku: "", name: "", category: "drug", unit: "unit", cold_chain: false, reorder_point: 10, reorder_qty: 50 });
  const [batchForm, setBatchForm] = useState({ stock_item_id: "", batch_no: "", expiry_date: "", quantity_on_hand: "" });
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [coldFilter, setColdFilter] = useState("all");

  const loadItems = () => inventoryApi.get("/stock-items").then((res) => setItems(res.data));
  const loadBackorders = () => inventoryApi.get("/backorders").then((res) => setBackorders(res.data));

  const { error: connectionError, refresh: reloadAll } = useLiveData(() =>
    Promise.all([loadItems(), loadBackorders()])
  );

  const createItem = async (e) => {
    e.preventDefault();
    await inventoryApi.post("/stock-items", itemForm);
    setItemForm({ sku: "", name: "", category: "drug", unit: "unit", cold_chain: false, reorder_point: 10, reorder_qty: 50 });
    reloadAll();
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
    reloadAll();
  };

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((i) => {
      if (categoryFilter !== "all" && i.category !== categoryFilter) return false;
      if (coldFilter === "yes" && !i.cold_chain) return false;
      if (coldFilter === "no" && i.cold_chain) return false;
      if (!q) return true;
      return [i.sku, i.name, i.category].filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q));
    });
  }, [items, search, categoryFilter, coldFilter]);

  const coldChainCount = items.filter((i) => i.cold_chain).length;

  const clearFilters = () => { setSearch(""); setCategoryFilter("all"); setColdFilter("all"); };

  return (
    <div>
      <h1 className="ms-page-title">Inventory Intelligence</h1>
      <ConnectionAlert error={connectionError} onRetry={reloadAll} />
      <p className="ms-page-sub">
        Ward/pharmacy stock with expiry- and cold-chain-aware reservation. Reservations are
        auto-created when a procurement request is submitted (see Approvals page).
      </p>

      <Row className="g-3 mb-3" xs={2} md={4}>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Stock items</div>
            <div className="ms-stat-value">{items.length}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Cold-chain</div>
            <div className="ms-stat-value">{coldChainCount}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Backorders</div>
            <div className="ms-stat-value" style={{ color: backorders.length ? "#c53434" : undefined }}>
              {backorders.length}
            </div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Categories</div>
            <div className="ms-stat-value">{new Set(items.map((i) => i.category)).size}</div>
          </div>
        </Col>
      </Row>

      <Row className="g-4">
        <Col lg={5}>
          <Card className="mb-4">
            <Card.Body>
              <Card.Title>Add stock item</Card.Title>
              <div className="ms-scroll-pane" style={{ maxHeight: 300 }}>
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
              </div>
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

        <Col lg={7}>
          <h5>Stock items</h5>
          <FilterBar
            search={search} onSearch={setSearch}
            searchPlaceholder="Search SKU or name…"
            selects={[
              { key: "category", label: "Category", value: categoryFilter, onChange: setCategoryFilter,
                options: ["drug", "consumable", "ppe", "implant", "equipment"] },
              { key: "cold", label: "Cold-chain", value: coldFilter, onChange: setColdFilter,
                options: [{ value: "yes", label: "cold-chain only" }, { value: "no", label: "ambient only" }] },
            ]}
            showing={filteredItems.length} total={items.length}
            onClear={clearFilters}
          />
          <div className="ms-table-card ms-scroll-pane" style={{ maxHeight: 380 }}>
          <Table hover size="sm" responsive>
            <thead><tr><th>SKU</th><th>Name</th><th>Category</th><th>Cold-chain</th></tr></thead>
            <tbody>
              {filteredItems.map((i) => (
                <tr key={i.id}>
                  <td>{i.sku}</td><td>{i.name}</td><td>{i.category}</td>
                  <td>{i.cold_chain ? <Badge bg="info">yes</Badge> : "no"}</td>
                </tr>
              ))}
              {filteredItems.length === 0 && (
                <tr><td colSpan={4} className="text-muted">
                  {items.length === 0 ? "No stock items yet." : "No items match these filters."}
                </td></tr>
              )}
            </tbody>
          </Table>
          </div>

          <h5 className="mt-4">Backorders</h5>
          <div className="ms-table-card ms-scroll-pane" style={{ maxHeight: 280 }}>
          <Table hover size="sm" responsive>
            <thead><tr><th>Stock item</th><th>Short by</th><th>Suggested reorder qty</th></tr></thead>
            <tbody>
              {backorders.map((b) => (
                <tr key={b.id}><td>{b.stock_item_id}</td><td>{b.quantity_short}</td><td>{b.suggested_reorder_qty}</td></tr>
              ))}
              {backorders.length === 0 && <tr><td colSpan={3} className="text-muted">No backorders.</td></tr>}
            </tbody>
          </Table>
          </div>
        </Col>
      </Row>
    </div>
  );
}
