import React from "react";
import { Container } from "react-bootstrap";
import { Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext.jsx";
import NavBar from "./components/NavBar.jsx";
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
          <Route path="/" element={<Home />} />
          <Route path="/documents" element={<DocumentUpload />} />
          <Route path="/vendors" element={<VendorOnboarding />} />
          <Route path="/approvals" element={<ApproverInbox />} />
          <Route path="/inventory" element={<InventoryDashboard />} />
          <Route path="/contracts" element={<ContractRepository />} />
          <Route path="/risk" element={<RiskDashboard />} />
          <Route path="/notifications" element={<NotificationsDashboard />} />
        </Routes>
      </Container>
    </AuthProvider>
  );
}
