"""ocr.py - read text out of scans with Tesseract.

Pure functions, no database and no UI. services.py decides what to read and where to store it.
"""
import shutil
from pathlib import Path

TESSERACT_DEFAULT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
OCR_EXTS = IMAGE_EXTS + (".pdf",)
MIN_LAYER_CHARS = 25        # a PDF page with at least this much real text is used as is, without OCR
RENDER_DPI = 200


class OcrUnavailable(Exception):
    """Tesseract or pytesseract is missing."""


def find_tesseract(configured=None):
    """Path to tesseract.exe: the configured path, then PATH, then the default install folder."""
    for cand in (configured, shutil.which("tesseract"), TESSERACT_DEFAULT):
        if cand and Path(cand).is_file():
            return str(cand)
    return None


def make_engine(tesseract_cmd=None, lang="eng", dpi=RENDER_DPI):
    """Return engine(path) -> text. Raises OcrUnavailable with a plain message if it cannot work."""
    cmd = find_tesseract(tesseract_cmd)
    if not cmd:
        raise OcrUnavailable("Tesseract was not found. Install it (UB Mannheim build) or set its path in Settings.")
    try:
        import pytesseract
    except ImportError:
        raise OcrUnavailable("The pytesseract package is not installed. Run: .venv\\Scripts\\python -m pip install pytesseract")
    pytesseract.pytesseract.tesseract_cmd = cmd

    def engine(path):
        return extract_text(path, lambda img: pytesseract.image_to_string(img, lang=lang), dpi)
    return engine


def _pymupdf():
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        import fitz
        return fitz


def extract_text(path, image_to_text, dpi=RENDER_DPI):
    """Text of one file. image_to_text(PIL image) -> str does the actual OCR.
    Images (every frame of a multi-page TIFF) go straight to OCR. In a PDF, pages that already
    carry a text layer are read directly; only picture-only pages are rendered and OCR'd."""
    path = Path(path)
    ext = path.suffix.lower()
    parts = []
    if ext in IMAGE_EXTS:
        from PIL import Image, ImageSequence
        with Image.open(path) as im:
            for frame in ImageSequence.Iterator(im):
                parts.append(image_to_text(frame.convert("RGB")))
    elif ext == ".pdf":
        from PIL import Image
        mu = _pymupdf()
        with mu.open(str(path)) as doc:
            for page in doc:
                layer = page.get_text().strip()
                if len(layer) >= MIN_LAYER_CHARS:
                    parts.append(layer)
                    continue
                pix = page.get_pixmap(dpi=dpi)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                parts.append(layer + "\n" + image_to_text(img))
    else:
        raise ValueError(f"Cannot read text from a {ext or 'file without extension'} file")
    return "\n".join(p for p in parts if p and p.strip())
