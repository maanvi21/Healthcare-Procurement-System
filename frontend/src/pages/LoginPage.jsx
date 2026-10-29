import React, { useState } from "react";
import { Alert, Badge, Button, Card, Col, Container, Form, Modal, Nav, Row } from "react-bootstrap";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function LoginPage() {
  const { users, login, isAuthenticated, currentUser, logout, addUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [selectedUser, setSelectedUser] = useState(users[0]);
  const [identifier, setIdentifier] = useState(users[0]?.email || "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  // Modal State for Adding New User
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [newUserForm, setNewUserForm] = useState({
    name: "",
    email: "",
    username: "",
    password: "password123",
    role: "department_manager",
    department: "",
  });
  const [modalError, setModalError] = useState("");

  const redirectPath = location.state?.from?.pathname || "/";

  const handleSelectDesignation = (user) => {
    setSelectedUser(user);
    setIdentifier(user.email);
    setPassword("");
    setErrorMessage("");
    setSuccessMessage("");
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");

    if (!identifier.trim()) {
      setErrorMessage("Please enter your designation email or username.");
      return;
    }

    if (!password.trim()) {
      setErrorMessage("Please enter your password.");
      return;
    }

    const res = login(identifier, password);
    if (res.success) {
      navigate(redirectPath, { replace: true });
    } else {
      setErrorMessage(res.message);
    }
  };

  const handleAddUserSubmit = (e) => {
    e.preventDefault();
    setModalError("");

    const res = addUser(newUserForm);
    if (res.success) {
      setShowAddUserModal(false);
      setSelectedUser(res.user);
      setIdentifier(res.user.email);
      setPassword("");
      setSuccessMessage(`User "${res.user.name}" registered successfully as ${res.user.roleLabel}. You can now sign in.`);
      setNewUserForm({
        name: "",
        email: "",
        username: "",
        password: "password123",
        role: "department_manager",
        department: "",
      });
    } else {
      setModalError(res.message);
    }
  };

  return (
    <Container className="py-4" style={{ maxWidth: "1050px" }}>
      {/* Brand Header */}
      <div className="text-center mb-4">
        <h1 className="fw-bold display-6 ms-page-title mb-1">
          ◆ MediSource AI
        </h1>
        <p className="ms-page-sub mx-auto text-muted fs-6" style={{ maxWidth: "600px" }}>
          Enterprise Designation Gateway & Role-Based Authentication
        </p>
      </div>

      {/* Currently Logged-in Session Banner */}
      {isAuthenticated && currentUser && (
        <Alert variant="info" className="d-flex align-items-center justify-content-between rounded-4 shadow-sm mb-4">
          <div>
            <strong>Active Session:</strong> Signed in as <Badge bg={currentUser.badgeVariant}>{currentUser.name}</Badge> ({currentUser.roleLabel}).
          </div>
          <div className="d-flex gap-2">
            <Button size="sm" variant="dark" className="rounded-pill" onClick={() => navigate("/")}>
              Continue to Dashboard →
            </Button>
            <Button size="sm" variant="outline-danger" className="rounded-pill" onClick={logout}>
              Sign Out
            </Button>
          </div>
        </Alert>
      )}

      {successMessage && (
        <Alert variant="success" className="rounded-3 mb-4 shadow-sm" dismissible onClose={() => setSuccessMessage("")}>
          {successMessage}
        </Alert>
      )}

      {errorMessage && (
        <Alert variant="danger" className="rounded-3 mb-4 shadow-sm" dismissible onClose={() => setErrorMessage("")}>
          <strong>Authentication Error:</strong> {errorMessage}
        </Alert>
      )}

      {/* Top Designation Switcher Navigation Bar */}
      <Card className="shadow-sm border-0 rounded-4 mb-4 bg-white p-2">
        <div className="d-flex align-items-center justify-content-between px-3 py-2 border-bottom mb-2">
          <span className="fw-bold text-dark small text-uppercase tracking-wider">
            Select User Designation ({users.length} registered users)
          </span>
          <Button
            variant="outline-primary"
            size="sm"
            className="rounded-pill px-3 fw-bold"
            onClick={() => setShowAddUserModal(true)}
          >
              Add New User
          </Button>
        </div>

        <Nav variant="pills" className="d-flex flex-wrap gap-2 p-1">
          {users.map((user) => {
            const isSelected = selectedUser.id === user.id;
            return (
              <Nav.Item key={user.id} className="flex-fill" style={{ minWidth: "220px" }}>
                <Button
                  variant={isSelected ? "dark" : "light"}
                  className={`w-100 text-start d-flex align-items-center justify-content-between py-2 px-3 rounded-3 border ${
                    isSelected ? "border-dark shadow-sm" : "border-light"
                  }`}
                  onClick={() => handleSelectDesignation(user)}
                >
                  <div>
                    <div className="fw-bold small d-flex align-items-center gap-1">
                      {user.roleLabel}
                      {user.isCustom && <Badge bg="secondary" style={{ fontSize: "0.6rem" }}>Custom</Badge>}
                    </div>
                    <div className={isSelected ? "text-light small" : "text-muted small"} style={{ fontSize: "0.75rem" }}>
                      {user.name} • {user.department}
                    </div>
                  </div>
                  <Badge bg={user.badgeVariant} className="px-2 py-1 text-uppercase ms-2" style={{ fontSize: "0.68rem" }}>
                    {user.initials}
                  </Badge>
                </Button>
              </Nav.Item>
            );
          })}
        </Nav>
      </Card>

      {/* Login Form & Selected Role Scope */}
      <Row className="g-4">
        <Col lg={7}>
          <Card className="shadow-sm border-0 rounded-4 h-100">
            <Card.Body className="p-4">
              <div className="d-flex align-items-center gap-2 mb-3">
                <Badge bg={selectedUser.badgeVariant} className="px-2 py-1 fs-6">
                  {selectedUser.initials}
                </Badge>
                <h5 className="fw-bold mb-0">Sign In — {selectedUser.roleLabel}</h5>
              </div>

              <Form onSubmit={handleSubmit}>
                <Form.Group className="mb-3" controlId="loginIdentifier">
                  <Form.Label className="fw-semibold small">Email Address or Designation Username</Form.Label>
                  <Form.Control
                    type="text"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder="Enter email or designation key"
                    required
                  />
                </Form.Group>

                <Form.Group className="mb-4" controlId="loginPassword">
                  <Form.Label className="fw-semibold small">Password</Form.Label>
                  <div className="position-relative">
                    <Form.Control
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter password"
                      required
                    />
                    <Button
                      type="button"
                      variant="link"
                      className="position-absolute end-0 top-50 translate-middle-y text-muted text-decoration-none pe-3 py-0"
                      onClick={() => setShowPassword(!showPassword)}
                      style={{ fontSize: "0.8rem" }}
                    >
                      {showPassword ? "Hide" : "Show"}
                    </Button>
                  </div>
                </Form.Group>

                <div className="d-grid">
                  <Button type="submit" variant="dark" size="lg" className="rounded-pill fw-bold">
                    Sign In to Portal
                  </Button>
                </div>
              </Form>
            </Card.Body>
          </Card>
        </Col>

        {/* Designation Scope Details */}
        <Col lg={5}>
          <Card className="ms-panel border-0 rounded-4 h-100 p-3">
            <Card.Body className="d-flex flex-column justify-content-between">
              <div>
                <div className="d-flex align-items-center justify-content-between mb-3">
                  <span className="text-uppercase small tracking-wide text-light opacity-75">
                    Designation Profile
                  </span>
                  <Badge bg={selectedUser.badgeVariant} className="px-2 py-1">
                    {selectedUser.department}
                  </Badge>
                </div>

                <h4 className="fw-bold text-white mb-2">{selectedUser.roleLabel}</h4>
                <p className="text-light opacity-75 small mb-4">
                  {selectedUser.description}
                </p>

                <h6 className="fw-bold text-white mb-2">Module Access Permissions:</h6>
                <div className="d-flex flex-wrap gap-2 mb-3">
                  {selectedUser.permissions.map((perm) => (
                    <Badge key={perm} bg="dark" className="border border-secondary px-2 py-1 text-light">
                {perm}
                    </Badge>
                  ))}
                </div>
              </div>

              <div className="p-3 bg-white bg-opacity-10 rounded-3 border border-white border-opacity-10 mt-3">
                <div className="text-white small fw-bold">Access Control</div>
                <div className="text-light opacity-75 small" style={{ fontSize: "0.75rem" }}>
                  Role permissions strictly enforced via <code>X-User-Role</code> headers matching OPA policies.
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Modal for Adding New User */}
      <Modal show={showAddUserModal} onHide={() => setShowAddUserModal(false)} centered>
        <Modal.Header closeButton className="border-0 pb-0">
          <Modal.Title className="fw-bold">Register / Add New User Account</Modal.Title>
        </Modal.Header>
        <Form onSubmit={handleAddUserSubmit}>
          <Modal.Body className="pt-3">
            {modalError && (
              <Alert variant="danger" className="py-2 px-3 small">
                {modalError}
              </Alert>
            )}

            <Form.Group className="mb-3">
              <Form.Label className="fw-semibold small">Full Name</Form.Label>
              <Form.Control
                type="text"
                placeholder="e.g. Dr. Robert Chen"
                value={newUserForm.name}
                onChange={(e) => setNewUserForm({ ...newUserForm, name: e.target.value })}
                required
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label className="fw-semibold small">Email Address</Form.Label>
              <Form.Control
                type="email"
                placeholder="e.g. robert.chen@medisource.ai"
                value={newUserForm.email}
                onChange={(e) => setNewUserForm({ ...newUserForm, email: e.target.value })}
                required
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label className="fw-semibold small">Username</Form.Label>
              <Form.Control
                type="text"
                placeholder="e.g. robert"
                value={newUserForm.username}
                onChange={(e) => setNewUserForm({ ...newUserForm, username: e.target.value })}
                required
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label className="fw-semibold small">Designation / Role</Form.Label>
              <Form.Select
                value={newUserForm.role}
                onChange={(e) => setNewUserForm({ ...newUserForm, role: e.target.value })}
              >
                <option value="department_manager">Department Manager</option>
                <option value="finance_manager">Finance Manager</option>
                <option value="compliance_officer">Compliance Officer</option>
                <option value="procurement_director">Procurement Director</option>
              </Form.Select>
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label className="fw-semibold small">Department Name</Form.Label>
              <Form.Control
                type="text"
                placeholder="e.g. Neurology & Surgery"
                value={newUserForm.department}
                onChange={(e) => setNewUserForm({ ...newUserForm, department: e.target.value })}
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label className="fw-semibold small">Password</Form.Label>
              <Form.Control
                type="password"
                placeholder="Enter password"
                value={newUserForm.password}
                onChange={(e) => setNewUserForm({ ...newUserForm, password: e.target.value })}
                required
              />
            </Form.Group>
          </Modal.Body>
          <Modal.Footer className="border-0 pt-0">
            <Button variant="light" className="rounded-pill" onClick={() => setShowAddUserModal(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="dark" className="rounded-pill px-4">
              Add User
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>
    </Container>
  );
}
