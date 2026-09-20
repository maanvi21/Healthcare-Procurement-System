# MediSource AI — Role-Based Access Control (RBAC) Specification

This document details the Role-Based Access Control (RBAC) architecture, role permissions, API authorization matrix, OPA rules, header specifications, and mock user accounts for MediSource AI.

---

## 1. System Roles & Mock Pre-Seeded Users

MediSource AI enforces 4 domain-specific hospital roles:

| Role Key | Display Name | Pre-Seeded User Identity | Department | Primary Responsibilities |
|---|---|---|---|---|
| `department_manager` | Department Manager | **Dr. Sarah** | Cardiology / Clinical | Submitting procurement requests, viewing ward inventory, reviewing incoming doc extractions, approving Step 1 approvals. |
| `finance_manager` | Finance Manager | **Mark** | Finance & Accounting | Financial risk auditing, spend threshold review, GST/invoice validation, approving Step 2 (Finance) approvals. |
| `compliance_officer` | Compliance Officer | **Elena** | Regulatory & Compliance | Drug license verification, pharma & controlled-substance approval sign-off, contract compliance override. |
| `procurement_director` | Procurement Director | **Arthur** | Procurement Executive | Executive procurement oversight, final sign-off for high-value/risk purchases, vendor onboarding, contract e-signature execution. |

---

## 2. API Authorization & RBAC Matrix

| Microservice | Endpoint | HTTP Method | Allowed Roles | Error Behavior (403) |
|---|---|---|---|---|
| **Document Intelligence** | `/api/documents/ingest` | POST | `department_manager`, `procurement_director` | `Access denied for role <role>. Required: ['department_manager', 'procurement_director']` |
| | `/api/documents/{id}` | GET | All roles (`department_manager`, `finance_manager`, `compliance_officer`, `procurement_director`) | — |
| | `/api/documents/{id}/review` | POST | `department_manager`, `compliance_officer`, `procurement_director` | `Access denied for role <role>. Required: ['department_manager', 'compliance_officer', 'procurement_director']` |
| | `/api/documents/{id}` | DELETE | `procurement_director` | `Access denied for role <role>. Required: ['procurement_director']` |
| **Vendor Intelligence** | `/api/vendors` | GET | All roles | — |
| | `/api/vendors/onboard` | POST | `compliance_officer`, `procurement_director` | `Access denied for role <role>. Required: ['compliance_officer', 'procurement_director']` |
| | `/api/vendors/{id}` | PUT/PATCH | `procurement_director` | `Access denied for role <role>. Required: ['procurement_director']` |
| **Approval Workflow** | `/api/approvals/requests` | POST | `department_manager`, `procurement_director` | `Access denied for role <role>. Required: ['department_manager', 'procurement_director']` |
| | `/api/approvals/requests` | GET | All roles | — |
| | `/api/approvals/inbox` | GET | All roles (filtered by role query) | — |
| | `/api/approvals/requests/{id}/decide` | POST | Role MUST match pending step role (`department_manager` for step 1, `finance_manager` for finance step, `compliance_officer` for compliance step, `procurement_director` for director step) | `Access denied for role <role>. Required: [<step_role>]` |
| **Inventory Intelligence** | `/api/inventory` | GET | All roles | — |
| | `/api/inventory/reserve` | POST | `department_manager`, `procurement_director` | `Access denied for role <role>. Required: ['department_manager', 'procurement_director']` |
| **Contract Intelligence** | `/api/contracts` | GET | All roles | — |
| | `/api/contracts/generate` | POST | `procurement_director` | `Access denied for role <role>. Required: ['procurement_director']` |
| | `/api/contracts/{id}/send-for-signature` | POST | `procurement_director` | `Access denied for role <role>. Required: ['procurement_director']` |
| | `/api/contracts/{id}/override-compliance` | POST | `compliance_officer`, `procurement_director` | `Access denied for role <role>. Required: ['compliance_officer', 'procurement_director']` |
| **Risk Intelligence** | `/api/risk` | GET | All roles | — |
| | `/api/risk/assess` | POST | `finance_manager`, `compliance_officer`, `procurement_director` | `Access denied for role <role>. Required: ['finance_manager', 'compliance_officer', 'procurement_director']` |
| **Notification Agent** | `/api/notifications` | GET | All roles | — |

---

## 3. Header Specification & Gateway Propagation

All requests from the frontend client send the following context headers:
- `X-User-Role`: Key of active role (e.g. `department_manager`)
- `X-User-Id`: Unique identifier (e.g. `usr_sarah_01`)
- `X-User-Name`: Display name (e.g. `Dr. Sarah`)

Nginx gateway proxies these headers upstream to all FastAPI microservices (`proxy_set_header X-User-Role $http_x_user_role;`, etc.).

---

## 4. OPA (Open Policy Agent) RBAC Rules

Policy location: `policies/opa/rbac_rules.rego`

Evaluates path, method, and role to produce decision:
```rego
package medisource.rbac

default allow = false
```

Services query OPA or use internal FastAPI security dependency `require_roles(...)` enforcing identical policy semantics.
