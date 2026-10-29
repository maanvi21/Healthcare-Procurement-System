import React from "react";
import { Badge, Button, Container, Nav, Navbar, NavDropdown } from "react-bootstrap";
import { Link, NavLink, useNavigate } from "react-router-dom";
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
  { to: "/kafka-logs", label: "Kafka Logs" },
  { to: "/storage", label: "Storage" },
];

export default function NavBar() {
  const { currentUser, isAuthenticated, logout, checkPermission } = useAuth();
  const navigate = useNavigate();

  const handleSwitchDesignation = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="ms-nav-sticky">
      <Container fluid="lg">
      <Navbar expand="xxl" className="ms-nav py-2">
        <Container fluid className="px-1">
          <Navbar.Brand as={Link} to="/" className="fw-bold fs-5 me-3 text-white text-decoration-none">
            ◆ MediSource AI
          </Navbar.Brand>
          <Navbar.Toggle aria-controls="main-nav" />
          <Navbar.Collapse id="main-nav">
            {isAuthenticated ? (
              <>
                <Nav className="me-auto gap-1">
                  {links.map((link) => {
                    const hasAccess = checkPermission(link.to);
                    return (
                      <Nav.Link
                        key={link.to}
                        as={NavLink}
                        to={link.to}
                        end={link.end}
                        className={({ isActive }) =>
                          `${isActive ? "active fw-semibold" : ""} ${!hasAccess ? "opacity-75" : ""}`
                        }
                      >
                        {link.label}
                        {!hasAccess && (
                          <span className="ms-1 small opacity-50" title="Restricted for current designation" aria-label="Restricted">·</span>
                        )}
                      </Nav.Link>
                    );
                  })}
                </Nav>

                <div className="ms-account-menu ms-auto">
                  <div className="ms-user-pill" title={`${currentUser.name} · ${currentUser.roleLabel}`}>
                    <Badge bg={currentUser.badgeVariant} className="px-2 py-1 text-uppercase rounded-circle">
                      {currentUser.initials}
                    </Badge>
                    <div className="ms-user-copy text-start lh-1">
                      <div className="fw-bold small text-dark text-truncate">{currentUser.name}</div>
                      <div className="text-muted text-truncate ms-user-role">
                        {currentUser.roleLabel}
                      </div>
                    </div>
                  </div>
                  <NavDropdown title="Account" id="user-dropdown" align="end">
                    <NavDropdown.Header>
                      <div className="fw-bold">{currentUser.name}</div>
                      <div className="small text-muted">{currentUser.roleLabel}</div>
                      <div className="small text-secondary">{currentUser.department}</div>
                    </NavDropdown.Header>
                    <NavDropdown.Divider />
                    <NavDropdown.Item onClick={handleSwitchDesignation}>Switch designation</NavDropdown.Item>
                    <NavDropdown.Item onClick={handleSwitchDesignation} className="text-danger">Sign out</NavDropdown.Item>
                  </NavDropdown>
                </div>
              </>
            ) : (
              <div className="ms-auto">
                <Button
                  as={Link}
                  to="/login"
                  variant="success"
                  size="sm"
                  className="rounded-pill fw-semibold px-3"
                >
                  Sign In / Select Designation
                </Button>
              </div>
            )}
          </Navbar.Collapse>
        </Container>
      </Navbar>
      </Container>
    </div>
  );
}
