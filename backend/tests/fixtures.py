"""Generate real test files (PDFs and images) in memory."""

import io

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def text_pdf(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(60, y, line)
        y -= 18
    c.showPage()
    c.save()
    return buffer.getvalue()


def text_image(lines: list[str], size=(900, 420)) -> Image.Image:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 26)
    except OSError:
        font = ImageFont.load_default()
    for i, line in enumerate(lines):
        draw.text((30, 30 + i * 44), line, fill="black", font=font)
    return img


def png(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    text_image(lines).save(buffer, format="PNG")
    return buffer.getvalue()


def scanned_pdf(lines: list[str]) -> bytes:
    """A PDF whose page is only an image (no text layer), like a scanned document."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.drawImage(ImageReader(text_image(lines, (1200, 700))), 40, 380, width=515, height=300)
    c.showPage()
    c.save()
    return buffer.getvalue()


def encrypted_pdf() -> bytes:
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(text_pdf(["secret"]))))
    writer.encrypt("pw-123")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
