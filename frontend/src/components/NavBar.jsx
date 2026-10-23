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
    <Container fluid="lg">
      <Navbar expand="lg" className="ms-nav py-2">
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
                          <span className="ms-1 small opacity-50" title="Restricted for current designation">
                            🔒
                          </span>
                        )}
                      </Nav.Link>
                    );
                  })}
                </Nav>

                <div className="d-flex align-items-center gap-2 ms-auto">
                  <Button
                    variant="outline-light"
                    size="sm"
                    className="rounded-pill px-3 me-1 fw-semibold"
                    style={{ fontSize: "0.8rem", borderColor: "rgba(255,255,255,0.25)" }}
                    onClick={handleSwitchDesignation}
                  >
                    🔄 Switch Designation
                  </Button>

                  <div className="bg-light rounded-pill px-2 py-1 border d-flex align-items-center gap-2">
                    <Badge bg={currentUser.badgeVariant} className="px-2 py-1 text-uppercase rounded-circle">
                      {currentUser.initials}
                    </Badge>
                    <div className="d-none d-sm-block text-start lh-1 me-1">
                      <div className="fw-bold small text-dark">{currentUser.name}</div>
                      <div className="text-muted" style={{ fontSize: "0.72rem" }}>
                        {currentUser.roleLabel}
                      </div>
                    </div>

                    <NavDropdown
                      title=""
                      id="user-dropdown"
                      align="end"
                      className="border-0 shadow-none p-0"
                    >
                      <NavDropdown.Header>
                        <div className="fw-bold">{currentUser.name}</div>
                        <div className="small text-muted">{currentUser.roleLabel}</div>
                        <div className="small text-secondary">{currentUser.department}</div>
                      </NavDropdown.Header>
                      <NavDropdown.Divider />
                      <NavDropdown.Item onClick={handleSwitchDesignation}>
                        🔄 Switch Designation
                      </NavDropdown.Item>
                      <NavDropdown.Item onClick={handleSwitchDesignation} className="text-danger">
                        🚪 Sign Out
                      </NavDropdown.Item>
                    </NavDropdown>
                  </div>
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
  );
}
