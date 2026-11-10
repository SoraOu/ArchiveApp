r"""apply_4c_ui.py - one-time patch for the Phase 4c screens (Index scans, OCR settings).
Edits ui/main_window.py and ui/settings_window.py in place. Every find text must match exactly once;
if any does not, nothing is changed. Backups: <name>.bak4c. Also needs ui/ocr_dialog.py in place.

Run from ArchiveApp:  .venv\\Scripts\\python apply_4c_ui.py
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

MAIN_WINDOW_EDITS = [
    (r'''from ui.maintenance import CheckDialog, start_backup
''',
     r'''from ui.maintenance import CheckDialog, start_backup
from ui.ocr_dialog import OcrDialog
'''),
    (r'''        tools.add_command(label="Check archive...", command=self.check_archive)
''',
     r'''        tools.add_command(label="Index scans (OCR)...", command=self.index_scans)
        tools.add_command(label="Check archive...", command=self.check_archive)
'''),
    (r'''    def open_settings(self):
''',
     r'''    def index_scans(self):
        dlg = OcrDialog(self.root, self.archive)
        dlg.run()
        if dlg.changed:
            self.status.set("Scan text indexed. Searches now look inside the scans.")

    def open_settings(self):
'''),
]

SETTINGS_EDITS = [
    (r'''super().__init__(parent, "Settings", "640x470")''',
     r'''super().__init__(parent, "Settings", "640x600")'''),
    (r'''        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=14, pady=(0, 12), side="bottom")
''',
     r'''        r += 1
        ttk.Separator(body).grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
        r += 1
        ttk.Label(body, text="Text in scans (OCR)", font=("TkDefaultFont", 10, "bold")).grid(row=r, column=0, sticky="w")
        r += 1
        ttk.Label(body, text="Tesseract program").grid(row=r, column=0, sticky="w", pady=5)
        self.tess_var = tk.StringVar(value=archive.get_setting("tesseract_path", ""))
        ttk.Entry(body, textvariable=self.tess_var).grid(row=r, column=1, sticky="ew", padx=(10, 0))
        ttk.Button(body, text="Browse...", width=8, command=self._browse_tesseract).grid(row=r, column=2, padx=(6, 0))
        r += 1
        ttk.Label(body, text="Language").grid(row=r, column=0, sticky="w", pady=5)
        self.lang_var = tk.StringVar(value=archive.get_setting("ocr_lang", "") or "eng")
        ttk.Entry(body, textvariable=self.lang_var, width=12).grid(row=r, column=1, sticky="w", padx=(10, 0))
        r += 1
        ttk.Label(body, foreground="#666", wraplength=470, justify="left", text=(
            "Leave the program path empty to find Tesseract automatically. eng is English. "
            "Other languages (for example fil) need their language file installed in Tesseract. "
            "Read new scans with Tools > Index scans.")).grid(row=r, column=1, columnspan=2, sticky="w", padx=(10, 0))

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=14, pady=(0, 12), side="bottom")
'''),
    (r'''    def _store(self):
''',
     r'''    def _browse_tesseract(self):
        f = filedialog.askopenfilename(parent=self, title="Choose tesseract.exe",
                                       filetypes=[("Tesseract", "tesseract.exe"), ("All files", "*.*")])
        self.regrab()
        if f:
            self.tess_var.set(f)

    def _store(self):
'''),
    (r'''        self.archive.set_setting("backup_reminder_days", days)
''',
     r'''        self.archive.set_setting("backup_reminder_days", days)
        self.archive.set_setting("tesseract_path", self.tess_var.get().strip())
        self.archive.set_setting("ocr_lang", self.lang_var.get().strip() or "eng")
'''),
]


def prepare(rel, edits, done_marker):
    path = HERE / rel
    text = path.read_text(encoding="utf-8")
    if done_marker in text:
        print(f"{rel}: already patched, skipped")
        return None
    for i, (old, new) in enumerate(edits, start=1):
        if text.count(old) != 1:
            print(f"{rel}: edit {i} found {text.count(old)} matches (expected 1). Nothing was changed.")
            sys.exit(1)
        text = text.replace(old, new)
    return path, text


def main():
    if not (HERE / "ui" / "ocr_dialog.py").exists():
        print("ui/ocr_dialog.py is missing. Copy it into the ui folder first.")
        sys.exit(1)
    jobs = [j for j in (prepare("ui/main_window.py", MAIN_WINDOW_EDITS, "OcrDialog"),
                        prepare("ui/settings_window.py", SETTINGS_EDITS, "tesseract_path")) if j]
    for path, text in jobs:
        shutil.copy2(path, path.with_name(path.name + ".bak4c"))
        path.write_text(text, encoding="utf-8", newline="")
        print(f"patched {path.name}")
    print("done" if jobs else "nothing to do")


main()
