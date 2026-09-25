import React from "react";
import { Container } from "react-bootstrap";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext.jsx";
import NavBar from "./components/NavBar.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import Home from "./pages/Home.jsx";
import DocumentUpload from "./pages/DocumentUpload.jsx";
import VendorOnboarding from "./pages/VendorOnboarding.jsx";
import ApproverInbox from "./pages/ApproverInbox.jsx";
import InventoryDashboard from "./pages/InventoryDashboard.jsx";
import ContractRepository from "./pages/ContractRepository.jsx";
import RiskDashboard from "./pages/RiskDashboard.jsx";
import NotificationsDashboard from "./pages/NotificationsDashboard.jsx";

export default function App() {
  return (
    <AuthProvider>
      <NavBar />
      <Container fluid="lg" className="pb-5">
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Home />
              </ProtectedRoute>
            }
          />
          <Route
            path="/documents"
            element={
              <ProtectedRoute allowedRoles={["department_manager", "compliance_officer", "procurement_director"]}>
                <DocumentUpload />
              </ProtectedRoute>
            }
          />
          <Route
            path="/vendors"
            element={
              <ProtectedRoute allowedRoles={["compliance_officer", "procurement_director"]}>
                <VendorOnboarding />
              </ProtectedRoute>
            }
          />
          <Route
            path="/approvals"
            element={
              <ProtectedRoute>
                <ApproverInbox />
              </ProtectedRoute>
            }
          />
          <Route
            path="/inventory"
            element={
              <ProtectedRoute allowedRoles={["department_manager", "procurement_director"]}>
                <InventoryDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/contracts"
            element={
              <ProtectedRoute allowedRoles={["finance_manager", "compliance_officer", "procurement_director"]}>
                <ContractRepository />
              </ProtectedRoute>
            }
          />
          <Route
            path="/risk"
            element={
              <ProtectedRoute allowedRoles={["finance_manager", "compliance_officer", "procurement_director"]}>
                <RiskDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/notifications"
            element={
              <ProtectedRoute>
                <NotificationsDashboard />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Container>
    </AuthProvider>
  );
}
