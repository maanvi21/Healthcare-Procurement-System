import React, { useMemo, useState } from "react";
import { Badge, Col, Row } from "react-bootstrap";
import { documentsApi } from "../api/client.js";
import { useLiveData } from "../api/useLiveData.js";
import ConnectionAlert from "../components/ConnectionAlert.jsx";
import FilterBar from "../components/FilterBar.jsx";

const bucketIcons = {
  documents: "📄",
  contracts: "📝",
  reports: "📊",
};

const formatSize = (bytes) => {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};

export default function StorageDashboard() {
  const [storageData, setStorageData] = useState({ buckets: [] });
  const [selectedBucket, setSelectedBucket] = useState(null);
  const [search, setSearch] = useState("");

  const loadStorage = async () => {
    const res = await documentsApi.get("/storage/buckets");
    setStorageData(res.data);
  };
  const { error: connectionError, refresh: reloadStorage } = useLiveData(loadStorage, { intervalMs: 5000 });

  const buckets = storageData.buckets || [];
  const totalObjects = buckets.reduce((sum, b) => sum + (b.object_count || 0), 0);
  const totalSize = buckets.reduce(
    (sum, b) => sum + (b.objects || []).reduce((s, o) => s + (o.size || 0), 0),
    0
  );

  const selectedBucketData = buckets.find((b) => b.name === selectedBucket);
  const objects = selectedBucketData?.objects || [];

  const filteredObjects = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return objects;
    return objects.filter((o) =>
      [o.name, o.content_type].filter(Boolean).some((v) => v.toLowerCase().includes(q))
    );
  }, [objects, search]);

  const clearFilters = () => setSearch("");

  return (
    <div>
      <h1 className="ms-page-title">Object Storage (MinIO)</h1>
      <p className="ms-page-sub">
        Browse all MinIO buckets and objects. Original documents are stored in the
        <code> documents</code> bucket, signed contracts in <code>contracts</code>. Every
        file uploaded, generated, or signed by the platform is stored here.
      </p>

      <ConnectionAlert error={connectionError} onRetry={reloadStorage} />

      {/* ── Summary Tiles ──────────────────────────────────── */}
      <Row className="g-3 mb-4" xs={2} md={4}>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Buckets</div>
            <div className="ms-stat-value">{buckets.length}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Total Objects</div>
            <div className="ms-stat-value">{totalObjects}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Total Size</div>
            <div className="ms-stat-value" style={{ fontSize: "1.1rem" }}>{formatSize(totalSize)}</div>
          </div>
        </Col>
        <Col>
          <div className="ms-stat">
            <div className="ms-stat-label">Contracts Bucket</div>
            <div className="ms-stat-value" style={{ color: "#2ecc71" }}>
              {(buckets.find((b) => b.name === "contracts")?.object_count) || 0}
            </div>
            <div className="ms-tile-sub">signed contracts</div>
          </div>
        </Col>
      </Row>

      {/* ── Bucket List + Object Browser ────────────────────── */}
      <div className="ms-split">
        <Row className="g-3">
          <Col lg={4}>
            <div className="d-flex justify-content-between align-items-center px-2 mb-2">
              <h6 className="mb-0 text-white">Buckets</h6>
              <span className="ms-chip" style={{ background: "rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.72)" }}>
                {buckets.length}
              </span>
            </div>
            <div className="ms-list">
              {buckets.map((bucket) => {
                const isSel = selectedBucket === bucket.name;
                const icon = bucketIcons[bucket.name] || "🗂️";
                const size = (bucket.objects || []).reduce((s, o) => s + (o.size || 0), 0);
                return (
                  <button
                    key={bucket.name}
                    type="button"
                    className={`ms-list-row ${isSel ? "selected" : ""}`}
                    onClick={() => setSelectedBucket(bucket.name)}
                  >
                    <span className="ms-list-avatar" style={{ fontSize: "1.2rem" }}>
                      {icon}
                    </span>
                    <span className="flex-grow-1" style={{ minWidth: 0 }}>
                      <span className="d-block text-truncate" style={{ fontSize: "0.88rem", fontWeight: 600 }}>
                        {bucket.name}
                      </span>
                      <span className="d-block" style={{ fontSize: "0.72rem", opacity: 0.7 }}>
                        {bucket.object_count} objects · {formatSize(size)}
                        {bucket.created && ` · created ${new Date(bucket.created).toLocaleDateString()}`}
                      </span>
                    </span>
                    <span className="d-flex flex-column align-items-end gap-1 flex-shrink-0">
                      <Badge bg={bucket.object_count > 0 ? "success" : "secondary"}>
                        {bucket.object_count}
                      </Badge>
                    </span>
                  </button>
                );
              })}
              {buckets.length === 0 && (
                <div className="px-2 py-3" style={{ color: "rgba(255,255,255,0.55)", fontSize: "0.85rem" }}>
                  No buckets found. Is MinIO running?
                </div>
              )}
            </div>
          </Col>

          <Col lg={8}>
            {!selectedBucket ? (
              <div className="ms-detail d-flex align-items-center justify-content-center">
                <span style={{ opacity: 0.65 }}>Select a bucket to browse its objects.</span>
              </div>
            ) : (
              <div className="ms-detail">
                <div className="d-flex justify-content-between align-items-center mb-3 flex-shrink-0">
                  <div>
                    <h5 className="mb-0 text-white">
                      {bucketIcons[selectedBucket] || "🗂️"} {selectedBucket}
                    </h5>
                    <span className="text-white-50" style={{ fontSize: "0.75rem" }}>
                      {objects.length} objects ·{" "}
                      {formatSize(objects.reduce((s, o) => s + (o.size || 0), 0))}
                    </span>
                  </div>
                  <Badge bg={objects.length > 0 ? "success" : "secondary"} style={{ fontSize: "0.8rem" }}>
                    {objects.length} files
                  </Badge>
                </div>

                <FilterBar
                  search={search}
                  onSearch={setSearch}
                  searchPlaceholder="Search object name, type…"
                  selects={[]}
                  showing={filteredObjects.length}
                  total={objects.length}
                  onClear={clearFilters}
                />

                <div className="ms-detail-scroll">
                  {filteredObjects.length === 0 ? (
                    <div className="text-center py-4" style={{ opacity: 0.6, fontSize: "0.85rem" }}>
                      {objects.length === 0 ? "This bucket is empty." : "No objects match your search."}
                    </div>
                  ) : (
                    <div className="ms-list">
                      {filteredObjects.map((obj, idx) => {
                        const fileName = obj.name.split("/").pop() || obj.name;
                        const folder = obj.name.includes("/")
                          ? obj.name.substring(0, obj.name.lastIndexOf("/"))
                          : null;
                        const isContract = selectedBucket === "contracts" || obj.name.includes("contract") || obj.name.includes("signed");
                        const isPdf = fileName.endsWith(".pdf") || fileName.endsWith(".html");

                        return (
                          <div
                            key={idx}
                            className="ms-kafka-event-row"
                            style={{
                              borderLeft: isContract ? "3px solid #2ecc71" : "3px solid rgba(255,255,255,0.1)",
                            }}
                          >
                            <div className="d-flex align-items-start gap-2 flex-grow-1" style={{ minWidth: 0 }}>
                              <span style={{ fontSize: "1.1rem" }}>
                                {isPdf ? "📄" : isContract ? "📝" : "📁"}
                              </span>
                              <div style={{ minWidth: 0 }}>
                                <div className="text-white fw-semibold text-truncate" style={{ fontSize: "0.82rem" }}>
                                  {fileName}
                                </div>
                                {folder && (
                                  <div className="text-white-50" style={{ fontSize: "0.68rem" }}>
                                    {folder}
                                  </div>
                                )}
                                <div className="d-flex gap-2 mt-1 flex-wrap">
                                  <span className="text-white-50" style={{ fontSize: "0.68rem" }}>
                                    {formatSize(obj.size)}
                                  </span>
                                  {obj.content_type && (
                                    <Badge bg="dark" style={{ fontSize: "0.62rem", border: "1px solid rgba(255,255,255,0.15)" }}>
                                      {obj.content_type}
                                    </Badge>
                                  )}
                                  {isContract && (
                                    <Badge bg="success" style={{ fontSize: "0.62rem" }}>
                                      Contract
                                    </Badge>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="text-end flex-shrink-0">
                              {obj.last_modified && (
                                <div className="text-white-50" style={{ fontSize: "0.68rem" }}>
                                  {new Date(obj.last_modified).toLocaleDateString()}
                                  <br />
                                  {new Date(obj.last_modified).toLocaleTimeString()}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}
          </Col>
        </Row>
      </div>
    </div>
  );
}
