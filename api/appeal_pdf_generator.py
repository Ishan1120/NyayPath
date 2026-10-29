import os
import io
import logging
from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors

logger = logging.getLogger(__name__)

def generate_first_appeal_pdf(
    appellant_name: str,
    appellant_address: str,
    first_appellate_authority: str,
    pio_address: str,
    rti_registration_no: str,
    rti_filing_date: str,
    pio_reply_date: Optional[str],
    grounds_of_appeal: str,
    legal_precedent: str
) -> bytes:
    """
    Generates a statutory First Appeal document (PDF) under Section 19(1) of the RTI Act, 2005.
    Includes grounds for appeal, statutory precedents, and penalty warnings.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        alignment=TA_CENTER,
        spaceAfter=12
    )

    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
        spaceAfter=18
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        alignment=TA_JUSTIFY,
        spaceAfter=8
    )

    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    story = []

    # Document Header
    story.append(Paragraph("BEFORE THE FIRST APPELLATE AUTHORITY", title_style))
    story.append(Paragraph("(Under Section 19(1) of the Right to Information Act, 2005)", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceAfter=14))

    # Parties Metadata
    story.append(Paragraph(f"<b>To:</b><br/>{first_appellate_authority}<br/>{pio_address}", body_style))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>From (Appellant):</b><br/>{appellant_name}<br/>{appellant_address}", body_style))
    story.append(Spacer(1, 12))

    # Subject Line
    story.append(Paragraph(
        f"<b>SUBJECT:</b> FIRST APPEAL UNDER SECTION 19(1) OF RTI ACT AGAINST PIO DECISION / DEEMED REFUSAL (Ref No: {rti_registration_no})",
        bold_style
    ))
    story.append(Spacer(1, 10))

    # Section 1: Original Particulars
    story.append(Paragraph("<b>1. PARTICULARS OF THE ORIGINAL RTI APPLICATION:</b>", bold_style))
    story.append(Paragraph(f"• <b>Application Ref No / Case ID:</b> {rti_registration_no}", body_style))
    story.append(Paragraph(f"• <b>Date of Original RTI Filing:</b> {rti_filing_date}", body_style))
    story.append(Paragraph(f"• <b>Date of PIO Reply (if received):</b> {pio_reply_date or 'N/A (Deemed Refusal under Section 7(2))'}", body_style))
    story.append(Spacer(1, 8))

    # Section 2: Grounds of Appeal
    story.append(Paragraph("<b>2. GROUNDS FOR APPEAL:</b>", bold_style))
    story.append(Paragraph(grounds_of_appeal, body_style))
    story.append(Spacer(1, 8))

    # Section 3: Legal Precedents & CIC Rulings
    story.append(Paragraph("<b>3. RELEVANT CIC PRECEDENTS & STATUTORY PROVISIONS:</b>", bold_style))
    story.append(Paragraph(legal_precedent, body_style))
    story.append(Spacer(1, 8))

    # Section 4: Prayer / Relief
    story.append(Paragraph("<b>4. PRAYER / RELIEF SOUGHT:</b>", bold_style))
    relief_text = (
        "In light of the statutory mandates and legal precedents detailed above, the Appellant respectfully prays that the First Appellate Authority:<br/>"
        "a) Direct the PIO to immediately supply the complete, unredacted information free of charge as per Section 7(6) of the RTI Act.<br/>"
        "b) Recommend penal action under Section 20(1) against the concerned PIO for willful default or unreasonable delay.<br/>"
        "c) Grant the Appellant an opportunity for a personal or virtual hearing before deciding this appeal."
    )
    story.append(Paragraph(relief_text, body_style))
    story.append(Spacer(1, 16))

    # Section 5: Verification & Signature
    story.append(Paragraph("<b>VERIFICATION:</b>", bold_style))
    story.append(Paragraph(
        "I, the Appellant named above, do hereby verify that the contents of this First Appeal are true, correct, and based on official records to the best of my knowledge and belief.",
        body_style
    ))
    story.append(Spacer(1, 24))

    story.append(Paragraph("<b>Signature of Appellant:</b> ___________________________", body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
