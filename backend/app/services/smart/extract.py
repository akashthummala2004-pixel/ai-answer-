"""Turn submitted text, PDFs and images into labelled inputs for the AI model.

Nothing here is persisted: file bytes and extracted document text live only for the request.
"""

import base64
import io
from dataclasses import dataclass, field

import pypdfium2
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_FILES = 3
MAX_TEXT_CHARS = 20_000
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 30            # pages whose text is extracted
MAX_DOC_CHARS = 30_000        # per document, sent to the model
MAX_SCANNED_PAGES = 3         # scanned pages rendered and sent to the vision model
SCANNED_CHARS_PER_PAGE = 25   # below this average, a PDF is treated as having no text layer
MAX_IMAGE_SIDE = 2000         # larger images are downscaled before upload

ACCEPTED = {"pdf": "application/pdf", "png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}


class InputError(Exception):
    """A submitted input is invalid; the message is safe to show to the user."""


@dataclass
class InputPart:
    id: str                       # "T", "D1", "I1", ...
    kind: str                     # "text" | "pdf" | "scanned_pdf" | "image"
    name: str
    mime: str
    size: int = 0
    pages: int | None = None
    text: str | None = None       # text sent to the model (typed text or extracted PDF text)
    images: list[str] = field(default_factory=list)  # data: URLs sent to the model
    notes: list[str] = field(default_factory=list)   # limitations specific to this input

    def metadata(self) -> dict:
        """What is stored with the verification: no document text and no image data."""
        return {"id": self.id, "kind": self.kind, "name": self.name, "mime": self.mime, "size": self.size,
                "pages": self.pages, "chars": len(self.text or ""), "images_sent": len(self.images),
                "notes": self.notes}


def sniff(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _data_url(img: Image.Image) -> str:
    """Normalise an image (RGB, bounded size) and return it as a JPEG/PNG data URL."""
    if max(img.size) > MAX_IMAGE_SIDE:
        img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    buffer = io.BytesIO()
    if img.mode in ("RGBA", "LA", "P"):
        img.convert("RGBA").save(buffer, format="PNG", optimize=True)
        mime = "image/png"
    else:
        img.convert("RGB").save(buffer, format="JPEG", quality=88)
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(buffer.getvalue()).decode()}"


def text_part(text: str) -> InputPart:
    text = text.strip()
    if len(text) > MAX_TEXT_CHARS:
        raise InputError(f"Text is too long ({len(text):,} characters). The limit is {MAX_TEXT_CHARS:,}.")
    return InputPart(id="T", kind="text", name="Typed text", mime="text/plain", size=len(text.encode()), text=text)


def pdf_part(part_id: str, name: str, data: bytes) -> InputPart:
    if len(data) > MAX_PDF_BYTES:
        raise InputError(f"'{name}' is larger than {MAX_PDF_BYTES // (1024 * 1024)} MB.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise InputError(f"'{name}' is password-protected. Remove the password and upload it again.")
        page_count = len(reader.pages)
        texts = []
        for page in reader.pages[:MAX_PDF_PAGES]:
            texts.append((page.extract_text() or "").strip())
    except InputError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise InputError(f"'{name}' could not be read as a PDF. It may be damaged.") from exc
    if page_count == 0:
        raise InputError(f"'{name}' has no pages.")

    part = InputPart(id=part_id, kind="pdf", name=name, mime="application/pdf", size=len(data), pages=page_count)
    processed = min(page_count, MAX_PDF_PAGES)
    text = "\n\n".join(f"[page {i + 1}]\n{t}" for i, t in enumerate(texts) if t)
    if sum(len(t) for t in texts) / processed >= SCANNED_CHARS_PER_PAGE:
        if len(text) > MAX_DOC_CHARS:
            text = text[:MAX_DOC_CHARS]
            part.notes.append(f"Only the first {MAX_DOC_CHARS:,} characters of '{name}' were analysed.")
        if page_count > MAX_PDF_PAGES:
            part.notes.append(f"Only the first {MAX_PDF_PAGES} of {page_count} pages of '{name}' were analysed.")
        part.text = text
        return part

    # No usable text layer: render the first pages and let the vision model read them.
    part.kind = "scanned_pdf"
    try:
        pdf = pypdfium2.PdfDocument(data)
        for index in range(min(page_count, MAX_SCANNED_PAGES)):
            bitmap = pdf[index].render(scale=1.6)
            part.images.append(_data_url(bitmap.to_pil()))
        pdf.close()
    except Exception as exc:  # noqa: BLE001 - pdfium raises its own error types
        raise InputError(f"'{name}' appears to be scanned, and its pages could not be rendered for reading.") from exc
    part.notes.append(f"'{name}' has no text layer (scanned or image-only). The first {len(part.images)} page(s) were "
                      "read by the AI model from page images; text read this way may contain errors.")
    if page_count > MAX_SCANNED_PAGES:
        part.notes.append(f"Only {MAX_SCANNED_PAGES} of {page_count} scanned pages of '{name}' were analysed.")
    return part


def image_part(part_id: str, name: str, data: bytes) -> InputPart:
    if len(data) > MAX_IMAGE_BYTES:
        raise InputError(f"'{name}' is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise InputError(f"'{name}' is not a valid image.") from exc
    kind = sniff(data)
    return InputPart(id=part_id, kind="image", name=name, mime=ACCEPTED[kind], size=len(data), images=[_data_url(img)])


def build_parts(text: str | None, files: list[tuple[str, bytes]]) -> list[InputPart]:
    """Validate and convert all inputs. Raises InputError with a user-facing message."""
    parts: list[InputPart] = []
    if text and text.strip():
        parts.append(text_part(text))
    if len(files) > MAX_FILES:
        raise InputError(f"Upload at most {MAX_FILES} files at a time.")
    docs = imgs = 0
    for name, data in files:
        name = (name or "file").strip()[:120] or "file"
        if not data:
            raise InputError(f"'{name}' is empty.")
        kind = sniff(data)
        if kind is None:
            raise InputError(f"'{name}' is not a supported file. Upload a PDF, PNG, JPG or WebP file.")
        if kind == "pdf":
            docs += 1
            parts.append(pdf_part(f"D{docs}", name, data))
        else:
            imgs += 1
            parts.append(image_part(f"I{imgs}", name, data))
    if not parts:
        raise InputError("Enter some text or upload a document or screenshot to verify.")
    return parts
