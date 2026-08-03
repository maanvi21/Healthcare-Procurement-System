# Data Model & Event Schema

Each service owns a private PostgreSQL database (database-per-service). No service reads
another service's tables directly — all cross-service data flow is via REST calls from the
frontend/gateway or Kafka events.

## document_intelligence — db `medisource_documents`

- **documents**(id UUID pk, source ENUM[upload,email,api,shared_folder], original_filename,
  minio_object_key, content_hash, doc_type ENUM[invoice,purchase_order,quotation,
  compliance_certificate,unclassified], status ENUM[received,processing,extracted,
  needs_review,validated,rejected], vendor_id UUID nullable, uploaded_at, processed_at)
- **extracted_fields**(id UUID pk, document_id fk, field_name, field_value, confidence
  FLOAT, is_manually_corrected BOOL)
- **duplicate_flags**(id UUID pk, document_id fk, duplicate_of_document_id fk, reason)

## vendor_intelligence — db `medisource_vendors`

- **vendors**(id UUID pk, legal_name, vendor_type ENUM[equipment_supplier,
  pharma_distributor, amc_contractor, consumables_supplier], gst_number, drug_license_number
  nullable, drug_license_expiry DATE nullable, fda_cdsco_registration_id nullable,
  contact_email, contact_phone, status ENUM[pending_review,approved,rejected,suspended],
  risk_band ENUM[low,medium,high] nullable, onboarded_at)
- **vendor_documents**(id UUID pk, vendor_id fk, document_id UUID references
  document_intelligence.documents(id) logically [cross-service id, not an FK], doc_purpose)

## approval_workflow — db `medisource_approvals`

- **procurement_requests**(id UUID pk, requested_by, department, category, vendor_id UUID,
  total_value NUMERIC, currency, status ENUM[pending,approved,rejected,escalated],
  created_at)
- **approval_steps**(id UUID pk, request_id fk, step_order INT, approver_role, approver_id
  nullable, status ENUM[pending,approved,rejected,skipped], sla_deadline TIMESTAMP,
  decided_at, decision_note)
- **approval_history**(id UUID pk, request_id fk, event, actor, at TIMESTAMP)

## inventory_intelligence — db `medisource_inventory`

- **stock_items**(id UUID pk, sku, name, category ENUM[drug,consumable,ppe,implant,
  equipment], unit, cold_chain BOOL, reorder_point INT, reorder_qty INT)
- **stock_batches**(id UUID pk, stock_item_id fk, batch_no, expiry_date DATE, quantity_on_hand
  INT, warehouse_location)
- **reservations**(id UUID pk, stock_item_id fk, batch_id fk nullable, request_id UUID
  [references approval_workflow.procurement_requests(id)], quantity INT, status
  ENUM[reserved,released,fulfilled,expired], reserved_at, expires_at)
- **backorders**(id UUID pk, stock_item_id fk, request_id UUID, quantity_short INT,
  suggested_reorder_qty INT, created_at)

## contract_intelligence — db `medisource_contracts`

- **contract_templates**(id UUID pk, name, template_type ENUM[supply_agreement,
  equipment_amc,vendor_agreement,nda], body_template TEXT [Jinja2], version INT)
- **contracts**(id UUID pk, template_id fk, vendor_id UUID, request_id UUID nullable,
  status ENUM[draft,sent_for_signature,signed,expired,terminated], minio_object_key,
  version INT, effective_date DATE, expiry_date DATE, renewal_reminder_days INT,
  esign_envelope_id nullable, created_at)
- **contract_events**(id UUID pk, contract_id fk, event, at TIMESTAMP)

## risk_intelligence — db `medisource_risk`

- **risk_assessments**(id UUID pk, vendor_id UUID, compliance_risk FLOAT, fraud_risk FLOAT,
  financial_risk FLOAT, supplier_risk FLOAT, operational_risk FLOAT, overall_risk FLOAT,
  risk_band ENUM[low,medium,high], model_version, assessed_at)
- **risk_features_snapshot**(id UUID pk, assessment_id fk, feature_name, feature_value)

## Kafka topics

| Topic | Producer | Consumers | Payload |
|---|---|---|---|
| `documents.ingested` | document_intelligence | — | document_id, source, doc_type(nullable) |
| `documents.processed` | document_intelligence | vendor_intelligence, approval_workflow | document_id, doc_type, vendor_id, extracted summary |
| `vendor.onboarded` | vendor_intelligence | risk_intelligence | vendor_id, status |
| `vendor.updated` | vendor_intelligence | risk_intelligence | vendor_id, changed_fields |
| `procurement.request.created` | approval_workflow | inventory_intelligence, risk_intelligence | request_id, vendor_id, items, total_value |
| `approval.requested` | approval_workflow | — | request_id, step |
| `approval.approved` | approval_workflow | contract_intelligence, inventory_intelligence | request_id, vendor_id |
| `approval.rejected` | approval_workflow | inventory_intelligence | request_id |
| `approval.escalated` | approval_workflow | — | request_id, step, escalated_to |
| `inventory.reserved` | inventory_intelligence | — | request_id, stock_item_id, quantity |
| `inventory.backorder` | inventory_intelligence | — | request_id, stock_item_id, quantity_short |
| `contract.generated` | contract_intelligence | — | contract_id, vendor_id |
| `contract.signed` | contract_intelligence | — | contract_id |
| `risk.assessed` | risk_intelligence | vendor_intelligence, contract_intelligence | vendor_id, overall_risk, risk_band |

All events are JSON, `{"event": "<topic>", "data": {...}, "occurred_at": "<iso8601>"}`,
produced with `key = <primary entity id>` for partition affinity.
