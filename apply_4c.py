r"""apply_4c.py - one-time patch for Phase 4c (OCR text search).
Edits db.py and services.py in place. Every find text must match exactly once; if any does not,
nothing is changed. Backups are written as db.py.bak4c and services.py.bak4c.

Run from ArchiveApp:  .venv\\Scripts\\python apply_4c.py
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

DB_EDITS = [
    (r'''MIGRATIONS = [SCHEMA_V1]  # index + 1 == schema version''',
     r'''SCHEMA_V2 = """
CREATE TABLE file_ocr (
    file_id     INTEGER PRIMARY KEY REFERENCES document_files(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    status      TEXT NOT NULL,
    text        TEXT NOT NULL DEFAULT '',
    error       TEXT NOT NULL DEFAULT '',
    ocr_at      TEXT NOT NULL
);
CREATE INDEX idx_ocr_doc ON file_ocr(document_id);
"""

MIGRATIONS = [SCHEMA_V1, SCHEMA_V2]  # index + 1 == schema version'''),
]

SERVICES_EDITS = [
    (r'''import db
import storage
''',
     r'''import db
import ocr
import storage
'''),
    (r'''            where.append("d.search_text LIKE ? ESCAPE '\\'")
            params.append(_like(token))
''',
     r'''            where.append("(d.search_text LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM file_ocr o "
                         "WHERE o.document_id=d.id AND o.text LIKE ? ESCAPE '\\'))")
            params += [_like(token), _like(token)]
'''),
    (r'''(name, type, notes, type details, tags, original file names)."""''',
     r'''(name, type, notes, type details, tags, original file names, text read from the scans)."""'''),
    (r'''    # ------------------------------------------------------------ scanner inbox (watch folder)
''',
     r'''    # ------------------------------------------------------------ OCR (text inside scans)
    def ocr_status(self):
        """{available, message, pending, done, empty, failed}. Cheap enough to call when the window opens."""
        try:
            ocr.make_engine(self.get_setting("tesseract_path") or None)
            available, message = True, "ok"
        except ocr.OcrUnavailable as e:
            available, message = False, str(e)
        counts = {r["status"]: r["n"] for r in self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM file_ocr GROUP BY status")}
        return {"available": available, "message": message, "pending": len(self.ocr_pending()),
                "done": counts.get("done", 0), "empty": counts.get("empty", 0), "failed": counts.get("failed", 0)}

    def ocr_pending(self, retry_failed=False):
        """Scan files (images and PDFs of documents not in the Recycle Bin) that have not been read yet.
        With retry_failed=True, files that failed earlier are included too."""
        rows = self.conn.execute(
            "SELECT f.id AS file_id, f.document_id, f.file_path, f.original_filename "
            "FROM document_files f JOIN documents d ON d.id=f.document_id "
            "LEFT JOIN file_ocr o ON o.file_id=f.id "
            "WHERE d.is_deleted=0 AND (o.file_id IS NULL OR (?=1 AND o.status='failed')) ORDER BY f.id",
            (1 if retry_failed else 0,)).fetchall()
        return [dict(r) for r in rows if Path(r["file_path"]).suffix.lower() in ocr.OCR_EXTS]

    def ocr_run(self, engine=None, progress=None, cancel=None, retry_failed=False):
        """Read the text of every pending scan so it becomes searchable. Each file is saved on its own,
        so stopping (cancel) or a crash keeps what is already done. One bad file does not stop the rest.
        engine(path) -> text is created from Tesseract when not given (tests pass a fake one).
        Run it on its own Archive object when called from a background thread.
        Returns {"done", "empty", "failed": [{file_id, name, error}], "cancelled"}."""
        if engine is None:
            try:
                engine = ocr.make_engine(self.get_setting("tesseract_path") or None,
                                         self.get_setting("ocr_lang") or "eng")
            except ocr.OcrUnavailable as e:
                raise ArchiveError(str(e))
        rows = self.ocr_pending(retry_failed)
        report = {"done": 0, "empty": 0, "failed": [], "cancelled": False}
        for n, r in enumerate(rows, start=1):
            if cancel and cancel():
                report["cancelled"] = True
                break
            text, error = "", ""
            try:
                text = " ".join(str(engine(self.storage.abs_path(r["file_path"]))).split()).casefold()
                status = "done" if text else "empty"
            except Exception as e:
                status, text, error = "failed", "", (str(e) or e.__class__.__name__)[:300]
            with self.conn:
                self.conn.execute(
                    "INSERT INTO file_ocr(file_id, document_id, status, text, error, ocr_at) VALUES(?,?,?,?,?,?) "
                    "ON CONFLICT(file_id) DO UPDATE SET status=excluded.status, text=excluded.text, "
                    "error=excluded.error, ocr_at=excluded.ocr_at",
                    (r["file_id"], r["document_id"], status, text, error, _now()))
            if status == "failed":
                report["failed"].append({"file_id": r["file_id"], "name": r["original_filename"], "error": error})
            else:
                report[status] += 1
            if progress:
                progress(n, len(rows), r["original_filename"])
        if rows:
            with self.conn:
                self._log("ocr_run", None,
                          f"{report['done']} read, {report['empty']} without text, {len(report['failed'])} failed"
                          + (" (stopped early)" if report["cancelled"] else ""))
        return report

    # ------------------------------------------------------------ scanner inbox (watch folder)
'''),
]


def apply(name, edits):
    path = HERE / name
    text = path.read_text(encoding="utf-8")
    if "file_ocr" in text:
        print(f"{name}: already patched, skipped")
        return None
    for i, (old, new) in enumerate(edits, start=1):
        if text.count(old) != 1:
            print(f"{name}: edit {i} found {text.count(old)} matches (expected 1). Nothing was changed.")
            sys.exit(1)
        text = text.replace(old, new)
    return path, text


def main():
    jobs = [j for j in (apply("db.py", DB_EDITS), apply("services.py", SERVICES_EDITS)) if j]
    for path, text in jobs:
        shutil.copy2(path, path.with_name(path.name + ".bak4c"))
        path.write_text(text, encoding="utf-8", newline="")
        print(f"patched {path.name}")
    print("done" if jobs else "nothing to do")


main()
