"""Renders the risk agent's ML layer as a presentation-ready diagram."""
FEATURES = {
    "Vendor master data": ("#0D6E61", [
        "license_days_to_expiry", "gstin_valid", "watchlist_hit", "years_in_business",
    ]),
    "Caller-supplied (ERP / WMS)": ("#8A5A05", [
        "cold_chain_violation_count", "financial_health_score", "prior_compliance_flags",
    ]),
    "Measured from platform events": ("#1F5FA8", [
        "late_delivery_rate", "doc_fraud_flag_rate", "doc_mean_fraud_score",
        "duplicate_invoice_rate", "log_total_spend", "spend_volatility",
        "spend_growth_ratio", "max_amount_zscore", "round_amount_rate", "anomaly_score",
    ]),
}
DIMS = [
    ("compliance_risk", "license expiry 79%"),
    ("fraud_risk", "watchlist 78%"),
    ("financial_risk", "fin. health 72%"),
    ("supplier_risk", "cold chain 55%"),
    ("spend_risk", "volatility 57%"),
    ("operational_risk", "cold chain 53%"),
]

INK, MUTED, LINE, BG = "#12211F", "#5F706C", "#C6D2CD", "#FFFFFF"
W, H = 1680, 960
p = []
a = p.append

a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
  f'font-family="Helvetica,Arial,sans-serif">')
