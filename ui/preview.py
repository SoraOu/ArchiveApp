"""ui/preview.py - shows the first page of a scanned file (PDF or image)."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk

try:
    from PIL import Image, ImageOps, ImageTk
except Exception:          # Pillow missing: previews simply unavailable
    Image = ImageOps = ImageTk = None
try:
    import pymupdf as fitz   # PyMuPDF (current import name)
except Exception:
    try:
        import fitz        # older import name
    except Exception:
        fitz = None

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}


class Preview(ttk.Frame):
    def __init__(self, parent, width=320, height=420):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, width=width, height=height, bg="#f3f3f3",
                                highlightthickness=1, highlightbackground="#c8c8c8")
        self.canvas.pack(fill="both", expand=True)
        nav = ttk.Frame(self)
        nav.pack(fill="x", pady=(4, 0))
        self.prev_btn = ttk.Button(nav, text="\u25c0", width=3, command=lambda: self._turn(-1))
        self.next_btn = ttk.Button(nav, text="\u25b6", width=3, command=lambda: self._turn(1))
        self.page_lbl = ttk.Label(nav, text="")
        self.prev_btn.pack(side="left")
        self.page_lbl.pack(side="left", padx=8)
        self.next_btn.pack(side="left")
        self._path = None
        self._page = 0
        self._pages = 1
        self._photo = None
        self._after = None
        self._size = (0, 0)
        self.canvas.bind("<Configure>", self._on_resize)
        self._update_nav()

    def show(self, path):
        self._path = Path(path) if path else None
        self._page = 0
        self._pages = 1
        self._render()

    def clear(self, message="No document selected"):
        self._path = None
        self._pages = 1
        self._message(message)
        self._update_nav()

    # ---- internals
    def _on_resize(self, ev):
        if abs(ev.width - self._size[0]) < 6 and abs(ev.height - self._size[1]) < 6:
            return
        self._size = (ev.width, ev.height)
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(150, self._render)

    def _turn(self, step):
        page = self._page + step
        if 0 <= page < self._pages:
            self._page = page
            self._render()

    def _update_nav(self):
        multi = self._pages > 1
        state = "normal" if multi else "disabled"
        self.prev_btn.configure(state=state if self._page > 0 else "disabled")
        self.next_btn.configure(state=state if self._page < self._pages - 1 else "disabled")
        self.page_lbl.configure(text=f"Page {self._page + 1} of {self._pages}" if multi else "")

    def _message(self, text):
        c = self.canvas
        c.delete("all")
        self._photo = None
        w, h = c.winfo_width(), c.winfo_height()
        c.create_text(max(w, 10) // 2, max(h, 10) // 2, text=text, justify="center",
                      fill="#666", width=max(w - 30, 60))

    def _render(self):
        self._after = None
        if not self._path:
            self._message("No document selected")
            self._update_nav()
            return
        c = self.canvas
        w, h = max(c.winfo_width() - 8, 60), max(c.winfo_height() - 8, 60)
        if not self._path.is_file():
            self._message("File not found:\n" + self._path.name)
            self._update_nav()
            return
        ext = self._path.suffix.lower()
        try:
            if ImageTk is None:
                raise RuntimeError("Pillow not installed")
            if ext == ".pdf":
                img = self._render_pdf(w, h)
            elif ext in _IMAGE_EXT:
                img = self._render_image(w, h)
            else:
                self._message(f"No preview for {ext or 'this'} files.\nUse Open File.")
                self._update_nav()
                return
        except Exception:
            self._message("Preview not available.\nUse Open File.")
            self._update_nav()
            return
        self._photo = ImageTk.PhotoImage(img)
        c.delete("all")
        c.create_image(c.winfo_width() // 2, c.winfo_height() // 2, image=self._photo)
        self._update_nav()

    def _render_pdf(self, w, h):
        if fitz is None:
            raise RuntimeError("PyMuPDF not installed")
        doc = fitz.open(str(self._path))
        try:
            self._pages = max(doc.page_count, 1)
            self._page = min(self._page, self._pages - 1)
            page = doc[self._page]
            zoom = min(w / page.rect.width, h / page.rect.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        finally:
            doc.close()

    def _render_image(self, w, h):
        img = Image.open(self._path)
        self._pages = max(getattr(img, "n_frames", 1), 1)
        self._page = min(self._page, self._pages - 1)
        if self._pages > 1:
            img.seek(self._page)
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((w, h))
        return img
