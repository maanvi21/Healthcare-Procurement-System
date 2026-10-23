import React, { createContext, useContext, useEffect, useState } from "react";

export const BUILTIN_USERS = [
  {
    id: "usr_sarah_01",
    email: "dr.sarah@medisource.ai",
    username: "sarah",
    password: "password123",
    name: "Dr. Sarah",
    role: "department_manager",
    roleLabel: "Department Manager",
    department: "Cardiology",
    initials: "DS",
    badgeVariant: "primary",
    description: "Submits procurement requests, manages department inventory, and reviews local documents.",
    permissions: ["Overview", "Documents", "Approvals", "Inventory", "Notifications", "Kafka Logs"],
  },
  {
    id: "usr_mark_02",
    email: "mark.finance@medisource.ai",
    username: "mark",
    password: "password123",
    name: "Mark",
    role: "finance_manager",
    roleLabel: "Finance Manager",
    department: "Finance & Accounting",
    initials: "MF",
    badgeVariant: "warning",
    description: "Evaluates financial thresholds, assesses fiscal risks, and signs off on high-value budgets.",
    permissions: ["Overview", "Approvals", "Contracts", "Risk", "Notifications", "Kafka Logs"],
  },
  {
    id: "usr_elena_03",
    email: "elena.compliance@medisource.ai",
    username: "elena",
    password: "password123",
    name: "Elena",
    role: "compliance_officer",
    roleLabel: "Compliance Officer",
    department: "Regulatory Compliance",
    initials: "EC",
    badgeVariant: "info",
    description: "Onboards vendors, verifies legal/regulatory compliance, and inspects document fraud scores.",
    permissions: ["Overview", "Documents", "Vendors", "Approvals", "Contracts", "Risk", "Notifications", "Kafka Logs", "Storage"],
  },
  {
    id: "usr_arthur_04",
    email: "arthur.procurement@medisource.ai",
    username: "arthur",
    password: "password123",
    name: "Arthur",
    role: "procurement_director",
    roleLabel: "Procurement Director",
    department: "Procurement Executive",
    initials: "AP",
    badgeVariant: "danger",
    description: "Executes contract generation, triggers digital signatures, overrides policy flags, and oversees all systems.",
    permissions: ["Overview", "Documents", "Vendors", "Approvals", "Inventory", "Contracts", "Risk", "Notifications", "Kafka Logs", "Storage"],
  },
];

export const MOCK_USERS = BUILTIN_USERS;

export const ROLE_METADATA = {
  department_manager: {
    roleLabel: "Department Manager",
    badgeVariant: "primary",
    description: "Submits procurement requests, manages department inventory, and reviews local documents.",
    permissions: ["Overview", "Documents", "Approvals", "Inventory", "Notifications", "Kafka Logs"],
  },
  finance_manager: {
    roleLabel: "Finance Manager",
    badgeVariant: "warning",
    description: "Evaluates financial thresholds, assesses fiscal risks, and signs off on high-value budgets.",
    permissions: ["Overview", "Approvals", "Contracts", "Risk", "Notifications", "Kafka Logs"],
  },
  compliance_officer: {
    roleLabel: "Compliance Officer",
    badgeVariant: "info",
    description: "Onboards vendors, verifies legal/regulatory compliance, and inspects document fraud scores.",
    permissions: ["Overview", "Documents", "Vendors", "Approvals", "Contracts", "Risk", "Notifications", "Kafka Logs", "Storage"],
  },
  procurement_director: {
    roleLabel: "Procurement Director",
    badgeVariant: "danger",
    description: "Executes contract generation, triggers digital signatures, overrides policy flags, and oversees all systems.",
    permissions: ["Overview", "Documents", "Vendors", "Approvals", "Inventory", "Contracts", "Risk", "Notifications", "Kafka Logs", "Storage"],
  },
};