a(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
a('<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
  f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{INK}"/></marker>'
  '<marker id="arg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
  'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#0D6E61"/></marker></defs>')

# title
a(f'<text x="48" y="56" font-size="30" font-weight="700" fill="{INK}">Risk Analysis Agent — ML Layer</text>')
a(f'<text x="48" y="84" font-size="16" fill="{MUTED}">17 features · 2 models · 6 risk dimensions + 1 anomaly signal</text>')
a(f'<line x1="48" y1="102" x2="{W-48}" y2="102" stroke="{INK}" stroke-width="2"/>')

# ---------------- column 1: features ----------------
a(f'<text x="48" y="140" font-size="13" font-weight="700" fill="{MUTED}" letter-spacing="1.6">INPUT FEATURE VECTOR (17)</text>')
y = 158
for group, (colour, feats) in FEATURES.items():
    bh = 34 + len(feats) * 25
    a(f'<rect x="48" y="{y}" width="416" height="{bh}" rx="7" fill="none" stroke="{colour}" stroke-width="2"/>')
    a(f'<text x="68" y="{y+25}" font-size="15" font-weight="700" fill="{colour}">{group} — {len(feats)}</text>')
    fy = y + 50
    for f in feats:
        a(f'<circle cx="76" cy="{fy-5}" r="3" fill="{colour}"/>')
        a(f'<text x="90" y="{fy}" font-size="14.5" font-family="monospace" fill="{INK}">{f}</text>')
        fy += 25
    y += bh + 16

# ---------------- column 2: the two models ----------------
MX = 560
a(f'<text x="{MX}" y="140" font-size="13" font-weight="700" fill="{MUTED}" letter-spacing="1.6">MODEL 1 — SUPERVISED</text>')
a(f'<rect x="{MX}" y="158" width="430" height="342" rx="7" fill="#F2F7F5" stroke="{INK}" stroke-width="2.5"/>')
a(f'<text x="{MX+20}" y="192" font-size="19" font-weight="700" fill="{INK}">MultiOutputRegressor</text>')
a(f'<text x="{MX+20}" y="216" font-size="14" fill="{MUTED}">fits one independent regressor per target</text>')
a(f'<line x1="{MX+20}" y1="232" x2="{MX+410}" y2="232" stroke="{LINE}" stroke-width="1.5"/>')
gy = 258
for i in range(6):
    a(f'<rect x="{MX+20}" y="{gy}" width="390" height="26" rx="4" fill="#FFFFFF" stroke="{LINE}" stroke-width="1.2"/>')
    a(f'<text x="{MX+32}" y="{gy+18}" font-size="13.5" font-family="monospace" fill="{INK}">'
      f'GradientBoostingRegressor · 150 trees</text>')
    gy += 32
a(f'<text x="{MX+20}" y="{gy+14}" font-size="13" fill="{MUTED}">900 trees total · max_depth 3 · lr 0.08 · squared_error</text>')

a(f'<text x="{MX}" y="536" font-size="13" font-weight="700" fill="{MUTED}" letter-spacing="1.6">MODEL 2 — UNSUPERVISED</text>')
a(f'<rect x="{MX}" y="554" width="430" height="176" rx="7" fill="#F2F7F5" stroke="{INK}" stroke-width="2.5" stroke-dasharray="7 4"/>')
a(f'<text x="{MX+20}" y="588" font-size="19" font-weight="700" fill="{INK}">IsolationForest</text>')
a(f'<text x="{MX+20}" y="612" font-size="14" fill="{MUTED}">100 trees · contamination="auto" · min 8 samples</text>')
a(f'<line x1="{MX+20}" y1="628" x2="{MX+410}" y2="628" stroke="{LINE}" stroke-width="1.5"/>')
a(f'<text x="{MX+20}" y="652" font-size="14" font-weight="700" fill="{INK}">+ 3 named rules</text>')
for i, r in enumerate(["spend spike ≥ 3× prior 90 days",
                       "invoice ≥ 3σ from peer mean",
                       "> 5 invoices in 7 days"]):
    a(f'<text x="{MX+34}" y="{674+i*22}" font-size="13.5" fill="{INK}">• {r}</text>')

# feature -> models
a(f'<line x1="464" y1="329" x2="{MX-8}" y2="329" stroke="{INK}" stroke-width="2" marker-end="url(#ar)"/>')
a(f'<text x="{(464+MX)//2}" y="321" font-size="12.5" text-anchor="middle" fill="{MUTED}">all 17</text>')
a(f'<line x1="464" y1="640" x2="{MX-8}" y2="640" stroke="{INK}" stroke-width="2" marker-end="url(#ar)"/>')
a(f'<text x="{(464+MX)//2}" y="632" font-size="12.5" text-anchor="middle" fill="{MUTED}">spend series</text>')

# ---------------- column 3: outputs ----------------
OX = 1080
a(f'<text x="{OX}" y="140" font-size="13" font-weight="700" fill="{MUTED}" letter-spacing="1.6">OUTPUT</text>')
dy = 158
for name, driver in DIMS:
    a(f'<rect x="{OX}" y="{dy}" width="330" height="42" rx="5" fill="#FFFFFF" stroke="{LINE}" stroke-width="1.5"/>')
    a(f'<text x="{OX+16}" y="{dy+19}" font-size="15" font-weight="700" font-family="monospace" fill="{INK}">{name}</text>')
    a(f'<text x="{OX+16}" y="{dy+35}" font-size="12.5" fill="{MUTED}">top driver: {driver}</text>')
    a(f'<line x1="{MX+430}" y1="{dy+21}" x2="{OX-8}" y2="{dy+21}" stroke="{INK}" stroke-width="1.4" marker-end="url(#ar)"/>')
    dy += 50
a(f'<text x="{OX}" y="{dy+16}" font-size="12.5" fill="{MUTED}">each clipped to [0, 1]</text>')

# anomaly output
a(f'<rect x="{OX}" y="596" width="330" height="60" rx="5" fill="#FFFFFF" stroke="{INK}" stroke-width="2" stroke-dasharray="6 3"/>')
a(f'<text x="{OX+16}" y="622" font-size="15" font-weight="700" font-family="monospace" fill="{INK}">anomaly_score + flag</text>')
a(f'<text x="{OX+16}" y="642" font-size="12.5" fill="{MUTED}">with human-readable reasons</text>')
a(f'<line x1="{MX+430}" y1="642" x2="{OX-8}" y2="626" stroke="{INK}" stroke-width="1.4" stroke-dasharray="6 3" marker-end="url(#ar)"/>')

# feedback loop: anomaly_score is also a feature
# measured-features box spans y 433..717; anomaly_score is its last row.
# Route the loop below Model 2 (which ends at y=730) so nothing is crossed.
a(f'<path d="M {OX+165} 656 L {OX+165} 792 L 262 792 L 262 721" fill="none" '
  f'stroke="#0D6E61" stroke-width="2.5" stroke-dasharray="7 4" marker-end="url(#arg)"/>')
a(f'<text x="470" y="784" font-size="14.5" font-weight="700" fill="#0D6E61">anomaly_score re-enters as 1 of the 17 features</text>')

# banding
a(f'<rect x="{OX}" y="750" width="330" height="150" rx="7" fill="#F2F7F5" stroke="#0D6E61" stroke-width="2.5"/>')
a(f'<text x="{OX+16}" y="780" font-size="17" font-weight="700" fill="#0D6E61">Banding</text>')
a(f'<text x="{OX+16}" y="806" font-size="13.5" font-family="monospace" fill="{INK}">worst ≥ 0.80 → overall = worst</text>')
a(f'<text x="{OX+16}" y="828" font-size="13.5" font-family="monospace" fill="{INK}">else ½·mean + ½·worst</text>')
a(f'<line x1="{OX+16}" y1="842" x2="{OX+314}" y2="842" stroke="{LINE}" stroke-width="1.5"/>')
a(f'<text x="{OX+16}" y="864" font-size="13.5" fill="{INK}">≤ 0.34 low   ·   ≤ 0.67 medium   ·   &gt; 0.67 high</text>')
a(f'<text x="{OX+16}" y="886" font-size="12.5" fill="{MUTED}">feeds OPA approval routing</text>')
a(f'<line x1="{OX+165}" y1="{158+6*50+18}" x2="{OX+165}" y2="742" stroke="{INK}" stroke-width="2" marker-end="url(#ar)"/>')

# footer
a(f'<text x="48" y="{H-24}" font-size="13" fill="{MUTED}">'
  'Trained on 4,000 synthetic rows (3,200 train / 800 test), seed 42 · tracked in MLflow · '
  'importances read from Production v4</text>')
a('</svg>')

open("/out/risk_ml_layer.svg", "w").write("\n".join(p))
print("  wrote risk_ml_layer.svg")
