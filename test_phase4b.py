r"""test_phase4b.py - checks the scanner inbox (watch folder), Phase 4b.
Uses a temporary folder and never touches your real data.

Run:  .venv\Scripts\python test_phase4b.py
"""
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

from services import Archive, ArchiveError

TMP = tempfile.TemporaryDirectory()
ROOT = Path(TMP.name)
INBOX = ROOT / "scanner"
INBOX.mkdir()
arc = Archive(ROOT / "data")


def put(name, content, age=30):
    p = INBOX / name
    p.write_bytes(content)
    t = time.time() - age
    os.utime(p, (t, t))
    return p


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


def names(res):
    return [f["name"] for f in res["files"]]


def t_not_set():
    res = arc.pending_files()
    assert res["folder"] is None and res["files"] == [] and res["error"] is None
    assert arc.get_watch_folder() is None


def t_set_folder():
    assert raises(ArchiveError, arc.set_watch_folder, ROOT / "nope")
    assert raises(ArchiveError, arc.set_watch_folder, arc.data_dir / "archive")
    arc.set_watch_folder(INBOX)
    assert arc.get_watch_folder() == INBOX
    assert any(r["action"] == "watch_folder" for r in arc.get_audit_log(10))


def t_pending_list():
    put("a.pdf", b"aaa", age=60)
    put("b.pdf", b"bbb", age=30)
    put("notes.txt", b"ignore")
    put(".hidden.pdf", b"hidden")
    sub = INBOX / "sub"
    sub.mkdir()
    (sub / "deep.pdf").write_bytes(b"deep")                      # sub-folders are not watched
    res = arc.pending_files()
    assert names(res) == ["a.pdf", "b.pdf"] and res["busy"] == 0, res          # oldest first


def t_still_writing():
    put("fresh.pdf", b"fresh", age=0)                             # modified just now
    res = arc.pending_files()
    assert "fresh.pdf" not in names(res) and res["busy"] == 1
    put("fresh.pdf", b"fresh", age=30)
    assert "fresh.pdf" in names(arc.pending_files())


def t_filed_disappears():
    arc.add_document(INBOX / "a.pdf", name="Filed A")
    res = arc.pending_files()
    assert "a.pdf" not in names(res) and "b.pdf" in names(res)
    put("a_copy.pdf", b"aaa")                                     # same content, other name
    assert "a_copy.pdf" not in names(arc.pending_files())
    doc = arc.search("Filed A")["results"][0]["id"]
    arc.delete_document(doc)                                      # still in the Recycle Bin: stays hidden
    assert "a.pdf" not in names(arc.pending_files())


def t_dismiss_and_restore():
    n = arc.ignore_files([INBOX / "b.pdf"])
    assert n == 1 and arc.ignored_count() == 1
    assert "b.pdf" not in names(arc.pending_files())
    assert arc.ignore_files([INBOX / "b.pdf"]) == 0               # already dismissed
    put("b_renamed.pdf", b"bbb")                                  # same content under a new name
    assert "b_renamed.pdf" not in names(arc.pending_files())
    assert arc.clear_ignored() == 2 - 1 and "b.pdf" in names(arc.pending_files())
    assert arc.clear_ignored() == 0


def t_changed_file_rehashed():
    p = put("grow.pdf", b"v1")
    assert "grow.pdf" in names(arc.pending_files())
    arc.add_document(p, name="Grow v1")
    assert "grow.pdf" not in names(arc.pending_files())
    p.write_bytes(b"version two, rescanned")                      # same name, new content
    t = time.time() - 30
    os.utime(p, (t, t))
    assert "grow.pdf" in names(arc.pending_files())


def t_folder_missing_and_off():
    other = ROOT / "gone"
    other.mkdir()
    arc.set_watch_folder(other)
    other.rmdir()
    res = arc.pending_files()
    assert res["files"] == [] and res["error"]
    arc.set_watch_folder("")
    assert arc.get_watch_folder() is None and arc.pending_files()["folder"] is None


TESTS = [t_not_set, t_set_folder, t_pending_list, t_still_writing, t_filed_disappears,
         t_dismiss_and_restore, t_changed_file_rehashed, t_folder_missing_and_off]

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
