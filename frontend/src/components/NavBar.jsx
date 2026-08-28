import React from "react";
import { Container, Nav, Navbar } from "react-bootstrap";
import { NavLink } from "react-router-dom";

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
  return (
    <Navbar bg="dark" variant="dark" expand="lg" className="mb-4">
      <Container fluid>
        <Navbar.Brand>MediSource AI</Navbar.Brand>
        <Navbar.Toggle aria-controls="main-nav" />
        <Navbar.Collapse id="main-nav">
          <Nav className="me-auto">
            {links.map((link) => (
              <Nav.Link
                key={link.to}
                as={NavLink}
                to={link.to}
                end={link.end}
                className={({ isActive }) => (isActive ? "active fw-bold" : "")}
              >
                {link.label}
              </Nav.Link>
            ))}
          </Nav>
          <Navbar.Text>Hospital Procurement Intelligence Platform</Navbar.Text>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
}
