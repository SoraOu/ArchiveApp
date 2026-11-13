"""thumbs.py - small preview images for scans (pure functions: no database, no UI).

make_thumbnail(src, dest, size) writes a PNG whose longest side is at most `size`
pixels, with a thin grey frame. It never raises: it returns True when the thumbnail was written, False when
the file is not a picture or PDF, or could not be read.
"""
import os
from pathlib import Path

try:
    from PIL import Image, ImageOps
except Exception:          # Pillow missing: no thumbnails
    Image = ImageOps = None
try:
    import pymupdf as fitz   # PyMuPDF (current import name)
except Exception:
    try:
        import fitz        # older import name
    except Exception:
        fitz = None

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
THUMB_EXTS = IMAGE_EXTS | {".pdf"}
BORDER = 1                      # pixels of frame on each side (inside `size`)
FRAME = (176, 176, 176)         # light grey


def _pdf_first_page(src, size):
    if fitz is None:
        raise RuntimeError("PyMuPDF not installed")
    doc = fitz.open(str(src))
    try:
        page = doc[0]
        zoom = (size - 2 * BORDER) / max(page.rect.width, page.rect.height, 1)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()


def _image_first_frame(src):
    img = Image.open(src)
    img.seek(0)
    return ImageOps.exif_transpose(img).convert("RGB")


def make_thumbnail(src, dest, size=96):
    src, dest = Path(src), Path(dest)
    if Image is None or src.suffix.lower() not in THUMB_EXTS:
        return False
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        img = _pdf_first_page(src, size) if src.suffix.lower() == ".pdf" else _image_first_frame(src)
        img.thumbnail((size - 2 * BORDER, size - 2 * BORDER))
        img = ImageOps.expand(img, border=BORDER, fill=FRAME)
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(tmp, format="PNG")
        os.replace(tmp, dest)
        return True
    except Exception:
        tmp.unlink(missing_ok=True)
        return False
