"""Default healthcare contract templates (Jinja2). Seeded into contract_templates on
first startup; the repository/dashboard UI can add further template versions without
any code change since rendering is fully data-driven."""
from jinja2 import Environment

from app.models import TemplateType

_env = Environment(autoescape=False)


def render(body_template: str, context: dict) -> str:
    template = _env.from_string(body_template)
    return template.render(**context)


DEFAULT_TEMPLATES: dict[TemplateType, dict] = {
    TemplateType.supply_agreement: {
        "name": "Standard Medical Supply Agreement",
        "body_template": """
<h1>MEDICAL SUPPLY AGREEMENT</h1>
<p>This Supply Agreement ("Agreement") is entered into as of {{ effective_date }} between
<b>{{ hospital_name }}</b> ("Buyer") and <b>{{ vendor_name }}</b> ("Supplier").</p>

<h2>1. Scope of Supply</h2>
<ul>
{% for item in items %}
  <li>{{ item.description }} — Qty: {{ item.quantity }} {{ item.unit | default('unit') }}
      {% if item.batch_no %} (Batch: {{ item.batch_no }}, Expiry: {{ item.expiry_date }}){% endif %}</li>
{% endfor %}
</ul>

<h2>2. Commercial Terms</h2>
<p>Total Contract Value: {{ currency | default('INR') }} {{ total_value }}<br/>
Payment Terms: {{ payment_terms | default('Net 30 days from delivery') }}</p>

<h2>3. Compliance</h2>
<p>Supplier warrants all pharmaceutical items supplied under this Agreement carry valid
drug-license and cold-chain compliance documentation as required by applicable law, and
that all consumable/implant items meet the quality standards specified by {{ hospital_name }}'s
procurement policy.</p>

<h2>4. Term</h2>
<p>This Agreement is effective from {{ effective_date }} and expires on {{ expiry_date }}
unless renewed or terminated earlier per Section 5.</p>

<h2>5. Termination</h2>
<p>Either party may terminate this Agreement with 30 days' written notice for convenience,
or immediately for a material breach including delivery of expired or non-compliant stock.</p>
""",
    },
    TemplateType.equipment_amc: {
        "name": "Biomedical Equipment Annual Maintenance Contract",
        "body_template": """
<h1>BIOMEDICAL EQUIPMENT ANNUAL MAINTENANCE CONTRACT (AMC)</h1>
<p>This AMC is entered into as of {{ effective_date }} between <b>{{ hospital_name }}</b>
("Buyer") and <b>{{ vendor_name }}</b> ("Service Provider").</p>

<h2>1. Covered Equipment</h2>
<ul>
{% for item in items %}
  <li>{{ item.description }}{% if item.serial_no %} (Serial No: {{ item.serial_no }}){% endif %}</li>
{% endfor %}
</ul>

<h2>2. Service Level</h2>
<p>Preventive maintenance visits: quarterly. Emergency response time: within 24 hours of a
fault report. Contract Value: {{ currency | default('INR') }} {{ total_value }} per annum.</p>

<h2>3. Term &amp; Renewal</h2>
<p>Effective {{ effective_date }} through {{ expiry_date }}. A renewal reminder is raised
{{ renewal_reminder_days }} days before expiry.</p>
""",
    },
    TemplateType.vendor_agreement: {
        "name": "General Vendor Agreement",
        "body_template": """
<h1>VENDOR AGREEMENT</h1>
<p>Entered into as of {{ effective_date }} between <b>{{ hospital_name }}</b> and
<b>{{ vendor_name }}</b>, governing all future purchase orders issued under this master
agreement through {{ expiry_date }}.</p>
<h2>Standard Terms</h2>
<p>Payment Terms: {{ payment_terms | default('Net 30 days from delivery') }}. All items
supplied must comply with {{ hospital_name }}'s vendor compliance policy.</p>
""",
    },
    TemplateType.nda: {
        "name": "Standard Non-Disclosure Agreement",
        "body_template": """
<h1>NON-DISCLOSURE AGREEMENT</h1>
<p>Entered into as of {{ effective_date }} between <b>{{ hospital_name }}</b> and
<b>{{ vendor_name }}</b> to protect confidential information exchanged during the course
of the procurement relationship, effective through {{ expiry_date }}.</p>
""",
    },
}
