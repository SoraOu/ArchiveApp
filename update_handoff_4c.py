r"""update_handoff_4c.py - one-time edit of HANDOFF.md after Phase 4c.
Run AFTER the handoff_tool.py --milestone commands (they rewrite the status table, board and log).
Edits the text sections 2, 3, 4, 5, 6 and 8 by hand-written find/replace. A text that is not found
exactly once is skipped and reported. Backup: HANDOFF.md.bak4c.

Run from ArchiveApp:  .venv\\Scripts\\python update_handoff_4c.py
"""
import shutil
from pathlib import Path

PATH = Path(__file__).resolve().parent / "HANDOFF.md"
EDITS = [
    (r'''Phases 2 and 3 were tested headless on Linux only. **The user has not yet confirmed them on Windows.**''',
     r'''Phases 2 and 3 were verified on Windows by the user on 2026-11-10 (app start, open file, show in folder, PDF preview, DPI/layout, Recycle Bin, backup, Settings). Phase 4 (bulk import, Scanner inbox, OCR text search) is built and confirmed working on Windows.'''),
    (r'''Test suites (all pass): `test_phase1.py` (18), `test_phase3.py` (13), `dev/gui_smoke_phase2.py`, `dev/gui_smoke_phase3.py`.''',
     r'''Test suites (all pass on the user's PC, 2026-11-10): `test_phase1.py` (18), `test_phase3.py` (13), `test_phase4.py` (6), `test_phase4b.py`, `test_phase4c.py` (10), `dev/gui_smoke_phase2.py`, `dev/gui_smoke_phase3.py`.'''),
    (r'''**Untested on Windows:** `os.startfile`, `explorer /select`, high-DPI behaviour, the `vista` ttk theme, PyMuPDF 2.1
import name (code tries `pymupdf` then `fitz`). First thing to do: ask the user how Phase 2/3 behaved on their PC.''',
     r'''**Still untested:** `restore.py`, filing a pending item from the Scanner inbox, OCR on multi-page or very large PDFs, OCR in a language other than English. The Index scans dialog and the OCR section of Settings were only run by the user: Tk is not available in the Linux test environment, so UI code is compile-checked there and confirmed on Windows.
First thing to do next chat: ask what to build next (4d thumbnails/export is low priority; 5 is the browser view).'''),
    (r'''  Tesseract OCR is **not installed** yet (only needed for OCR).''',
     r'''  Tesseract OCR 5.5.3 is installed at `C:\Program Files\Tesseract-OCR` (found automatically; path and language can be set in Settings).'''),
    (r'''11. **Scope kept small on purpose** (see section 1). Resist adding workflow features.''',
     r'''11. **Scope kept small on purpose** (see section 1). Resist adding workflow features.
12. **OCR text search (4c).** Text from scans lives in its own table `file_ocr` (one row per file; status done/empty/failed; text stored casefolded), not in `documents.search_text`, so search text stays small and backups include it. `search()` matches each query word against `search_text` OR the OCR text, so Phase 6 confidential filtering (`include_confidential=False`) also hides OCR matches; never expose `file_ocr.text` any other way. PDF pages that already have a text layer (25+ characters) are read directly; only picture-only pages go to Tesseract. Scans are read on demand from Tools > Index scans (OCR), not automatically. Failed files are retried only when the user ticks the box. Default language `eng`; settings `tesseract_path` and `ocr_lang`. Existing scans are queued automatically after the v2 upgrade because they have no `file_ocr` row.'''),
    (r'''backup.py/restore.py   backup + restore (pure functions, no UI)''',
     r'''backup.py/restore.py   backup + restore (pure functions, no UI)
ocr.py            Tesseract lookup and text extraction from images/PDFs (pure functions, no DB, no UI)'''),
    (r'''                  settings_window, maintenance, activity_log, recycle_bin, preview, widgets, common)''',
     r'''                  settings_window, maintenance, ocr_dialog, activity_log, recycle_bin, preview, widgets, common)'''),
    (r'''- Windows-hostile characters in names are sanitized in `storage.sanitize_filename`.''',
     r'''- Windows-hostile characters in names are sanitized in `storage.sanitize_filename`.
- A background thread that writes to the database creates its own `Archive(data_dir)` and closes it at the end (see `ui/ocr_dialog.py`). It never shares the UI's connection.'''),
    (r'''## 6. Data model (schema version 1)''',
     r'''## 6. Data model (schema version 2)'''),
    (r'''Data types: text, longtext, number, id, year, date, name, yesno, dropdown.''',
     r'''Data types: text, longtext, number, id, year, date, name, yesno, dropdown.
Schema v2 (Phase 4c): `file_ocr(file_id PK -> document_files, document_id -> documents, status, text, error, ocr_at)`, both foreign keys ON DELETE CASCADE.'''),
    (r'''Before 4a: collect the remaining ~14 document types from the user (format `Type: detail (data type), ...`) and ask what "Source" holds for Resolutions and Executive Orders.''',
     r'''Open since 2026-11-10 (the user postponed it): collect the remaining ~14 document types (format `Type: detail (data type), ...`) and ask what "Source" holds for Resolutions and Executive Orders. It does not block 4d, 5 or 6.'''),
]

text = PATH.read_text(encoding="utf-8")
if "12. **OCR text search (4c).**" in text:
    print("HANDOFF.md already has the 4c notes. Nothing to do.")
    raise SystemExit(0)
skipped = 0
for i, (old, new) in enumerate(EDITS, start=1):
    if text.count(old) == 1:
        text = text.replace(old, new)
    else:
        skipped += 1
        print(f"edit {i}: text found {text.count(old)} times (expected 1), skipped")
shutil.copy2(PATH, PATH.with_name("HANDOFF.md.bak4c"))
PATH.write_text(text, encoding="utf-8", newline="")
print(f"HANDOFF.md updated ({len(EDITS) - skipped} of {len(EDITS)} edits applied)")
