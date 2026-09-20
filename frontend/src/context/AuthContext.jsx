import React, { createContext, useContext, useEffect, useState } from "react";

export const MOCK_USERS = [
  {
    id: "usr_sarah_01",
    name: "Dr. Sarah",
    role: "department_manager",
    roleLabel: "Department Manager",
    department: "Cardiology",
    initials: "DS",
    badgeVariant: "primary",
  },
  {
    id: "usr_mark_02",
    name: "Mark",
    role: "finance_manager",
    roleLabel: "Finance Manager",
    department: "Finance & Accounting",
    initials: "MF",
    badgeVariant: "warning",
  },
  {
    id: "usr_elena_03",
    name: "Elena",
    role: "compliance_officer",
    roleLabel: "Compliance Officer",
    department: "Regulatory Compliance",
    initials: "EC",
    badgeVariant: "info",
  },
  {
    id: "usr_arthur_04",
    name: "Arthur",
    role: "procurement_director",
    roleLabel: "Procurement Director",
    department: "Procurement Executive",
    initials: "AP",
    badgeVariant: "danger",
  },
];

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(() => {
    const savedId = localStorage.getItem("medisource_user_id");
    const found = MOCK_USERS.find((u) => u.id === savedId);
    return found || MOCK_USERS[0];
  });

  const switchUser = (userId) => {
    const user = MOCK_USERS.find((u) => u.id === userId);
    if (user) {
      setCurrentUser(user);
      localStorage.setItem("medisource_user_id", user.id);
    }
  };

  const hasRole = (allowedRoles) => {
    if (!allowedRoles || allowedRoles.length === 0) return true;
    return allowedRoles.includes(currentUser.role);
  };

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        switchUser,
        mockUsers: MOCK_USERS,
        hasRole,
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
