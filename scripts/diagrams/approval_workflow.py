"""Approval workflow diagram — routing, the sequential chain, and every exit."""
INK, MUTED, LINE, BG = "#12211F", "#5F706C", "#C6D2CD", "#FFFFFF"
TEAL, AMBER, RED, BLUE = "#0D6E61", "#8A5A05", "#A0301C", "#1F5FA8"
W, H = 1720, 1000
p = []; a = p.append

a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
  f'font-family="Helvetica,Arial,sans-serif">')
a(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
a('<defs>')
for name, col in (("ar", INK), ("art", TEAL), ("arr", RED), ("ara", AMBER)):
    a(f'<marker id="{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
      f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{col}"/></marker>')
a('</defs>')

a(f'<text x="48" y="54" font-size="30" font-weight="700" fill="{INK}">Approval Workflow</text>')
a(f'<text x="48" y="82" font-size="16" fill="{MUTED}">'
  'OPA decides the chain · Temporal runs it · one approver at a time</text>')
a(f'<line x1="48" y1="100" x2="{W-48}" y2="100" stroke="{INK}" stroke-width="2"/>')

# ── STAGE 1 ─ triggers ──────────────────────────────────────────────────────
a(f'<text x="48" y="134" font-size="13" font-weight="700" fill="{MUTED}" letter-spacing="1.6">1 · REQUEST RAISED</text>')
a(f'<rect x="48" y="150" width="290" height="60" rx="6" fill="none" stroke="{TEAL}" stroke-width="2"/>')
a(f'<text x="66" y="176" font-size="15" font-weight="700" fill="{TEAL}">Automatically</text>')
a(f'<text x="66" y="196" font-size="13" fill="{INK}">clean invoice or PO from document agent</text>')
a(f'<rect x="48" y="222" width="290" height="60" rx="6" fill="none" stroke="{INK}" stroke-width="1.6"/>')
a(f'<text x="66" y="248" font-size="15" font-weight="700" fill="{INK}">By hand</text>')
a(f'<text x="66" y="268" font-size="13" fill="{INK}">submitted on the Approvals page</text>')

# ── STAGE 2 ─ OPA ───────────────────────────────────────────────────────────
a(f'<text x="400" y="134" font-size="13" font-weight="700" fill="{MUTED}" letter-spacing="1.6">2 · OPA DECIDES THE CHAIN</text>')
a(f'<rect x="400" y="150" width="530" height="216" rx="6" fill="#F2F7F5" stroke="{INK}" stroke-width="2.5"/>')
a(f'<text x="418" y="176" font-size="16" font-weight="700" fill="{INK}">Open Policy Agent</text>')
a(f'<text x="418" y="195" font-size="12.5" fill="{MUTED}">policies/opa/approval_rules.rego · input: value, category, vendor risk</text>')
a(f'<line x1="418" y1="206" x2="912" y2="206" stroke="{LINE}" stroke-width="1.5"/>')
rows = [
    ("vendor risk = high", "dept mgr 12h → finance 24h → director 24h"),
    ("value ≥ ₹5,00,000", "dept mgr 12h → finance 24h → director 48h"),
    ("value ≥ ₹50,000", "dept mgr 24h → finance 48h"),
    ("below that", "dept mgr 24h"),
]
ry = 228
for cond, chain in rows:
    a(f'<text x="418" y="{ry}" font-size="12.5" font-weight="700" fill="{INK}">{cond}</text>')
    a(f'<text x="596" y="{ry}" font-size="12.5" font-family="monospace" fill="{INK}">{chain}</text>')
    ry += 24
a(f'<line x1="418" y1="{ry-14}" x2="912" y2="{ry-14}" stroke="{LINE}" stroke-width="1.5"/>')
a(f'<text x="418" y="{ry+8}" font-size="12.5" font-weight="700" fill="{AMBER}">+ pharma or controlled substance</text>')
a(f'<text x="418" y="{ry+26}" font-size="12.5" fill="{INK}">always appends compliance officer 12h — at any value</text>')

a(f'<line x1="338" y1="240" x2="392" y2="240" stroke="{INK}" stroke-width="2" marker-end="url(#ar)"/>')

# ── STAGE 3 ─ the chain ─────────────────────────────────────────────────────
a(f'<text x="992" y="134" font-size="13" font-weight="700" fill="{MUTED}" letter-spacing="1.6">3 · THE CHAIN, ONE AT A TIME</text>')
a(f'<line x1="930" y1="240" x2="984" y2="240" stroke="{INK}" stroke-width="2" marker-end="url(#ar)"/>')
steps = [("Department manager", "24h"), ("Finance manager", "48h"), ("Compliance officer", "12h")]
sx = 992
for i, (role, sla) in enumerate(steps):
    a(f'<rect x="{sx}" y="150" width="216" height="66" rx="6" fill="#FFFFFF" stroke="{INK}" stroke-width="1.8"/>')
    a(f'<text x="{sx+14}" y="174" font-size="12" font-weight="700" fill="{MUTED}">STEP {i+1}</text>')
    a(f'<text x="{sx+14}" y="196" font-size="14.5" font-weight="700" fill="{INK}">{role}</text>')
    a(f'<text x="{sx+178}" y="174" font-size="12.5" font-family="monospace" fill="{AMBER}">{sla}</text>')
    if i < 2:
        a(f'<line x1="{sx+216}" y1="183" x2="{sx+244}" y2="183" stroke="{INK}" stroke-width="2" marker-end="url(#ar)"/>')
    sx += 244
a(f'<text x="992" y="244" font-size="12.5" fill="{MUTED}">Only the step in play appears in an inbox. The other two are invisible until their turn.</text>')
a(f'<text x="992" y="264" font-size="12.5" fill="{RED}">An out-of-turn decision is refused: 409 "awaiting step 1 (department manager)".</text>')

# ── STAGE 4 ─ what happens per step ─────────────────────────────────────────
a(f'<text x="48" y="{406}" font-size="13" font-weight="700" fill="{MUTED}" letter-spacing="1.6">4 · WHAT TEMPORAL DOES FOR EACH STEP</text>')
a(f'<rect x="48" y="422" width="1624" height="286" rx="8" fill="none" stroke="{INK}" stroke-width="2" stroke-dasharray="8 4"/>')
a(f'<text x="70" y="450" font-size="14" font-weight="700" fill="{INK}">repeat for every approver in the chain</text>')

boxes = [
    (86,  "Mark step pending", "publishes approval.requested", TEAL),
    (416, "Show in that role's inbox", "no one else sees it", INK),
    (746, "Wait for a decision", "clock runs for the step's SLA", AMBER),
    (1076,"Record the decision", "step approved / rejected", INK),
]
for bx, title, sub, col in boxes:
    a(f'<rect x="{bx}" y="474" width="290" height="72" rx="6" fill="#FFFFFF" stroke="{col}" stroke-width="2"/>')
    a(f'<text x="{bx+16}" y="502" font-size="14.5" font-weight="700" fill="{col}">{title}</text>')
    a(f'<text x="{bx+16}" y="524" font-size="12.5" fill="{MUTED}">{sub}</text>')
    if bx < 1076:
        a(f'<line x1="{bx+290}" y1="510" x2="{bx+326}" y2="510" stroke="{INK}" stroke-width="2" marker-end="url(#ar)"/>')

a(f'<rect x="1406" y="474" width="240" height="72" rx="6" fill="#FFFFFF" stroke="{TEAL}" stroke-width="2"/>')
a(f'<text x="1422" y="502" font-size="14.5" font-weight="700" fill="{TEAL}">Next approver</text>')
a(f'<text x="1422" y="524" font-size="12.5" fill="{MUTED}">or finish the chain</text>')
a(f'<line x1="1366" y1="510" x2="1398" y2="510" stroke="{INK}" stroke-width="2" marker-end="url(#ar)"/>')

# the async note
a(f'<rect x="416" y="572" width="620" height="52" rx="6" fill="#FFF9EC" stroke="{AMBER}" stroke-width="1.6"/>')
a(f'<text x="434" y="594" font-size="13" font-weight="700" fill="{AMBER}">The decision is a signal, not a direct write</text>')
a(f'<text x="434" y="613" font-size="12.5" fill="{INK}">'
  'The API returns instantly; Temporal updates the step ~4 seconds later.</text>')

# SLA timeout branch
a(f'<path d="M 891 546 L 891 656 L 1076 656" fill="none" stroke="{AMBER}" stroke-width="2" marker-end="url(#ara)"/>')
a(f'<text x="906" y="650" font-size="12.5" font-weight="700" fill="{AMBER}">SLA expires, no decision</text>')
a(f'<rect x="1076" y="632" width="290" height="52" rx="6" fill="#FFF9EC" stroke="{AMBER}" stroke-width="2"/>')
a(f'<text x="1092" y="654" font-size="14" font-weight="700" fill="{AMBER}">Escalate and move on</text>')
a(f'<text x="1092" y="672" font-size="12" fill="{INK}">step marked escalated · approval.escalated</text>')
a(f'<path d="M 1366 658 L 1526 658 L 1526 552" fill="none" stroke="{AMBER}" stroke-width="2" marker-end="url(#ara)"/>')

# ── STAGE 5 ─ outcomes ──────────────────────────────────────────────────────
a(f'<text x="48" y="{754}" font-size="13" font-weight="700" fill="{MUTED}" letter-spacing="1.6">5 · HOW IT ENDS</text>')
outs = [
    (48,   TEAL,  "APPROVED", "every step approved", "approval.approved → contract agent"),
    (592,  RED,   "REJECTED", "any one approver rejects", "approval.rejected — chain stops immediately"),
    (1136, AMBER, "ESCALATED", "an SLA expired", "approval.escalated — that step is skipped, chain continues"),
]
for ox, col, title, when, ev in outs:
    a(f'<rect x="{ox}" y="770" width="536" height="98" rx="7" fill="#FFFFFF" stroke="{col}" stroke-width="2.5"/>')
    a(f'<text x="{ox+18}" y="800" font-size="17" font-weight="700" fill="{col}">{title}</text>')
    a(f'<text x="{ox+18}" y="824" font-size="13.5" fill="{INK}">{when}</text>')
    a(f'<text x="{ox+18}" y="848" font-size="12.5" font-family="monospace" fill="{MUTED}">{ev}</text>')

a(f'<text x="48" y="906" font-size="13" fill="{MUTED}">'
  'Escalation does not reassign the step to someone more senior — it marks that approver as having missed their'
  ' window and hands the request to the next role in the chain.</text>')

a(f'<text x="48" y="{H-30}" font-size="13" fill="{MUTED}">'
  'Services: approval_workflow (FastAPI) · OPA (routing policy) · Temporal (SLA + orchestration) · '
  'Redis (60s duplicate guard) · Kafka (events) · PostgreSQL (medisource_approvals)</text>')
a('</svg>')
open("/out/approval_workflow.svg","w").write("\n".join(p))
print("  wrote approval_workflow.svg")
