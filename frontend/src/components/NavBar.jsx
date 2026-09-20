import React from "react";
import { Badge, Container, Form, Nav, Navbar } from "react-bootstrap";
import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

const links = [
  { to: "/", label: "Overview", end: true },
  { to: "/documents", label: "Documents" },
  { to: "/vendors", label: "Vendors" },
  { to: "/approvals", label: "Approvals" },
  { to: "/inventory", label: "Inventory" },
  { to: "/contracts", label: "Contracts" },
  { to: "/risk", label: "Risk" },
  { to: "/notifications", label: "Notifications" },
];

export default function NavBar() {
  const { currentUser, switchUser, mockUsers } = useAuth();

  return (
    <Container fluid="lg">
      <Navbar expand="lg" className="ms-nav py-2">
        <Container fluid className="px-1">
          <Navbar.Brand className="fw-bold fs-5 me-3">◆ MediSource AI</Navbar.Brand>
          <Navbar.Toggle aria-controls="main-nav" />
          <Navbar.Collapse id="main-nav">
            <Nav className="me-auto gap-1">
              {links.map((link) => (
                <Nav.Link
                  key={link.to}
                  as={NavLink}
                  to={link.to}
                  end={link.end}
                  className={({ isActive }) => (isActive ? "active fw-semibold" : "")}
                >
                  {link.label}
                </Nav.Link>
              ))}
            </Nav>
            <div className="d-flex align-items-center gap-2 ms-auto bg-light rounded p-1 border">
              <Badge bg={currentUser.badgeVariant} className="px-2 py-1 text-uppercase">
                {currentUser.initials}
              </Badge>
              <div className="d-none d-sm-block text-start lh-1 me-1">
                <div className="fw-bold small">{currentUser.name}</div>
                <div className="text-muted" style={{ fontSize: "0.72rem" }}>
                  {currentUser.roleLabel}
                </div>
              </div>
              <Form.Select
                size="sm"
                className="border-0 bg-transparent fw-semibold text-dark shadow-none"
                style={{ width: "auto", cursor: "pointer" }}
                value={currentUser.id}
                onChange={(e) => switchUser(e.target.value)}
                aria-label="Switch User Role"
              >
                {mockUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} — {u.roleLabel} ({u.department})
                  </option>
                ))}
              </Form.Select>
            </div>
          </Navbar.Collapse>
        </Container>
      </Navbar>
    </Container>
  );
}
