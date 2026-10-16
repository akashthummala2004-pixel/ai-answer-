"""Client-ready PDF report for Smart Verification records (ReportLab)."""

import io
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from app.services.smart.record import ASSESSMENT_LABELS, effective_assessment

LOGO = Path(__file__).resolve().parents[2] / "assets" / "mindmasters-logo.png"

NAVY = colors.HexColor("#1f2d3d")
INK = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748b")
LINE = colors.HexColor("#e2e8f0")
SOFT = colors.HexColor("#f8fafc")
BRAND = colors.HexColor("#3d8a5f")

ASSESSMENT_COLORS = {
    "supported_by_evidence": ("#166534", "#dcfce7"),
    "contradicted_by_evidence": ("#991b1b", "#fee2e2"),
    "not_independently_verified": ("#334155", "#e2e8f0"),
    "requires_human_review": ("#92400e", "#fef3c7"),
}
SEVERITY_COLORS = {"high": ("#991b1b", "#fee2e2"), "medium": ("#92400e", "#fef3c7"), "low": ("#334155", "#e2e8f0")}
RISK_TEXT = {"low": "Low", "moderate": "Moderate", "elevated": "Elevated", "high": "High"}
CONTENT_TYPES = {"ai_answer": "AI-generated answer", "email": "Email", "business_message": "Business message",
                 "document": "Document", "screenshot": "Screenshot", "web_content": "Web content", "other": "Other content"}

_REPLACEMENTS = {"₹": "INR ", "→": "->", "←": "<-", "✓": "v", "✗": "x"}


def safe(text: Any) -> str:
    """Escape for ReportLab markup and keep to characters the built-in fonts can draw."""
    s = str(text or "")
    for k, v in _REPLACEMENTS.items():
        s = s.replace(k, v)
    s = s.encode("cp1252", errors="replace").decode("cp1252")
    return escape(s).replace("\n", "<br/>")


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8, leading=11, textColor=MUTED),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.8, leading=12),
        "cellb": ParagraphStyle("cellb", parent=base, fontSize=8.8, leading=12, fontName="Helvetica-Bold", textColor=NAVY),
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=NAVY),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=NAVY,
                             spaceBefore=12, spaceAfter=6),
        "eyebrow": ParagraphStyle("eyebrow", parent=base, fontName="Helvetica-Bold", fontSize=8, leading=10,
                                  textColor=BRAND, alignment=TA_RIGHT),
        "meta": ParagraphStyle("meta", parent=base, fontSize=8.5, leading=12, textColor=MUTED, alignment=TA_RIGHT),
    }


def _pill(text: str, fg: str, bg: str, style: ParagraphStyle) -> Table:
    t = Table([[Paragraph(f'<font color="{fg}"><b>{safe(text)}</b></font>', style)]])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                           ("ROUNDEDCORNERS", [3, 3, 3, 3])]))
    return t


def _grid(rows: list[list[Any]], widths: list[float], header: bool = True) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), SOFT), ("LINEBELOW", (0, 0), (-1, 0), 0.8, BRAND)]
    t.setStyle(TableStyle(style))
    return t


def _input_labels(record: dict[str, Any]) -> dict[str, str]:
    labels = {}
    for i in record.get("inputs", []):
        labels[i["id"]] = {"text": "Submitted text", "pdf": f"Document: {i['name']}",
                           "scanned_pdf": f"Scanned document: {i['name']}", "image": f"Image: {i['name']}"}[i["kind"]]
    return labels


