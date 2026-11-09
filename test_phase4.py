r"""test_phase4.py - checks bulk import (Phase 4a).
Uses a temporary folder and never touches your real data.

Run:  .venv\Scripts\python test_phase4.py
"""
import sys
import tempfile
import traceback
from pathlib import Path

from services import Archive, ArchiveError

HERE = Path(__file__).resolve().parent
TMP = tempfile.TemporaryDirectory()
ROOT = Path(TMP.name)
INBOX = ROOT / "inbox"
(INBOX / "2025" / "Q1").mkdir(parents=True)
arc = Archive(ROOT / "data")
arc.ensure_seeded(HERE / "profile.json")
S = {}


def put(rel, content):
    p = INBOX / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


def t_scan_folder():
    put("one.pdf", b"one")
    put("two.JPG", b"two")
    put("2025/Q1/three.png", b"three")
    put("notes.txt", b"ignore me")
    put("~$temp.pdf", b"office temp")
    put(".hidden.pdf", b"hidden")
    names = [p.name for p in arc.scan_folder(INBOX)]
    assert sorted(names) == ["one.pdf", "three.png", "two.JPG"], names
    assert [p.name for p in arc.scan_folder(INBOX, recursive=False)] == ["one.pdf", "two.JPG"]
    assert raises(ArchiveError, arc.scan_folder, ROOT / "nope")
    # the archive's own data folder is never scanned
    inside = arc.data_dir / "archive" / "x.pdf"
    inside.parent.mkdir(parents=True, exist_ok=True)
    inside.write_bytes(b"x")
    assert all("archive" not in p.parts for p in arc.scan_folder(ROOT))
    inside.unlink()


def t_import_basic():
    res = arc.find_type("Resolution")
    files = arc.scan_folder(INBOX)
    seen = []
    rep = arc.import_files(files, type_id=res, tags=["2025", "Scans"], progress=lambda i, n, name: seen.append((i, n)))
    assert len(rep["imported"]) == 3 and not rep["skipped"] and not rep["failed"] and not rep["cancelled"]
    assert seen[-1] == (3, 3)
    first = next(r for r in rep["imported"] if r["name"] == "one")
    d = arc.get_document(first["doc_id"])
    assert d["name"] == "one" and d["type_name"] == "Resolution"
    assert d["tags"] == sorted(["2025", "Needs details", "Scans"], key=str.casefold)
    assert d["files"][0]["exists"] and d["files"][0]["original_filename"] == "one.pdf"
    assert arc.search("", tags=["Needs details"])["total"] == 3
    assert arc.search("three")["total"] == 1                      # file name is searchable
    S["first"] = first["doc_id"]


def t_import_duplicates():
    put("copy_of_one.pdf", b"one")                                 # same content as one.pdf
    put("four.pdf", b"four")
    put("four_again.pdf", b"four")                                 # duplicate inside the same batch
    files = [p for p in arc.scan_folder(INBOX) if p.name in ("copy_of_one.pdf", "four.pdf", "four_again.pdf")]
    rep = arc.import_files(files)
    assert [r["name"] for r in rep["imported"]] == ["four"], rep
    assert len(rep["skipped"]) == 2 and rep["skipped"][0]["matches"][0]["doc_id"] in (S["first"], rep["imported"][0]["doc_id"])
    again = arc.import_files(arc.scan_folder(INBOX))               # running it twice adds nothing
    assert again["imported"] == [] and len(again["skipped"]) == 6, again
    forced = arc.import_files([INBOX / "copy_of_one.pdf"], skip_duplicates=False, review_tag=None)
    assert len(forced["imported"]) == 1
    assert "Needs details" not in arc.get_document(forced["imported"][0]["doc_id"])["tags"]


def t_import_failures_and_cancel():
    rep = arc.import_files([INBOX / "missing.pdf", put("five.pdf", b"five")])
    assert len(rep["failed"]) == 1 and len(rep["imported"]) == 1       # one bad file does not stop the rest
    a, b = put("six.pdf", b"six"), put("seven.pdf", b"seven")
    calls = []
    rep = arc.import_files([a, b], cancel=lambda: bool(calls) or calls.append(1))
    assert rep["cancelled"] and [r["name"] for r in rep["imported"]] == ["six"]   # stopped before the 2nd file
    assert raises(ArchiveError, arc.import_files, [a], type_id=99999)


def t_import_required_type():
    t = arc.create_type("Strict", [{"label": "Code", "data_type": "id", "is_required": True}])
    before = arc.search()["total"]
    assert raises(ArchiveError, arc.import_files, [INBOX / "seven.pdf"], type_id=t)
    assert arc.search()["total"] == before and arc.search("seven")["total"] == 0


def t_audit():
    assert any(r["action"] == "bulk_import" for r in arc.get_audit_log(100))
    rep = arc.check_integrity(verify_hashes=True)
    assert rep["database_ok"] and rep["missing_files"] == [] and rep["orphan_files"] == [] and rep["changed_files"] == []


TESTS = [t_scan_folder, t_import_basic, t_import_duplicates, t_import_failures_and_cancel,
         t_import_required_type, t_audit]

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
