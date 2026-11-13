r"""test_phase4d.py - checks thumbnails and export (Phase 4d).
Uses a temporary folder, so it never touches your real data.

Run:  .venv\Scripts\python test_phase4d.py
"""
import csv
import sys
import tempfile
import traceback
from pathlib import Path

import openpyxl
import pymupdf
from PIL import Image

import thumbs
from services import Archive, ArchiveError

TMP = tempfile.TemporaryDirectory()
ROOT = Path(TMP.name)
SRC = ROOT / "src"
SRC.mkdir()
arc = Archive(ROOT / "data")
S = {}
EVIL = "=cmd|' /C calc'!A0"


def mkfile(name, content=None):
    p = SRC / name
    p.write_bytes(content or name.encode())
    return p


def mkpng(name, color, size=(300, 200)):
    p = SRC / name
    Image.new("RGB", size, color).save(p)
    return p


def mkpdf(name, text):
    p = SRC / name
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    doc.save(str(p))
    doc.close()
    return p


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


class CountCalls:
    """Replace thumbs.make_thumbnail with a counting wrapper."""
    def __enter__(self):
        self.orig, self.n = thumbs.make_thumbnail, 0

        def wrapper(*a, **kw):
            self.n += 1
            return self.orig(*a, **kw)
        thumbs.make_thumbnail = wrapper
        return self

    def __exit__(self, *exc):
        thumbs.make_thumbnail = self.orig


# ---------------------------------------------------------------- export
def t_export_rows():
    t = arc.create_type("Resolution", [{"label": "Ref No.", "data_type": "id", "is_key": True}])
    S["t"] = t
    arc.add_document(mkfile("a.pdf"), name="Alpha budget", type_id=t, details={"Ref No.": "R-1"},
                     tags=["Budget", "2025"], doc_date="2025-03-01")
    arc.add_document(mkfile("b.pdf"), name="Beta report", tags=["Report"])
    arc.add_document(mkfile("c.pdf"), name="Gamma secret", confidential=True)
    arc.add_document(mkfile("d.pdf"), name=EVIL)
    headers, rows = arc.export_rows()
    assert headers == list(Archive.EXPORT_COLUMNS) == [
        "Name", "Type", "Reference", "Document date", "Tags", "Confidential", "Date added", "Files"], headers
    assert len(rows) == 4 and all(len(r) == len(headers) for r in rows), rows
    alpha = next(r for r in rows if r[0] == "Alpha budget")
    assert alpha[1:6] == ["Resolution", "R-1", "2025-03-01", "2025, Budget", ""], alpha
    assert alpha[7] == 1 and "T" not in alpha[6], alpha
    gamma = next(r for r in rows if r[0] == "Gamma secret")
    assert gamma[5] == "Yes", gamma
    # paging: small pages give exactly the same rows in the same order
    assert arc.export_rows(page_size=2)[1] == rows
    assert arc.export_rows(page_size=1)[1] == rows


def t_export_filters():
    assert len(arc.export_rows(query="alpha")[1]) == 1
    assert len(arc.export_rows(tags=["Budget"])[1]) == 1
    assert len(arc.export_rows(type_id=S["t"])[1]) == 1
    assert len(arc.export_rows(query="zzzz")[1]) == 0
    rows = arc.export_rows(include_confidential=False)[1]
    assert len(rows) == 3 and "Gamma secret" not in [r[0] for r in rows]
    rows = arc.export_rows(sort="name")[1]
    assert rows[1][0] == "Alpha budget" and rows[-1][0] == "Gamma secret", [r[0] for r in rows]


def t_export_csv():
    path = ROOT / "out.csv"
    assert arc.export_file(path) == 4
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")                     # BOM so Excel reads UTF-8
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    assert rows[0][0] == "Name" and len(rows) == 5, rows
    evil = next(r[0] for r in rows[1:] if "calc" in r[0])
    assert evil.startswith("'="), evil                                       # never opens as a formula
    assert not (ROOT / "out.csv.tmp").exists()
    assert arc.export_file(ROOT / "open.csv", include_confidential=False) == 3


