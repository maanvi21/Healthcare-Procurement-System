"""Render template HTML into an auditable PDF with an explicit signature page."""
from html.parser import HTMLParser
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
from xml.sax.saxutils import escape


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "h1", "h2", "h3", "li", "br", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"p", "h1", "h2", "h3", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def render_contract_pdf(document_html: str, vendor_name: str) -> tuple[bytes, int]:
    """Return PDF bytes and the 1-based page containing the signature widget."""
    parser = _TextExtractor()
    parser.feed(document_html)
    text = "".join(parser.parts)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("ContractBody", parent=styles["BodyText"], leading=15, spaceAfter=8)
    heading = ParagraphStyle("ContractHeading", parent=styles["Heading1"], alignment=TA_CENTER, textColor=colors.HexColor("#17324d"), spaceAfter=18)
    signature = ParagraphStyle("SignatureTitle", parent=styles["Heading2"], alignment=TA_CENTER, spaceAfter=24)
    story = [Paragraph("MEDISOURCE PROCUREMENT CONTRACT", heading), Spacer(1, 8)]
    for line in (line.strip() for line in text.splitlines()):
        if not line:
            continue
        safe_line = escape(line)
        if line.isupper() and len(line) < 100:
            story.append(Paragraph(safe_line, styles["Heading2"]))
        else:
            story.append(Paragraph(safe_line, body))
    story.extend([
        PageBreak(),
        Paragraph("Electronic Signature", signature),
        Paragraph("Please review the agreement and apply your digital signature in the marked field.", body),
        Spacer(1, 1.2 * inch),
        Paragraph(f"Supplier: {escape(vendor_name or 'Supplier')}", body),
        Spacer(1, 0.65 * inch),
        Paragraph("Authorized supplier signature", body),
        Spacer(1, 0.45 * inch),
        Paragraph("Signing and completion are recorded by the electronic-signature provider.", styles["Italic"]),
    ])
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter, rightMargin=0.8*inch, leftMargin=0.8*inch, topMargin=0.7*inch, bottomMargin=0.7*inch)
    doc.build(story)
    # Signature page is deliberately forced after the terms; it is always the final page.
    page_count = doc.canv.getPageNumber() - 1
    return output.getvalue(), page_count