const ROUTE_PERMISSIONS = {
  "/": ["department_manager", "finance_manager", "compliance_officer", "procurement_director"],
  "/documents": ["department_manager", "compliance_officer", "procurement_director"],
  "/vendors": ["compliance_officer", "procurement_director"],
  "/approvals": ["department_manager", "finance_manager", "compliance_officer", "procurement_director"],
  "/inventory": ["department_manager", "procurement_director"],
  "/contracts": ["finance_manager", "compliance_officer", "procurement_director"],
  "/risk": ["finance_manager", "compliance_officer", "procurement_director"],
  "/notifications": ["department_manager", "finance_manager", "compliance_officer", "procurement_director"],
  "/kafka-logs": ["department_manager", "finance_manager", "compliance_officer", "procurement_director"],
  "/storage": ["compliance_officer", "procurement_director"],
};

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [users, setUsers] = useState(() => {
    try {
      const savedCustom = localStorage.getItem("medisource_custom_users");
      const customList = savedCustom ? JSON.parse(savedCustom) : [];
      return [...BUILTIN_USERS, ...customList];
    } catch (err) {
      console.error("Error loading custom users from storage", err);
      return BUILTIN_USERS;
    }
  });

  const [currentUser, setCurrentUser] = useState(() => {
    const savedId = localStorage.getItem("medisource_user_id");
    const isAuth = localStorage.getItem("medisource_authenticated") === "true";
    if (!isAuth || !savedId) return null;
    const found = users.find((u) => u.id === savedId);
    return found || null;
  });

  const isAuthenticated = Boolean(currentUser && localStorage.getItem("medisource_authenticated") === "true");

  const addUser = ({ name, email, username, password, role, department }) => {
    const cleanEmail = (email || "").trim().toLowerCase();
    const cleanUsername = (username || "").trim().toLowerCase();
    const cleanName = (name || "").trim();
    const cleanDept = (department || "").trim() || "General Department";

    if (!cleanName || !cleanEmail || !cleanUsername || !password) {
      return { success: false, message: "All required fields (Name, Email, Username, Password) must be filled." };
    }

    const existing = users.find(
      (u) => u.email.toLowerCase() === cleanEmail || u.username.toLowerCase() === cleanUsername
    );

    if (existing) {
      return { success: false, message: `A user with email '${cleanEmail}' or username '${cleanUsername}' already exists.` };
    }

    const meta = ROLE_METADATA[role] || ROLE_METADATA.department_manager;

    // Generate Initials (e.g., "Dr. Robert Chen" -> "RC")
    const words = cleanName.replace(/[^a-zA-Z\s]/g, "").trim().split(/\s+/);
    const initials = words.length >= 2
      ? (words[0][0] + words[words.length - 1][0]).toUpperCase()
      : cleanName.substring(0, 2).toUpperCase();

    const newUser = {
      id: `usr_custom_${Date.now()}`,
      email: cleanEmail,
      username: cleanUsername,
      password: password.trim(),
      name: cleanName,
      role,
      roleLabel: meta.roleLabel,
      department: cleanDept,
      initials,
      badgeVariant: meta.badgeVariant,
      description: meta.description,
      permissions: meta.permissions,
      isCustom: true,
    };

    const updatedUsers = [...users, newUser];
    setUsers(updatedUsers);

    // Save only custom users to localStorage
    const customUsers = updatedUsers.filter((u) => u.isCustom);
    localStorage.setItem("medisource_custom_users", JSON.stringify(customUsers));

    return { success: true, user: newUser };
  };

  const login = (identifier, password) => {
    const cleanId = (identifier || "").trim().toLowerCase();
    const cleanPass = (password || "").trim();

    const user = users.find(
      (u) =>
        u.email.toLowerCase() === cleanId ||
        u.username.toLowerCase() === cleanId ||
        u.role === cleanId ||
        u.id === cleanId
    );

    if (!user) {
      return { success: false, message: "No matching account or designation email found." };
    }

    if (user.password !== cleanPass) {
      return { success: false, message: "Invalid password for selected designation account." };
    }

    setCurrentUser(user);
    localStorage.setItem("medisource_user_id", user.id);
    localStorage.setItem("medisource_authenticated", "true");
    return { success: true, user };
  };

  const logout = () => {
    setCurrentUser(null);
    localStorage.removeItem("medisource_user_id");
    localStorage.setItem("medisource_authenticated", "false");
  };

  const hasRole = (allowedRoles) => {
    if (!isAuthenticated || !currentUser) return false;
    if (!allowedRoles || allowedRoles.length === 0) return true;
    return allowedRoles.includes(currentUser.role);
  };

  const checkPermission = (path) => {
    if (!isAuthenticated || !currentUser) return false;
    const allowed = ROUTE_PERMISSIONS[path];
    if (!allowed) return true;
    return allowed.includes(currentUser.role);
  };

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        isAuthenticated,
        login,
        logout,
        addUser,
        users,
        mockUsers: users,
        hasRole,
        checkPermission,
        routePermissions: ROUTE_PERMISSIONS,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