def t_export_xlsx():
    path = ROOT / "out.xlsx"
    assert arc.export_file(path, tags=["Budget"]) == 1
    assert arc.export_file(path) == 4                                        # overwrites
    ws = openpyxl.load_workbook(path)["Documents"]
    assert ws.max_row == 5 and ws.cell(1, 1).value == "Name", ws.max_row
    cell = next(c for row in ws.iter_rows(min_row=2, max_col=1) for c in row if "calc" in str(c.value))
    assert cell.value == EVIL and cell.data_type == "s", (cell.value, cell.data_type)   # text, not a formula
    assert not (ROOT / "out.xlsx.tmp").exists()


def t_export_errors():
    assert raises(ArchiveError, arc.export_file, ROOT / "x.txt")
    assert raises(ArchiveError, arc.export_file, ROOT / "no_such_folder" / "x.csv")
    assert not (ROOT / "x.txt").exists()


def t_export_audit():
    assert any(r["action"] == "export" for r in arc.get_audit_log(200))


# ---------------------------------------------------------------- thumbnails
def t_thumb_png():
    S["png"] = d = arc.add_document(mkpng("t1.png", "red"), name="Red png")
    p = arc.thumbnail_for_document(d, 64)
    assert p is not None and p.is_file(), p
    assert p.parent.parent == ROOT / "data" / "thumbs", p                    # outside archive\ (not a backup/orphan matter)
    w, h = Image.open(p).size
    assert max(w, h) == 64 and (w, h) == (64, 43), (w, h)
    im = Image.open(p).convert("RGB")
    assert im.getpixel((0, 0)) == thumbs.FRAME and im.getpixel((w - 1, h - 1)) == thumbs.FRAME   # frame
    assert im.getpixel((w // 2, h // 2)) == (255, 0, 0)                                           # picture inside
    with CountCalls() as c:
        assert arc.thumbnail_for_document(d, 64) == p and c.n == 0           # cached
        p.unlink()
        assert arc.thumbnail_for_document(d, 64).is_file() and c.n == 1      # rebuilt when missing
        assert arc.thumbnail_for_document(d, 32).is_file() and c.n == 2      # another size = another file


def t_thumb_pdf():
    d = arc.add_document(mkpdf("t2.pdf", "Hello thumbnail"), name="Pdf scan")
    p = arc.thumbnail_for_document(d, 64)
    assert p is not None and max(Image.open(p).size) == 64


def t_thumb_none():
    docx = arc.add_document(mkfile("memo.docx"), name="Memo")
    bad = arc.add_document(mkfile("bad.png", b"not really a picture"), name="Broken picture")
    with CountCalls() as c:
        assert arc.thumbnail_for_document(docx) is None and c.n == 0         # not a picture: no attempt
        assert arc.thumbnail_for_document(bad) is None and c.n == 1
        assert arc.thumbnail_for_document(bad) is None and c.n == 1          # failure is remembered
    assert arc.thumbnail_for_document(999999) is None


def t_thumb_integrity():
    rep = arc.check_integrity(verify_hashes=True)
    assert rep["database_ok"] and rep["orphan_files"] == [] and rep["changed_files"] == [] and rep["missing_files"] == [], rep


def t_thumb_missing_file():
    d = arc.add_document(mkpng("t3.png", "blue", (120, 120)), name="Blue")
    Path(arc.get_document(d)["files"][0]["abs_path"]).unlink()
    assert arc.thumbnail_for_document(d, 64) is None                         # file gone: no crash


def t_make_thumbnail_direct():
    out = ROOT / "direct" / "x.png"
    assert thumbs.make_thumbnail(SRC / "t1.png", out, 50) and max(Image.open(out).size) == 50
    assert not thumbs.make_thumbnail(SRC / "memo.docx", ROOT / "direct" / "y.png", 50)
    assert not thumbs.make_thumbnail(SRC / "bad.png", ROOT / "direct" / "z.png", 50)
    assert not list((ROOT / "direct").glob("*.tmp"))


TESTS = [t_export_rows, t_export_filters, t_export_csv, t_export_xlsx, t_export_errors, t_export_audit,
         t_thumb_png, t_thumb_pdf, t_thumb_none, t_thumb_integrity, t_thumb_missing_file,
         t_make_thumbnail_direct]

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