def render_pdf(record: dict[str, Any]) -> bytes:
    st = _styles()
    a = record["analysis"]
    labels = _input_labels(record)
    created = record.get("verified_at") or record.get("created_at") or ""
    try:
        created_text = datetime.fromisoformat(created).strftime("%d %B %Y, %H:%M UTC")
    except ValueError:
        created_text = created
    width = A4[0] - 36 * mm
    story: list[Any] = []

    # --- Header
    logo = Image(str(LOGO), width=46 * mm, height=46 * mm * 466 / 743) if LOGO.exists() else Spacer(1, 1)
    right = [Paragraph("VERIFICATION REPORT", st["eyebrow"]), Spacer(1, 4),
             Paragraph(f"<b>{safe(record['title'])}</b>", ParagraphStyle("t", parent=st["h1"], alignment=TA_RIGHT, fontSize=14, leading=18)),
             Spacer(1, 4), Paragraph(f"{safe(created_text)}<br/>Verification ID: {safe(record['id'])}", st["meta"])]
    head = Table([[logo, right]], colWidths=[52 * mm, width - 52 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 1.6, BRAND),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story += [head, Spacer(1, 10)]

    # --- Submitted content
    inputs = []
    for i in record.get("inputs", []):
        if i["kind"] == "text":
            inputs.append(f"Text ({i['chars']:,} characters)")
        else:
            pages = f", {i['pages']} page(s)" if i.get("pages") else ""
            inputs.append(f"{labels[i['id']]} ({i['size'] / 1024:,.0f} KB{pages})")
    story.append(Paragraph("Submitted content", st["h2"]))
    box = Table([[Paragraph(f"<b>Content type:</b> {safe(CONTENT_TYPES.get(a['content_type'], 'Other'))}<br/>"
                            f"<b>Inputs:</b> {safe('; '.join(inputs))}<br/><br/>{safe(a['summary'])}", st["base"])]],
                colWidths=[width])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                             ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.append(box)

    # --- Overall assessment
    risk = a["risk_level"]
    fg, bg = {"low": ("#166534", "#dcfce7"), "moderate": ("#334155", "#e2e8f0"), "elevated": ("#92400e", "#fef3c7"),
              "high": ("#991b1b", "#fee2e2")}[risk]
    story.append(Paragraph("Overall assessment", st["h2"]))
    story.append(Table([[_pill(f"Warning-sign level: {RISK_TEXT[risk]}", fg, bg, st["cell"]),
                         Paragraph("Reflects warning signs found by the AI review, not proof of wrongdoing.", st["small"])]],
                       colWidths=[52 * mm, width - 52 * mm], style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                                                     ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [Spacer(1, 6), Paragraph(safe(a["overall_assessment"]), st["base"])]

    # --- Key findings
    if a["key_findings"] or a.get("detected_details"):
        story.append(Paragraph("Key findings", st["h2"]))
    if a["key_findings"]:
        with_source = any(f.get("source") in labels for f in a["key_findings"])
        header = [Paragraph("<b>Finding</b>", st["cell"]), Paragraph("<b>Detail</b>", st["cell"])]
        rows = [header + ([Paragraph("<b>Source</b>", st["cell"])] if with_source else [])]
        for f in a["key_findings"]:
            row = [Paragraph(safe(f["label"]), st["cellb"]), Paragraph(safe(f["detail"]), st["cell"])]
            if with_source:
                row.append(Paragraph(safe(labels.get(f["source"], "-")), st["small"]))
            rows.append(row)
        widths = [38 * mm, width - 78 * mm, 40 * mm] if with_source else [42 * mm, width - 42 * mm]
        story.append(_grid(rows, widths))
    if a.get("detected_details"):
        story += [Spacer(1, 6), Paragraph("Details detected automatically in the content (pattern matching, not AI):", st["small"])]
        rows = [[Paragraph("<b>Type</b>", st["cell"]), Paragraph("<b>Value</b>", st["cell"]), Paragraph("<b>Source</b>", st["cell"])]]
        rows += [[Paragraph(safe(d["type"]), st["cell"]), Paragraph(safe(d["value"]), st["cell"]),
                  Paragraph(safe(labels.get(d["source"], "-")), st["small"])] for d in a["detected_details"]]
        story.append(_grid(rows, [32 * mm, width - 72 * mm, 40 * mm]))

    # --- Risks
    story.append(Paragraph("Potential risks", st["h2"]))
    if a["risks"]:
        rows = []
        for r in a["risks"]:
            fg, bg = SEVERITY_COLORS[r["severity"]]
            rows.append([_pill(r["severity"].capitalize(), fg, bg, st["small"]),
                         Paragraph(f"<b>{safe(r['title'])}</b><br/>{safe(r['detail'])}", st["cell"])])
        story.append(_grid(rows, [20 * mm, width - 20 * mm], header=False))
    else:
        story.append(Paragraph("No specific warning signs were identified in the submitted content.", st["base"]))

    # --- Claims
    story.append(Paragraph("Claim-by-claim analysis", st["h2"]))
    if record["claims"]:
        rows = [[Paragraph("<b>#</b>", st["cell"]), Paragraph("<b>Claim</b>", st["cell"]),
                 Paragraph("<b>Assessment</b>", st["cell"]), Paragraph("<b>Explanation and evidence</b>", st["cell"])]]
        for c in record["claims"]:
            shown = effective_assessment(c)
            fg, bg = ASSESSMENT_COLORS[shown]
            detail = safe(c["explanation"])
            for e in c.get("evidence", []):
                detail += f'<br/><font color="#166534"><b>Evidence ({safe(e["label"])}):</b></font> <i>"{safe(e["quote"])}"</i>'
            if c.get("review"):
                rv = c["review"]
                detail += ('<br/><font color="#3a6fb0"><b>Human review:</b></font> '
                           f'{safe(ASSESSMENT_LABELS.get(rv["verdict"], rv["verdict"]))}'
                           f'{" - " + safe(rv["note"]) if rv.get("note") else ""}'
                           f' (system assessment: {safe(ASSESSMENT_LABELS[c["assessment"]])})')
            rows.append([Paragraph(safe(c["id"]), st["small"]), Paragraph(safe(c["text"]), st["cell"]),
                         _pill(ASSESSMENT_LABELS[shown], fg, bg, st["small"]), Paragraph(detail, st["cell"])])
        story.append(_grid(rows, [9 * mm, 52 * mm, 34 * mm, width - 95 * mm]))
    else:
        story.append(Paragraph("The AI review did not identify discrete factual claims in the submitted content.", st["base"]))

    # --- Sources
    story.append(Paragraph("Supporting sources", st["h2"]))
    evidence = [(c["id"], e) for c in record["claims"] for e in c.get("evidence", [])]
    if evidence:
        for cid, e in evidence:
            story.append(Paragraph(f'<b>{safe(cid)}</b> - {safe(e["label"])}: <i>"{safe(e["quote"])}"</i>', st["base"]))
    else:
        story.append(Paragraph("No independent sources were available for this verification. Claims marked "
                               "Not Independently Verified have not been checked against external evidence.", st["base"]))

    # --- Next steps
    story.append(Paragraph("Recommended next steps", st["h2"]))
    for n, step in enumerate(a["next_steps"], 1):
        story.append(Paragraph(f"<b>{n}.</b> {safe(step)}", st["base"]))
        story.append(Spacer(1, 2))

    # --- Limitations
    lim = [Paragraph("<b>Verification limitations</b>", ParagraphStyle("lh", parent=st["base"], textColor=NAVY))]
    lim += [Paragraph(f"&bull; {safe(x)}", st["small"]) for x in record.get("limitations", [])]
    lim.append(Paragraph(f"&bull; Model: {safe(record.get('model'))}. Generated by Mind Masters AI Solutions "
                         "Answer Verification. This report records an AI-assisted assessment; it is not an "
                         "independent audit or certification.", st["small"]))
    box = Table([[lim]], colWidths=[width])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                             ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [Spacer(1, 14), KeepTogether([box])]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 9.5 * mm, f"Mind Masters AI Solutions Pvt. Ltd.  |  Report {record['id'][:8]}")
        canvas.drawRightString(A4[0] - 18 * mm, 9.5 * mm, f"AI-assisted assessment - not independent verification  |  Page {doc.page}")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=20 * mm, title=f"Verification Report - {record['title']}",
                            author="Mind Masters AI Solutions", subject="AI Answer Verification report")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
