import io
from html import escape

import pytesseract
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from rules.catalog import FOOD_DOMESTIC_PROFILE, evaluate_rules, extract_declarations

app = FastAPI()

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReportRequest(BaseModel):
    filename: str
    compliance: dict
    declarations: dict
    rule_checks: list


@app.get("/")
def read_root():
    return {"message": "ReguLens backend is running"}


@app.post("/analyze")
async def analyze_label(image: UploadFile = File(...)):
    allowed_types = {"image/jpeg", "image/png"}

    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Please upload a JPG or PNG image.",
        )

    image_bytes = await image.read()

    try:
        opened_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        extracted_text = pytesseract.image_to_string(opened_image).strip()
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file could not be read as an image.",
        )

    declarations = extract_declarations(extracted_text)

    rule_checks, compliance = evaluate_rules(
        FOOD_DOMESTIC_PROFILE,
        declarations,
        opened_image.size,
    )

    missing_fields = [
        rule["title"]
        for rule in rule_checks
        if rule["status"] == "Potential violation"
    ]

    return {
        "filename": image.filename,
        "profile": FOOD_DOMESTIC_PROFILE["name"],
        "message": "OCR analysis completed.",
        "extracted_text": extracted_text,
        "declarations": declarations,
        "missing_fields": missing_fields,
        "compliance": compliance,
        "rule_checks": rule_checks,
    }


def corrective_action(rule_id):
    actions = {
        "R6_A": "Add the responsible manufacturer, packer, or importer name and complete postal address.",
        "R6_B": "Add the common or generic name of the commodity.",
        "R6_C": "Add net quantity using an appropriate standard unit, such as g, kg, ml, or L.",
        "R6_D": "Add the month and year of manufacture, packing, or import.",
        "R6_E": "Declare MRP and include the words 'inclusive of all taxes'.",
        "R6_2": "Add consumer-care name/address and a phone number or email address.",
        "FOOD_01": "Add a best-before or use-by declaration for the food product.",
        "R7": "Verify minimum font and numeral height using the package dimensions.",
        "R8": "Verify that declarations appear on the principal display panel.",
    }

    return actions.get(rule_id, "Review this declaration against the applicable rule.")

@app.post("/report")
async def generate_report(report: ReportRequest):
    buffer = io.BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReguLensTitle",
        parent=styles["Title"],
        textColor=colors.HexColor("#167548"),
        fontSize=23,
        spaceAfter=12,
    )

    small_style = ParagraphStyle(
        "SmallText",
        parent=styles["BodyText"],
        fontSize=8,
        leading=10,
    )

    story = [
        Paragraph("ReguLens Compliance Report", title_style),
        Paragraph(
            f"<b>Image analyzed:</b> {escape(report.filename)}",
            styles["BodyText"],
        ),
        Spacer(1, 10),
        Paragraph("Inspection Summary", styles["Heading2"]),
        Paragraph(
            f"<b>Assessment:</b> {escape(report.compliance['status'])}",
            styles["BodyText"],
        ),
        Paragraph(
            f"<b>Automated compliance score:</b> {report.compliance['score']}/100",
            styles["BodyText"],
        ),
        Paragraph(
            escape(report.compliance["message"]),
            styles["BodyText"],
        ),
        Spacer(1, 12),
    ]

    potential_violations = [
        rule
        for rule in report.rule_checks
        if rule["status"] == "Potential violation"
    ]

    if potential_violations:
        story.append(Paragraph("Potential Violations and Required Fixes", styles["Heading2"]))

        violation_rows = [[
            Paragraph("<b>Rule</b>", small_style),
            Paragraph("<b>What failed</b>", small_style),
            Paragraph("<b>Evidence</b>", small_style),
            Paragraph("<b>Required correction</b>", small_style),
        ]]

        for rule in potential_violations:
            violation_rows.append([
                Paragraph(escape(rule["reference"]), small_style),
                Paragraph(escape(rule["title"]), small_style),
                Paragraph(escape(rule["evidence"]), small_style),
                Paragraph(escape(corrective_action(rule["rule_id"])), small_style),
            ])

        violation_table = Table(
            violation_rows,
            colWidths=[28 * mm, 43 * mm, 37 * mm, 67 * mm],
            repeatRows=1,
        )

        violation_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#A12A2A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#F0B4B4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FFF0F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )

        story.append(violation_table)
        story.append(Spacer(1, 12))

    review_items = [
        rule
        for rule in report.rule_checks
        if rule["status"] == "Needs review"
    ]

    if review_items:
        story.append(Paragraph("Manual Review Required", styles["Heading2"]))

        review_rows = [[
            Paragraph("<b>Rule</b>", small_style),
            Paragraph("<b>Check</b>", small_style),
            Paragraph("<b>Inspector action</b>", small_style),
        ]]

        for rule in review_items:
            review_rows.append([
                Paragraph(escape(rule["reference"]), small_style),
                Paragraph(escape(rule["title"]), small_style),
                Paragraph(escape(rule["reason"]), small_style),
            ])

        review_table = Table(
            review_rows,
            colWidths=[35 * mm, 60 * mm, 80 * mm],
            repeatRows=1,
        )

        review_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#805500")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EAC96D")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FFF7DF")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )

        story.append(review_table)
        story.append(Spacer(1, 12))

    story.append(Paragraph("Extracted Declarations", styles["Heading2"]))

    declaration_rows = [[
        Paragraph("<b>Declaration</b>", styles["BodyText"]),
        Paragraph("<b>Detected value</b>", styles["BodyText"]),
    ]]

    for field_name, value in report.declarations.items():
        declaration_rows.append([
            Paragraph(escape(field_name), styles["BodyText"]),
            Paragraph(escape(value or "Not detected"), styles["BodyText"]),
        ])

    declaration_table = Table(
        declaration_rows,
        colWidths=[65 * mm, 110 * mm],
        repeatRows=1,
    )

    declaration_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#167548")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CFE0D4")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F5FBF7")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])
    )

    story.append(declaration_table)
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "Note: This is an automated screening report. Potential violations require review by an authorised inspector.",
            small_style,
        )
    )

    document.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=regulens-compliance-report.pdf"
        },
    )