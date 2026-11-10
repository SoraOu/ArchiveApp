r"""test_phase4c.py - checks OCR text search (Phase 4c).
Uses a temporary folder and a fake OCR engine, so it never touches your real data
and does not need Tesseract.

Run:  .venv\Scripts\python test_phase4c.py
"""
import sys
import tempfile
import traceback
from pathlib import Path

import ocr
from services import Archive, ArchiveError

TMP = tempfile.TemporaryDirectory()
ROOT = Path(TMP.name)
SRC = ROOT / "src"
SRC.mkdir()
arc = Archive(ROOT / "data")
S = {}

TEXTS = {
    "scan1.png": "Barangay Nutrition Scholar Training 2025\nCertificate of Appreciation",
    "scan2.pdf": "Resolution approving the 100% budget for feeding_program",
}


def fake_engine(path):
    # mkfile() writes the file's own name as its content, so the fake engine can tell the scans apart
    return TEXTS.get(Path(path).read_bytes().decode(errors="ignore"), "")


def mkfile(name, content=None):
    p = SRC / name
    p.write_bytes(content or name.encode())
    return p


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


def ocr_rows():
    return arc.conn.execute("SELECT status FROM file_ocr").fetchall()


def t_schema():
    assert arc.conn.execute("PRAGMA user_version").fetchone()[0] == 2
    cols = {r[1] for r in arc.conn.execute("PRAGMA table_info(file_ocr)")}
    assert {"file_id", "document_id", "status", "text", "error", "ocr_at"} <= cols, cols


def t_pending_and_run():
    S["d1"] = arc.add_document(mkfile("scan1.png"), name="Training certificate", tags=["Training"])
    S["d2"] = arc.add_document(mkfile("scan2.pdf"), name="Budget resolution")
    S["d3"] = arc.add_document(mkfile("memo.docx"), name="Memo")          # not a scan: never OCR'd
    pend = arc.ocr_pending()
    assert len(pend) == 2 and {p["document_id"] for p in pend} == {S["d1"], S["d2"]}, pend
    seen = []
    rep = arc.ocr_run(engine=fake_engine, progress=lambda i, n, name: seen.append((i, n)))
    assert rep["done"] == 2 and rep["empty"] == 0 and rep["failed"] == [] and not rep["cancelled"], rep
    assert seen[-1] == (2, 2)
    assert arc.ocr_pending() == []
    again = arc.ocr_run(engine=fake_engine)                                # nothing left to do
    assert again["done"] == 0 and again["failed"] == []
    st = arc.ocr_status()
    assert st["pending"] == 0 and st["done"] == 2 and st["failed"] == 0, st


def t_search():
    assert [r["id"] for r in arc.search("scholar")["results"]] == [S["d1"]]
    assert arc.search("SCHOLAR")["total"] == 1                              # case-insensitive
    assert arc.search("scholar 2025")["total"] == 1                         # every word must match
    assert arc.search("scholar zzzz")["total"] == 0
    assert arc.search("training certificate")["total"] == 1                 # words from name and from scan text
    assert arc.search("scholar", tags=["Training"])["total"] == 1
    assert arc.search("scholar", tags=["Nope"])["total"] == 0
    assert arc.search("budget")["total"] == 1                               # name still works
    assert arc.search("100%")["total"] == 1 and arc.search("%")["total"] == 1   # % is literal, not a wildcard
    assert arc.search("feeding_program")["total"] == 1 and arc.search("feeding-program")["total"] == 0
    assert arc.search("memo")["total"] == 1


def t_empty_and_failed():
    d = arc.add_document(mkfile("blank_page.png"), name="Blank")
    rep = arc.ocr_run(engine=lambda p: "   \n ")
    assert rep["empty"] == 1 and rep["done"] == 0 and arc.ocr_pending() == []
    e = arc.add_document(mkfile("broken.png"), name="Broken")

    def boom(path):
        raise RuntimeError("bad image")
    rep = arc.ocr_run(engine=boom)
    assert len(rep["failed"]) == 1 and "bad image" in rep["failed"][0]["error"], rep
    assert arc.ocr_pending() == [] and arc.ocr_status()["failed"] == 1       # not retried by default
    assert len(arc.ocr_pending(retry_failed=True)) == 1
    rep = arc.ocr_run(engine=lambda p: "recovered words", retry_failed=True)
    assert rep["done"] == 1 and arc.ocr_status()["failed"] == 0
    assert arc.search("recovered")["total"] == 1
    S["blank"], S["broken"] = d, e


