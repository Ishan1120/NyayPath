"""
JanAdhikar Case Brief PDF Generator
Compiles court-ready, 1-page structured Judicial Case Brief PDFs using ReportLab.
Includes Presiding Bench, Hearing Directives, Binding Legal Ratio, and Quotable Citations.
"""

import io
import html
from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib import colors

def clean_pdf_text(text: Optional[str]) -> str:
    """Escapes special characters for ReportLab XML flowables."""
    if not text:
        return ""
    safe = html.escape(str(text))
    # Preserve linebreaks
    safe = safe.replace("\n", "<br/>")
    return safe

def generate_precedent_case_brief_pdf(case: Dict[str, Any]) -> bytes:
    """
    Compiles a formal 1-page Judicial Case Brief PDF for advocates and citizens.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#7F1D1D')
    )

    sub_header_style = ParagraphStyle(
        'SubHeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#475569')
    )

    case_title_style = ParagraphStyle(
        'CaseTitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#0F172A')
    )

    citation_style = ParagraphStyle(
        'CitationStyle',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=9.5,
        leading=12,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#991B1B')
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#1E293B')
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor('#334155')
    )

    directive_style = ParagraphStyle(
        'DirectiveStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#0F172A')
    )

    quote_style = ParagraphStyle(
        'QuoteStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor('#451A03')
    )

    elements = []

    # 1. Header Banner
    elements.append(Paragraph("JANADHIKAR JUDICIAL PRECEDENT REPOSITORY", header_style))
    elements.append(Paragraph("COURT-READY ADVOCATE CASE BRIEF &amp; STATUTORY RATIO LEDGER", sub_header_style))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#991B1B'), spaceAfter=12))

    # 2. Case Title & Law Report Citation
    elements.append(Paragraph(clean_pdf_text(case.get("title", "Judicial Precedent")), case_title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"Official Citation: {clean_pdf_text(case.get('citation', ''))}", citation_style))
    elements.append(Spacer(1, 8))

    # 3. Meta Table (Court, Presiding Bench, Hearing Date, Category)
    meta_data = [
        [
            Paragraph("<b>Forum / Court:</b>", section_heading),
            Paragraph(clean_pdf_text(case.get("court", "Supreme Court of India")), body_style),
            Paragraph("<b>Hearing / Decision:</b>", section_heading),
            Paragraph(clean_pdf_text(case.get("hearing_date", "Landmark Order")), body_style)
        ],
        [
            Paragraph("<b>Presiding Bench:</b>", section_heading),
            Paragraph(clean_pdf_text(case.get("bench", "Hon'ble Division Bench")), body_style),
            Paragraph("<b>Legal Category:</b>", section_heading),
            Paragraph(clean_pdf_text(case.get("category", "Constitutional")), body_style)
        ]
    ]

    meta_table = Table(meta_data, colWidths=[90, 160, 95, 155])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10))

    # 4. Dispute Background & Facts
    elements.append(Paragraph("1. BACKGROUND &amp; DISPUTE FACTS", section_heading))
    elements.append(Paragraph(clean_pdf_text(case.get("facts", case.get("summary", ""))), body_style))
    elements.append(Spacer(1, 9))

    # 5. Operative Court Hearing & Directives (Boxed Table)
    directives_text = case.get("court_hearing_and_directions", "Court scrutinized administrative submissions and granted binding relief.")
    directives_flowable = Paragraph(clean_pdf_text(directives_text), directive_style)
    
    directive_box = Table(
        [
            [Paragraph("<b>OPERATIVE COURT HEARING &amp; BENCH DIRECTIVES (WHAT COURT GAVE):</b>", section_heading)],
            [directives_flowable]
        ],
        colWidths=[500]
    )
    directive_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF1F2')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#FECDD3')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(directive_box)
    elements.append(Spacer(1, 10))

    # 6. Binding Legal Ratio (Ratio Decidendi)
    elements.append(Paragraph("2. RATIO DECIDENDI (BINDING LEGAL PRECEDENT)", section_heading))
    elements.append(Paragraph(f"&ldquo;{clean_pdf_text(case.get('key_ratio', ''))}&rdquo;", quote_style))
    elements.append(Spacer(1, 9))

    # 7. Statutory Citation Snippet (How to Cite)
    cite_box = Table(
        [
            [Paragraph("<b>STATUTORY CITATION FOR RTI / FIRST APPEAL / LEGAL NOTICE:</b>", section_heading)],
            [Paragraph(f"&ldquo;{clean_pdf_text(case.get('how_to_cite', ''))}&rdquo;", body_style)]
        ],
        colWidths=[500]
    )
    cite_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEFCE8')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#FEF08A')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(cite_box)
    elements.append(Spacer(1, 10))

    # 8. Statutory Sections Tag Row
    sections = ", ".join(case.get("statutory_sections", []))
    elements.append(Paragraph(f"<b>Applicable Statutory Sections:</b> {clean_pdf_text(sections)}", body_style))
    elements.append(Spacer(1, 12))

    # 9. Verification & Stamp Footer
    elements.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor('#CBD5E1'), spaceAfter=6))
    footer_text = "Verified from Indian Judicial Archives • Generated via JanAdhikar Legal Engine • Admissible for legal citation in public filings."
    elements.append(Paragraph(footer_text, sub_header_style))

    doc.build(elements)
    return buffer.getvalue()

