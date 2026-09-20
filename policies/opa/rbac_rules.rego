# RBAC Policy rules for MediSource AI.
#
# Input shape:
#   {
#     "user_role": "department_manager" | "finance_manager" | "compliance_officer" | "procurement_director",
#     "path": "/documents/ingest",
#     "method": "POST"
#   }
package medisource.rbac

default allow = false

# Document Intelligence permissions
allow {
    input.path == "/documents/ingest"
    input.method == "POST"
    input.user_role in ["department_manager", "procurement_director"]
}

allow {
    startswith(input.path, "/documents/")
    endswith(input.path, "/review")
    input.method == "POST"
    input.user_role in ["department_manager", "compliance_officer", "procurement_director"]
}

allow {
    startswith(input.path, "/documents/")
    input.method == "DELETE"
    input.user_role == "procurement_director"
}

# Vendor Intelligence permissions
allow {
    input.path == "/vendors/onboard"
    input.method == "POST"
    input.user_role in ["compliance_officer", "procurement_director"]
}

# Approval Workflow permissions
allow {
    input.path == "/approvals/requests"
    input.method == "POST"
    input.user_role in ["department_manager", "procurement_director"]
}

# Inventory Intelligence permissions
allow {
    input.path == "/inventory/reserve"
    input.method == "POST"
    input.user_role in ["department_manager", "procurement_director"]
}

# Contract Intelligence permissions
allow {
    input.path == "/contracts/generate"
    input.method == "POST"
    input.user_role == "procurement_director"
}

allow {
    endswith(input.path, "/send-for-signature")
    input.method == "POST"
    input.user_role == "procurement_director"
}

allow {
    endswith(input.path, "/override-compliance")
    input.method == "POST"
    input.user_role in ["compliance_officer", "procurement_director"]
}

# Risk Intelligence permissions
allow {
    input.path == "/risk/assess"
    input.method == "POST"
    input.user_role in ["finance_manager", "compliance_officer", "procurement_director"]
}

# GET requests across all services are allowed for authenticated roles
allow {
    input.method == "GET"
    input.user_role in ["department_manager", "finance_manager", "compliance_officer", "procurement_director"]
}