def t_cancel():
    mkfile("c1.png"), mkfile("c2.png")
    arc.add_document(SRC / "c1.png", name="C1")
    arc.add_document(SRC / "c2.png", name="C2")
    calls = []
    rep = arc.ocr_run(engine=lambda p: "stopword", cancel=lambda: bool(calls) or calls.append(1))
    assert rep["cancelled"] and rep["done"] == 1 and len(arc.ocr_pending()) == 1, rep
    assert arc.ocr_run(engine=lambda p: "stopword")["done"] == 1             # finishes the rest later


def t_deleted_and_purge():
    d = arc.add_document(mkfile("gone.png"), name="Gone")
    arc.delete_document(d)
    assert arc.ocr_pending() == []                                           # Recycle Bin items are skipped
    arc.restore_document(d)
    assert len(arc.ocr_pending()) == 1
    arc.ocr_run(engine=lambda p: "purgeme")
    assert arc.search("purgeme")["total"] == 1
    arc.delete_document(d)
    assert arc.search("purgeme")["total"] == 0                               # deleted docs are not found
    before = len(ocr_rows())
    arc.purge_document(d)
    assert len(ocr_rows()) == before - 1                                     # OCR rows go with the document


def t_second_connection():
    # the planned pattern for a background thread: its own Archive object on the same data folder
    arc.add_document(mkfile("bg.png"), name="Background")
    arc2 = Archive(ROOT / "data")
    try:
        rep = arc2.ocr_run(engine=lambda p: "backgroundtext")
        assert rep["done"] == 1
    finally:
        arc2.close()
    assert arc.search("backgroundtext")["total"] == 1


def t_unavailable():
    orig = ocr.find_tesseract
    ocr.find_tesseract = lambda configured=None: None
    try:
        st = arc.ocr_status()
        assert st["available"] is False and "Tesseract" in st["message"], st
        arc.add_document(mkfile("needs_engine.png"), name="Needs engine")
        assert raises(ArchiveError, arc.ocr_run)
        assert arc.ocr_status()["pending"] >= 1                              # nothing was lost
    finally:
        ocr.find_tesseract = orig


def t_extract_text():
    from PIL import Image
    import pymupdf
    png = SRC / "real.png"
    Image.new("RGB", (80, 40), "white").save(png)
    calls = []

    def img2txt(img):
        calls.append(img.size)
        return "from image"
    assert ocr.extract_text(png, img2txt).strip() == "from image" and len(calls) == 1
    # PDF: page 1 has a text layer (used as is), page 2 is only a picture (goes to OCR)
    pdf = SRC / "real.pdf"
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "This page already has a real text layer with plenty of words.")
    p2 = doc.new_page()
    p2.insert_image(pymupdf.Rect(50, 50, 250, 250), filename=str(png))
    doc.save(str(pdf))
    doc.close()
    calls.clear()
    text = ocr.extract_text(pdf, img2txt)
    assert "real text layer" in text and "from image" in text and len(calls) == 1, (text, calls)


def t_audit_and_integrity():
    assert any(r["action"] == "ocr_run" for r in arc.get_audit_log(200))
    rep = arc.check_integrity(verify_hashes=True)
    assert rep["database_ok"] and rep["missing_files"] == [] and rep["orphan_files"] == [] and rep["changed_files"] == []


TESTS = [t_schema, t_pending_and_run, t_search, t_empty_and_failed, t_cancel, t_deleted_and_purge,
         t_second_connection, t_unavailable, t_extract_text, t_audit_and_integrity]

if __name__ == "__main__":
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS  {fn.__name__[2:]}")
        except Exception:
            failed += 1
            print(f"FAIL  {fn.__name__[2:]}")
            traceback.print_exc()
    print()
    print("ALL TESTS PASSED" if not failed else f"{failed} TEST(S) FAILED")
    try:
        arc.close()
        TMP.cleanup()
    except Exception:
        pass
    sys.exit(1 if failed else 0)
