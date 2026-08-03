# Vendor/contract compliance gate for MediSource AI (Team C).
#
# Called by contract_intelligence immediately before a contract is sent for
# e-signature (see services/contract_intelligence/app/opa_client.py), so a high-risk or
# regulatorily non-compliant vendor can never silently reach a signed contract without a
# human override being explicitly recorded.
#
# Input shape:
#   {
#     "vendor_risk_band": "low" | "medium" | "high" | "unknown",
#     "drug_license_valid": true | false,
#     "override_approved": true | false
#   }
package medisource.compliance

default allow_signature = false

allow_signature {
	input.vendor_risk_band != "high"
	input.drug_license_valid != false
}

allow_signature {
	input.override_approved == true
}

deny_reasons[msg] {
	input.vendor_risk_band == "high"
	not input.override_approved
	msg := "Vendor is high-risk; a contract-manager override is required before signature"
}

deny_reasons[msg] {
	input.drug_license_valid == false
	not input.override_approved
	msg := "Vendor's drug license is not currently valid"
}
