import React from "react";
import { Alert, Badge, Button, Card, Container } from "react-bootstrap";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function AccessDenied({ requiredRoles = [] }) {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const roleLabels = requiredRoles
    .map((r) => r.replace("_", " ").toUpperCase())
    .join(", ");

  return (
    <Container className="py-5" style={{ maxWidth: "680px" }}>
      <Card className="shadow-lg border-0 rounded-4 overflow-hidden text-center p-4">
        <Card.Body>
          <div className="mb-3">
            <span
              className="d-inline-flex align-items-center justify-content-center bg-danger-subtle text-danger rounded-circle p-3"
              style={{ width: "70px", height: "70px" }}
            >
              <svg width="36" height="36" fill="currentColor" viewBox="0 0 16 16">
                <path d="M8 1a2 2 0 0 1 2 2v2H6V3a2 2 0 0 1 2-2zm3 4V3a3 3 0 0 0-6 0v2a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zM5 8h6v5H5V8z" />
              </svg>
            </span>
          </div>

          <h2 className="fw-bold mb-2">Access Restricted</h2>
          <p className="text-muted mb-4">
            Your current designation <Badge bg={currentUser?.badgeVariant || "secondary"} className="px-2 py-1 fs-6">{currentUser?.roleLabel}</Badge> does not have authorization to access this module.
          </p>

          {requiredRoles.length > 0 && (
            <Alert variant="warning" className="text-start mb-4 py-2 px-3 small">
              <strong>Required Designation / Role:</strong> {roleLabels}
            </Alert>
          )}

          <div className="d-flex flex-wrap justify-content-center gap-3">
            <Button variant="primary" className="px-4" onClick={() => navigate("/")}>
              Return to Overview
            </Button>
            <Button
              variant="outline-secondary"
              className="px-4"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              Switch Designation
            </Button>
          </div>
        </Card.Body>
      </Card>
    </Container>
  );
}
