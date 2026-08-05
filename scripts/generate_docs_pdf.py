import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#1A365D"))
        
        # Header (on all pages except page 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "MEDISOURCE AI — ARCHITECTURE & CAPABILITIES REPORT")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(1)
            self.line(54, 742, 612 - 54, 742)
            
            # Footer
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#718096"))
            self.drawString(54, 40, "Confidential | Healthcare Supply Chain Automation Platform")
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(612 - 54, 40, page_text)
            self.line(54, 52, 612 - 54, 52)
            
        self.restoreState()

def build_pdf(filename="MediSource_AI_Documentation.pdf"):
    # 54pt margin = 0.75 in. Letter is 612 x 792 pt. Printable width is 504 pt.
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    primary_color = colors.HexColor("#1A365D")   # Deep navy
    secondary_color = colors.HexColor("#2B6CB0") # Medium blue
    text_color = colors.HexColor("#2D3748")      # Dark slate text
    light_bg = colors.HexColor("#F7FAFC")        # Soft grey
    border_color = colors.HexColor("#E2E8F0")    # Border line color
    
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=32,
        leading=38,
        textColor=primary_color,
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=16,
        leading=22,
        textColor=secondary_color,
        spaceAfter=30
    )
    
    h1_style = ParagraphStyle(
        'Header1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=primary_color,
        spaceBefore=18,
        spaceAfter=10,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'Header2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=secondary_color,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14.5,
        textColor=text_color,
        spaceAfter=8
    )
    
    body_bold = ParagraphStyle(
        'BodyDarkBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    bullet_style = ParagraphStyle(
        'BulletText',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=5
    )
    
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white
    )
    
    table_body_style = ParagraphStyle(
        'TableBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=text_color
    )
    
    table_body_bold = ParagraphStyle(
        'TableBodyBold',
        parent=table_body_style,
        fontName='Helvetica-Bold'
    )
    
    callout_style = ParagraphStyle(
        'Callout',
        parent=body_style,
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#2C5282")
    )
    
    story = []
    
    # ------------------ COVER PAGE ------------------
    story.append(Spacer(1, 100))
    story.append(Paragraph("MEDISOURCE AI", title_style))
    story.append(Paragraph("Hospital Procurement Automation & Intelligence Platform", subtitle_style))
    
    # Decorative line
    line_data = [[""]]
    line_table = Table(line_data, colWidths=[504], rowHeights=[4])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), secondary_color),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 20))
    
    intro_summary = (
        "This document details the architecture, design choices, microservices integration, "
        "and systemic fallbacks of the MediSource AI platform. Built specifically for the "
        "healthcare supply chain, the platform automates document ingestion, supplier onboarding, "
        "multi-level financial approvals, expiration-aware inventory management, contract "
        "lifecycle generation, and automated risk scoring."
    )
    story.append(Paragraph(intro_summary, body_style))
    story.append(Spacer(1, 150))
    
    # Meta Details Table
    meta_data = [
        [Paragraph("Document Type:", table_body_bold), Paragraph("Technical & Functional Architecture Guide", table_body_style)],
        [Paragraph("Target Domain:", table_body_bold), Paragraph("Healthcare Supply Chain & Procurement Operations", table_body_style)],
        [Paragraph("Status:", table_body_bold), Paragraph("Implementation Phase Complete (Docker Ready)", table_body_style)],
        [Paragraph("Created Date:", table_body_bold), Paragraph("August 5, 2026", table_body_style)],
        [Paragraph("Platform Version:", table_body_bold), Paragraph("v1.0.0 (FastAPI / React SPA)", table_body_style)]
    ]
    t_meta = Table(meta_data, colWidths=[120, 384])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), light_bg),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 1, border_color),
        ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
    ]))
    story.append(t_meta)
    
    story.append(PageBreak())
    
    # ------------------ SECTION 1: TECH STACK IN LAYMAN'S TERMS ------------------
    story.append(Paragraph("1. Technology Stack in Layman's Terms", h1_style))
    story.append(Paragraph(
        "A modern enterprise web application has many moving parts. Rather than a single monolithic "
        "program, MediSource AI is built as a <b>Microservice Architecture</b> (meaning the application "
        "is split into 6 specialized mini-servers). Here is what each piece of technology does in simple terms:",
        body_style
    ))
    
    tech_data = [
        [Paragraph("Technology", table_header_style), Paragraph("Layman's Description & Role", table_header_style)],
        [Paragraph("<b>FastAPI</b>", table_body_style), Paragraph("The <i>engine room</i> of each microservice. It is a lightweight, super-fast framework that runs the server code and handles inputs and outputs (APIs).", table_body_style)],
        [Paragraph("<b>React & Bootstrap</b>", table_body_style), Paragraph("The <i>visual dashboard</i>. This is the web page that the hospital staff sees, clicks, and interacts with in their browser.", table_body_style)],
        [Paragraph("<b>Nginx (API Gateway)</b>", table_body_style), Paragraph("The <i>front-gate security guard</i>. It receives all incoming website traffic at http://localhost. It displays the React dashboard to users and routes any '/api/...' request to the correct microservice.", table_body_style)],
        [Paragraph("<b>PostgreSQL</b>", table_body_style), Paragraph("The <i>secured file rooms</i>. Under the 'Database-per-Service' rule, each service has its own separate database. Services never touch each other's database files directly, maintaining data isolation.", table_body_style)],
        [Paragraph("<b>Apache Kafka</b>", table_body_style), Paragraph("The <i>internal mail delivery system</i>. When a service finishes a task (like approving an invoice), it leaves a note (event) in Kafka. Other services listening for that note pick it up and do their job. This keeps services loosely coupled.", table_body_style)],
        [Paragraph("<b>Temporal</b>", table_body_style), Paragraph("The <i>executive assistant</i>. It handles long-running workflows that span days or weeks. If an invoice needs 3 managers to sign off, Temporal sends notifications, tracks deadlines, and escalates to the next manager if a deadline is missed.", table_body_style)],
        [Paragraph("<b>Open Policy Agent (OPA)</b>", table_body_style), Paragraph("The <i>official rulebook</i>. When an invoice comes in, OPA checks the hospital rules (e.g., 'If spend > $10,000, we need the CFO to approve') to decide the exact approval chain.", table_body_style)],
        [Paragraph("<b>Redis</b>", table_body_style), Paragraph("The <i>digital reservation sticky-notes</i>. It temporarily locks items (like reserving 100 boxes of gloves) while an order is being placed, preventing two departments from ordering the exact same physical items at the same instant.", table_body_style)],
        [Paragraph("<b>MinIO</b>", table_body_style), Paragraph("The <i>document warehouse</i>. An open-source, private version of Amazon S3. It stores actual files, such as PDFs of vendor invoices and finalized supply agreements.", table_body_style)],
        [Paragraph("<b>scikit-learn & MLflow</b>", table_body_style), Paragraph("The <i>artificial intelligence analyst</i>. It runs risk-prediction models on suppliers (e.g., probability of late delivery or fraud) and tracks model experiments in MLflow.", table_body_style)],
    ]
    t_tech = Table(tech_data, colWidths=[130, 374])
    t_tech.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
        ('BOX', (0,0), (-1,-1), 1, border_color),
        ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_bg])
    ]))
    story.append(t_tech)
    story.append(Spacer(1, 10))
    
    story.append(PageBreak())
    
    # ------------------ SECTION 2: THE 6 INTELLIGENCE AGENTS (SERVICES) & FALLBACKS ------------------
    story.append(Paragraph("2. Microservices & Robust Fallbacks", h1_style))
    story.append(Paragraph(
        "Each of the six services functions as a specialized 'agent' focused on a single business domain. "
        "To ensure the system works reliably even when external components or databases fail, several "
        "fault-tolerance fallbacks have been built in:",
        body_style
    ))
    
    # Service 1
    story.append(Paragraph("A. Document Intelligence Service (Port 8001)", h2_style))
    story.append(Paragraph(
        "<b>Role:</b> Ingests PDF or image documents (invoices, purchase orders, quotes) uploaded by vendors "
        "or staff. It uses OpenCV to clean up scans (denoising, grayscaling, straightening) and PaddleOCR "
        "to extract written text into structured data (vendor name, invoice number, items, taxes, totals).",
        body_style
    ))
    story.append(Paragraph(
        "<b>Fallback & Resilience:</b> Text extraction is rarely 100% perfect. For every invoice, the service "
        "calculates an <i>average confidence score</i>. If the text extraction confidence falls below 75% or "
        "crucial fields (like 'Total Due') are missing, the system does not fail or reject the document. "
        "Instead, it flags the document for manual review and pushes it to a <i>Human-in-the-Loop Review Queue</i>. "
        "Hospital staff can then review the original side-by-side with the extraction and make manual corrections.",
        body_style
    ))
    
    # Service 2
    story.append(Paragraph("B. Vendor Intelligence Service (Port 8002)", h2_style))
    story.append(Paragraph(
        "<b>Role:</b> Manages onboarding and profiles for medical suppliers, pharmaceutical distributors, and equipment engineers. "
        "It validates tax IDs (GST), regulatory drug licenses, and CDSCO/FDA registrations.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Fallback & Resilience:</b> The service contains a built-in validation rules engine. If an external "
        "license registry is offline or a watchlist lookup returns an error, the system does not crash or automatically block "
        "the vendor. Instead, it marks the validation as 'Under review' and moves the vendor profile to 'Pending Verification', "
        "notifying operators to manually approve or request further documents.",
        body_style
    ))
    
    # Service 3
    story.append(Paragraph("C. Approval Workflow Service (Port 8003)", h2_style))
    story.append(Paragraph(
        "<b>Role:</b> Governs the financial sign-off flow. It sends the purchase request details to Open Policy Agent (OPA), "
        "which calculates the required chain of human approvers (e.g. Ward Supervisor -> Department Head -> CFO). It then starts a "
        "Temporal workflow engine to track the sign-off steps.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Fallback & Resilience:</b> If a hospital manager goes on vacation or forgets to click 'Approve', "
        "Temporal tracks the SLA deadline. On a timeout event (e.g., no action in 48 hours), Temporal triggers a fallback "
        "escalation mechanism, automatically rerouting the approval to the next-in-line supervisor or raising an alert. "
        "Redis is also used to prevent double-submissions, ensuring rapid double-clicks do not create duplicate workflows.",
        body_style
    ))
    
    story.append(PageBreak())
    
    # Service 4
    story.append(Paragraph("D. Inventory Intelligence Service (Port 8004)", h2_style))
    story.append(Paragraph(
        "<b>Role:</b> Tracks clinical stock. When a procurement request is approved, this service reserves stock units "
        "automatically. It is specifically built for healthcare: it separates inventory by <i>expiration dates</i> and "
        "<i>cold-chain requirements</i> (such as vaccines needing strict refrigeration).",
        body_style
    ))
    story.append(Paragraph(
        "<b>Fallback & Resilience:</b> To prevent two departments from reserving the exact same box of scarce medicine "
        "simultaneously, the service uses a <i>Redis Distributed Lock</i>. If the lock is held, a process will retry gracefully. "
        "If stock is unavailable, it automatically switches from a 'Reserved' status to a 'Backorder/Reorder' recommendation, "
        "sending notifications for replenishment without halting the system.",
        body_style
    ))
    
    # Service 5
    story.append(Paragraph("E. Contract Intelligence Service (Port 8005)", h2_style))
    story.append(Paragraph(
        "<b>Role:</b> Auto-populates Jinja2 contract templates (Supply Agreements, Equipment AMCs) using vendor and approval "
        "data. It converts these to signed digital contracts and pushes them to OpenSign.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Fallback & Resilience:</b> OpenSign is an external e-signature service. If the OpenSign service is offline or "
        "fails to respond, the contract service falls back to a <i>Local Simulation Mode</i> (a fallback signature mock flow). "
        "This allows the testing and sandbox environments to progress with signature status updates immediately instead of failing. "
        "In production, failed webhook notifications are queued for retry in database state machines.",
        body_style
    ))
    
    # Service 6
    story.append(Paragraph("F. Risk Intelligence Service (Port 8006)", h2_style))
    story.append(Paragraph(
        "<b>Role:</b> Evaluates vendors using a Machine Learning gradient-boosted classifier. It predicts probability scores "
        "across five dimensions: Compliance, Fraud, Financial health, Supplier reliability, and Operational delivery. "
        "Experiments are logged directly into MLflow.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Fallback & Resilience:</b> If the MLflow server is down or the pickled ML model file fails to load at startup, "
        "the service gracefully falls back to a <i>Deterministic Rule-Based Risk Engine</i>. It computes fallback scores using "
        "historical data points (e.g. number of late deliveries and days until license expiry), ensuring risk scoring remains active.",
        body_style
    ))
    
    story.append(PageBreak())
    
    # ------------------ SECTION 3: SYSTEM INTERCONNECTIONS & EVENT FLOW ------------------
    story.append(Paragraph("3. Connections & System Integration Flow", h1_style))
    story.append(Paragraph(
        "The microservices communicate using two distinct channels: <b>Synchronous API calls</b> "
        "(direct HTTP request/response for user interfaces) and <b>Asynchronous Event Pub/Sub</b> "
        "(via Apache Kafka for backend actions). Here is how a document travels through the system:",
        body_style
    ))
    
    flow_steps = [
        ("Step 1: Document Upload", "A user uploads an invoice. Nginx forwards the file to the Document Intelligence service. The file is saved in MinIO, OCR is run, and the extracted data is saved in PostgreSQL."),
        ("Step 2: Processed Event", "The Document Intelligence service publishes a <i>documents.processed</i> event to Kafka. The Vendor Intelligence and Approval Workflow services are listening for this event."),
        ("Step 3: Vendor & Approval Setup", "Vendor Intelligence updates the supplier profile. Approval Workflow uses OPA to determine the approval routing, writes a record to its PostgreSQL database, and starts a Temporal tracker."),
        ("Step 4: Human Approval", "The approver views the request on the React frontend (proxied via Nginx) and clicks 'Approve'. This signals the Temporal workflow, which fires an <i>approval.approved</i> event to Kafka."),
        ("Step 5: Reservation & Contract", "Inventory Intelligence consumes the approval event and reserves stock in PostgreSQL using a Redis lock. Contract Intelligence consumes the approval event, generates a contract document in MinIO, and triggers an e-signature envelope via OpenSign."),
        ("Step 6: Risk Analysis", "Risk Intelligence performs compliance/fraud scoring. If a contract is high-risk, it publishes a <i>risk.assessed</i> event to notify managers and block automated execution.")
    ]
    
    for title, desc in flow_steps:
        story.append(Paragraph(f"• <b>{title}</b>: {desc}", bullet_style))
    
    story.append(Spacer(1, 15))
    
    # Architecture Summary Callout
    callout_data = [[
        Paragraph(
            "<b>Architecture Summary:</b> This combination of direct HTTP gateways (Nginx) and decoupled event queues "
            "(Kafka) ensures that even if one service crashes (e.g., Risk Intelligence is temporarily down), "
            "users can still upload invoices and view dashboards. The system is resilient to individual service failures.",
            callout_style
        )
    ]]
    t_callout = Table(callout_data, colWidths=[504])
    t_callout.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EBF8FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#BEE3F8")),
        ('PADDING', (0,0), (-1,-1), 12),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_callout)
    
    story.append(PageBreak())
    
    # ------------------ SECTION 4: LOCAL DEVELOPMENT & DEPLOYMENT ------------------
    story.append(Paragraph("4. Running the Codebase (Docker Setup)", h1_style))
    story.append(Paragraph(
        "To run this codebase locally without having to install and link Postgres, Kafka, OPA, and Temporal manually, "
        "you should use the provided Docker Compose files.",
        body_style
    ))
    
    story.append(Paragraph("Prerequisites:", h2_style))
    story.append(Paragraph("• <b>Docker Desktop:</b> Ensure Docker Desktop is installed and running on your Windows host.", bullet_style))
    story.append(Paragraph("• <b>Python:</b> Python 3.x on your PATH to run the mock seed data script.", bullet_style))
    
    story.append(Paragraph("Deployment Instructions:", h2_style))
    story.append(Paragraph("1. Open a PowerShell terminal in the root directory.", bullet_style))
    story.append(Paragraph("2. Run the deployment script:", bullet_style))
    story.append(Paragraph("   <font face='Courier'>.\\scripts\\deploy.ps1</font>", bullet_style))
    story.append(Paragraph("   This script creates your config files, starts all 16 Docker containers, waits for core databases to become healthy, sets up the Kafka topics, runs SQL database migrations, and installs requests/reportlab libraries to inject dummy healthcare records.", bullet_style))
    story.append(Paragraph("3. Open your browser and navigate to <b>http://localhost</b> to interact with the frontend.", bullet_style))
    
    story.append(Spacer(1, 15))
    
    # Service Endpoints Table
    endpoints_data = [
        [Paragraph("Console / Service Name", table_header_style), Paragraph("Address / Port", table_header_style), Paragraph("Description", table_header_style)],
        [Paragraph("<b>Web Frontend Dashboard</b>", table_body_style), Paragraph("http://localhost", table_body_style), Paragraph("Main UI dashboard for all microservices.", table_body_style)],
        [Paragraph("<b>Temporal Dashboard</b>", table_body_style), Paragraph("http://localhost:8088", table_body_style), Paragraph("Monitor approval workflows and timers.", table_body_style)],
        [Paragraph("<b>MLflow Console</b>", table_body_style), Paragraph("http://localhost:5000", table_body_style), Paragraph("Track ML training, parameters, and model registry.", table_body_style)],
        [Paragraph("<b>MinIO Storage Console</b>", table_body_style), Paragraph("http://localhost:9001", table_body_style), Paragraph("Explore raw uploaded PDFs and generated contracts.", table_body_style)],
        [Paragraph("<b>OPA Engine REST</b>", table_body_style), Paragraph("http://localhost:8181", table_body_style), Paragraph("Rules engine endpoints for evaluation.", table_body_style)]
    ]
    t_end = Table(endpoints_data, colWidths=[150, 150, 204])
    t_end.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 1, border_color),
        ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_bg])
    ]))
    story.append(t_end)
    
    story.append(Spacer(1, 40))
    story.append(Paragraph("<b>End of Report</b>", ParagraphStyle('CenterBold', parent=body_style, fontName='Helvetica-Bold', alignment=1)))
    
    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)

if __name__ == "__main__":
    build_pdf()
    print("PDF Generated successfully.")
