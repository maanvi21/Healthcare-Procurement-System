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
    <Container fluid="lg">
      <Navbar expand="lg" className="ms-nav">
        <Container fluid className="px-1">
          <Navbar.Brand>◆ MediSource AI</Navbar.Brand>
          <Navbar.Toggle aria-controls="main-nav" />
          <Navbar.Collapse id="main-nav">
            <Nav className="mx-auto gap-1">
              {links.map((link) => (
                <Nav.Link
                  key={link.to}
                  as={NavLink}
                  to={link.to}
                  end={link.end}
                  className={({ isActive }) => (isActive ? "active" : "")}
                >
                  {link.label}
                </Nav.Link>
              ))}
            </Nav>
            <Navbar.Text className="d-none d-xl-block">Hospital Procurement Intelligence</Navbar.Text>
          </Navbar.Collapse>
        </Container>
      </Navbar>
    </Container>
  );
}
