# Approval routing policy for MediSource AI (Team B).
#
# Input shape (see services/approval_workflow/app/opa_client.py):
#   {
#     "department": "cardiology",
#     "category": "pharma" | "controlled_substance" | "equipment" | "consumable" | ...,
#     "total_value": 125000.0,
#     "vendor_risk_band": "low" | "medium" | "high" | "unknown"
#   }
#
# Output: an ordered list of {"approver_role": ..., "sla_hours": ...} that
# approval_workflow turns into ApprovalStep rows and feeds to the ApprovalWorkflow
# Temporal workflow.
package medisource.approval

# ------------------------------------------------------------- value/risk based chain
base_chain(total_value, risk_band) = result {
	risk_band == "high"
	result := [
		{"approver_role": "department_manager", "sla_hours": 12},
		{"approver_role": "finance_manager", "sla_hours": 24},
		{"approver_role": "procurement_director", "sla_hours": 24},
	]
} else = result {
	total_value >= 500000
	result := [
		{"approver_role": "department_manager", "sla_hours": 12},
		{"approver_role": "finance_manager", "sla_hours": 24},
		{"approver_role": "procurement_director", "sla_hours": 48},
	]
} else = result {
	total_value >= 50000
	result := [
		{"approver_role": "department_manager", "sla_hours": 24},
		{"approver_role": "finance_manager", "sla_hours": 48},
	]
} else = result {
	result := [{"approver_role": "department_manager", "sla_hours": 24}]
}

# ------------------------------------------------- pharma / controlled-substance gate
# Drug and controlled-substance purchases always get an extra compliance-officer step,
# regardless of spend value — a low-value controlled-substance order still needs
# regulatory sign-off, unlike a low-value consumables order.
requires_compliance_review {
	input.category == "pharma"
}

requires_compliance_review {
	input.category == "controlled_substance"
}

compliance_step := [{"approver_role": "compliance_officer", "sla_hours": 12}]

# ------------------------------------------------------------------------ entrypoint
steps = result {
	requires_compliance_review
	result := array.concat(base_chain(input.total_value, input.vendor_risk_band), compliance_step)
} else = result {
	result := base_chain(input.total_value, input.vendor_risk_band)
}
