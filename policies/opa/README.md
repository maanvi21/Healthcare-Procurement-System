# OPA Policies

Loaded into the `opa` container at startup (`docker-compose.yml` mounts this directory
into `/policies` and runs `opa run --server /policies`).

- **approval_rules.rego** — `medisource.approval.steps`: computes the approver chain +
  per-step SLA for a procurement request. Called by `approval_workflow`
  (`app/opa_client.py`) when a request is created.
- **compliance_rules.rego** — `medisource.compliance.allow_signature` /
  `medisource.compliance.deny_reasons`: gates whether a contract can be sent for
  e-signature. Called by `contract_intelligence` (`app/opa_client.py`) right before
  `POST /contracts/{id}/send-for-signature`.

## Testing a policy locally

```bash
# approval routing for a ₹125,000 pharma order from a medium-risk vendor
opa eval -d approval_rules.rego \
  -i <(echo '{"department":"pharmacy","category":"pharma","total_value":125000,"vendor_risk_band":"medium"}') \
  "data.medisource.approval.steps"

# compliance gate for a high-risk vendor without an override
opa eval -d compliance_rules.rego \
  -i <(echo '{"vendor_risk_band":"high","drug_license_valid":true,"override_approved":false}') \
  "data.medisource.compliance"
```

Or against the running container:

```bash
curl -X POST http://localhost:8181/v1/data/medisource/approval/steps \
  -d '{"input":{"department":"pharmacy","category":"pharma","total_value":125000,"vendor_risk_band":"medium"}}'
```
