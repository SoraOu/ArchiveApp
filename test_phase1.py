"""test_phase1.py - checks the Phase 1 logic. Uses a temporary folder, never touches your real data.

Run:  .venv\\Scripts\\python test_phase1.py
"""
import sys
import tempfile
import traceback
from pathlib import Path

from services import Archive, DuplicateError, DuplicateFileError, InUseError, ArchiveError

HERE = Path(__file__).resolve().parent
TMP = tempfile.TemporaryDirectory()
ROOT = Path(TMP.name)
SCANS = ROOT / "scans"
SCANS.mkdir()
arc = Archive(ROOT / "data")
S = {}  # shared state between tests


def scan(name, content):
    p = SCANS / name
    p.write_bytes(content)
    return p


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


def archive_files():
    return sorted(p for p in (ROOT / "data" / "archive").rglob("*") if p.is_file())


def t_schema():
    assert arc.conn.execute("PRAGMA user_version").fetchone()[0] == 1
    names = {r[0] for r in arc.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"documents", "doc_types", "type_fields", "tags", "document_tags",
            "document_files", "audit_log", "settings"} <= names


def t_seed():
    s = arc.ensure_seeded(HERE / "profile.json")
    assert s["types_created"] == 6, s
    assert arc.ensure_seeded(HERE / "profile.json") is None  # only once
    again = arc.seed_from_profile(HERE / "profile.json")
    assert again["types_created"] == 0 and again["fields_added"] == 0, again
    names = [t["name"] for t in arc.list_types()]
    assert "Resolution" in names and "Operation Timbang Plus" in names
    S["res"] = arc.find_type("resolution")
    S["tp"] = arc.find_type("Operation Timbang Plus")
    S["brgy"] = arc.find_type("BNC Directory")


def t_suggest_types():
    assert arc.suggest_types("resolutoin")[0] == "Resolution"      # typo
    assert arc.suggest_types("Resolutions")[0] == "Resolution"     # plural
    assert arc.suggest_types("exec")[0] == "Executive Order"       # prefix
    assert "BNS Database" in arc.suggest_types("database")         # contains


def t_create_type():
    assert "Travel Order" not in arc.similar_types("Memo")
    tid = arc.create_type("Travel Order", [
        {"label": "Travel Order No.", "data_type": "id", "is_key": True},
        {"label": "Employee", "data_type": "name"},
        {"label": "Destination", "data_type": "text"},
        {"label": "Date of Travel", "data_type": "date"}])
    S["travel"] = tid
    assert arc.similar_types("Travel Orders")[0] == "Travel Order"
    assert raises(DuplicateError, arc.create_type, "  travel   order ")
    labels = [x["label"] for x in arc.suggest_field_labels("yea")]
    assert "Year" in labels
    assert arc.suggest_field_labels("Ref")[0]["label"] == "Ref No."


def t_add_document():
    f = scan("res12.pdf", b"%PDF resolution 12")
    doc_id = arc.add_document(
        f, name="Resolution No. 2026-12", type_id=S["res"], doc_date="10/12/2026",
        details={"Ref No.": "2026-12", "Source": "Sangguniang Bayan"},
        tags=["Budget", "budget ", " Nutrition"], notes="Approved budget")
    S["res_doc"] = doc_id
    d = arc.get_document(doc_id)
    assert d["name"] == "Resolution No. 2026-12" and d["type_name"] == "Resolution"
    assert d["doc_date"] == "2026-10-12"
    assert d["tags"] == ["Budget", "Nutrition"], d["tags"]
    vals = {x["label"]: x["value"] for x in d["fields"]}
    assert vals == {"Ref No.": "2026-12", "Source": "Sangguniang Bayan"}, vals
    fi = d["files"][0]
    assert fi["exists"] and not fi["path"].startswith("/") and "\\" not in fi["path"]
    assert Path(fi["abs_path"]).read_bytes() == b"%PDF resolution 12"
    assert Path(fi["abs_path"]).name.startswith(f"{doc_id}_")
    # name falls back to the file name
    d2 = arc.get_document(arc.add_document(scan("untitled scan.jpg", b"jpg-bytes")))
    assert d2["name"] == "untitled scan" and d2["type_id"] is None


def t_duplicate_file():
    same = scan("copy_of_res12.pdf", b"%PDF resolution 12")
    try:
        arc.add_document(same, name="Again")
        assert False, "duplicate not detected"
    except DuplicateFileError as e:
        assert list(e.matches.values())[0][0]["doc_id"] == S["res_doc"]
    assert arc.check_duplicate_files([same])
    assert not arc.check_duplicate_files([scan("other.pdf", b"different")])
    before = arc.search()["total"]
    arc.add_document(same, name="Allowed copy", allow_duplicate_files=True)
    assert arc.search()["total"] == before + 1


def t_key_duplicates():
    det = {"Year": 2026, "Version": "v1"}
    assert arc.find_key_duplicates(S["tp"], det) == []
    arc.add_document(scan("tp1.pdf", b"timbang 2026 v1"), name="OPT+ 2026 v1", type_id=S["tp"], details=det)
    assert len(arc.find_key_duplicates(S["tp"], det)) == 1
    assert arc.find_key_duplicates(S["tp"], {"Year": "2026", "Version": "V1"})        # case-insensitive
    assert arc.find_key_duplicates(S["tp"], {"Year": 2026, "Version": "v2"}) == []
    assert arc.find_key_duplicates(S["tp"], {"Year": 2026}) == []                      # incomplete key
    r = arc.search("2026 v1", type_id=S["tp"])["results"][0]
    assert r["ref"] == "2026 | v1", r["ref"]


def t_validation():
    f = scan("bad.pdf", b"bad file")
    for details in ({"Year": "202", "Version": "v1"}, {"Year": 2026, "Version": "v9"},
                    {"Nonsense": "x"}):
        assert raises(ValueError, arc.add_document, f, name="x", type_id=S["tp"], details=details), details
    assert raises(ValueError, arc.add_document, f, name="x", type_id=S["travel"],
                  details={"Date of Travel": "not a date"})
    assert raises(ValueError, arc.add_document, f, name="x", doc_date="31/31/2026")
    assert raises(ValueError, arc.add_document, f, name="x", details={"Year": 2026})   # details need a type
    assert raises(FileNotFoundError, arc.add_document, SCANS / "missing.pdf")
    assert raises(ValueError, arc.add_document, [])


def t_atomic():
    docs_before = arc.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    files_before = archive_files()
    f = scan("atomic.pdf", b"atomic content")
    assert raises(ValueError, arc.add_document, f, name="Bad", type_id=S["tp"], details={"Year": "abc"})
    assert arc.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == docs_before
    assert archive_files() == files_before
    # a failure in the middle of copying leaves nothing behind
    good, bad = scan("g.pdf", b"good one"), scan("b.pdf", b"bad one")
    orig = arc.storage.store_file

    def flaky(src, doc_id, name, seq=0, expected_hash=None):
        if Path(src).name == "b.pdf":
            raise IOError("disk error")
        return orig(src, doc_id, name, seq, expected_hash)
    arc.storage.store_file = flaky
    try:
        assert raises(IOError, arc.add_document, [good, bad], name="Two files")
    finally:
        arc.storage.store_file = orig
    assert arc.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == docs_before
    assert archive_files() == files_before


def t_tags():
    names = [t["name"] for t in arc.list_tags()]
    assert names.count("Budget") == 1 and len(names) == len({n.casefold() for n in names})
    assert arc.suggest_tags("bud") == ["Budget"]
    assert arc.suggest_tags("nutriton")[0] == "Nutrition"     # typo
    assert "Budget" not in arc.suggest_tags("bud", exclude=["budget"])


def t_search():
    r = arc.search("sangguniang")                              # type detail value
    assert [x["id"] for x in r["results"]] == [S["res_doc"]]
    assert arc.search("approved BUDGET")["total"] == 1         # all words, any case, notes
    assert arc.search("copy_of_res12.pdf")["total"] == 1       # original file name
    assert arc.search("res12.pdf")["total"] == 2               # also matches the allowed copy
    assert arc.search("", tags=["budget", "nutrition"])["total"] == 1
    assert arc.search("", tags=["nope"])["total"] == 0
    assert arc.search("", type_id=S["res"])["total"] == 1
    assert arc.search("", date_from="2026-10-01", date_to="2026-10-31")["total"] == 1
    assert arc.search("", date_from="2026-11-01")["total"] == 0
    assert arc.search("100%")["total"] == 0                     # wildcard characters are literal
    assert arc.search("", limit=2)["total"] > 2 and len(arc.search("", limit=2)["results"]) == 2
    arc.update_document(S["res_doc"], confidential=True)
    assert arc.search("", type_id=S["res"], include_confidential=False)["total"] == 0
    arc.update_document(S["res_doc"], confidential=False)


def t_multifile():
    d = arc.add_document([scan("p1.png", b"page one"), scan("p2.png", b"page two")], name="Two pager")
    S["multi"] = d
    arc.add_files(d, scan("p3.png", b"page three"))
    files = arc.get_document(d)["files"]
    assert len(files) == 3 and all(f["exists"] for f in files)
    assert len({f["path"] for f in files}) == 3
    assert arc.search("p3.png")["total"] == 1


def t_update():
    d = S["res_doc"]
    arc.update_document(d, name="Resolution 12 (final)", tags=["Budget", "Final"])
    got = arc.get_document(d)
    assert got["name"] == "Resolution 12 (final)" and got["tags"] == ["Budget", "Final"]
    assert arc.search("final")["total"] == 1 and arc.search("nutrition")["total"] == 0
    assert raises(ValueError, arc.update_document, d, name="  ")
    assert raises(ValueError, arc.update_document, d, details={"Ref No.": "x", "Year": 1})
    arc.update_document(d, details={"Ref No.": "2026-13", "Source": "Mayor"})      # replace details
    assert arc.search("2026-13")["total"] == 1 and arc.search("sangguniang")["total"] == 0
    arc.update_document(d, type_id=S["travel"])                                     # type change clears details
    assert arc.get_document(d)["details"] == {}
    arc.update_document(d, type_id=S["res"], details={"Ref No.": "2026-12", "Source": "Sangguniang Bayan"})
    arc.update_document(d, doc_date=None)
    assert arc.get_document(d)["doc_date"] is None


def t_delete_restore_purge():
    d = S["multi"]
    paths = [Path(f["abs_path"]) for f in arc.get_document(d)["files"]]
    arc.delete_document(d)
    assert arc.search("two pager")["total"] == 0
    assert [x["id"] for x in arc.list_deleted()] == [d]
    assert all(p.exists() for p in paths)
    assert raises(ArchiveError, arc.delete_document, d)
    arc.restore_document(d)
    assert arc.search("two pager")["total"] == 1
    assert raises(ArchiveError, arc.purge_document, d)           # must be in the bin first
    arc.delete_document(d)
    arc.purge_document(d)
    assert arc.get_document(d) is None and not any(p.exists() for p in paths)
    assert arc.conn.execute("SELECT COUNT(*) FROM document_files WHERE document_id=?", (d,)).fetchone()[0] == 0


def t_field_rules():
    brgy_field = next(f for f in arc.get_type(S["brgy"])["fields"] if f["label"] == "Barangay")
    year_field = next(f for f in arc.get_type(S["brgy"])["fields"] if f["label"] == "Year")
    assert len(brgy_field["options"]) == 37
    assert raises(ValueError, arc.add_document, scan("b1.pdf", b"bc1"), type_id=S["brgy"],
                  details={"Year": 2026, "Barangay": "Atlantis"})
    assert arc.add_field_option(brgy_field["id"], "Atlantis") == "Atlantis"      # add a missing choice
    assert arc.add_field_option(brgy_field["id"], "atlantis") == "Atlantis"      # no duplicates
    arc.add_document(scan("b2.pdf", b"bc2"), name="BNC Atlantis", type_id=S["brgy"],
                     details={"Year": 2026, "Barangay": "atlantis"})
    assert arc.search("atlantis")["results"][0]["ref"] == "2026 | Atlantis"
    # data-type lock and option protection once a field holds data
    assert raises(InUseError, arc.update_field, year_field["id"], data_type="text")
    assert raises(InUseError, arc.update_field, brgy_field["id"], options=["Anapog"])
    arc.update_field(year_field["id"], label="Year of Coverage")                  # renaming is fine
    assert arc.search("2026", type_id=S["brgy"])["total"] == 1
    # an unused field can change type; hiding keeps saved values
    new_id = arc.add_field(S["res"], "Page count", "text")
    arc.update_field(new_id, data_type="number")
    assert arc.get_field(new_id)["data_type"] == "number"
    assert raises(DuplicateError, arc.add_field, S["res"], "page COUNT", "text")
    src = next(f for f in arc.get_type(S["res"])["fields"] if f["label"] == "Source")
    arc.hide_field(src["id"])
    assert "Source" not in [f["label"] for f in arc.get_type(S["res"])["fields"]]
    assert "Source" in [f["label"] for f in arc.get_document(S["res_doc"])["fields"]]
    # editing a document keeps values of hidden fields when they are passed back by id
    doc = arc.get_document(S["res_doc"])
    arc.update_document(S["res_doc"], details={int(k): v for k, v in doc["details"].items()}, notes="edited")
    assert arc.get_document(S["res_doc"])["details"] == doc["details"]


def t_filenames():
    f = scan("weird.pdf", b"weird name content")
    d = arc.add_document(f, name='Memo: "Budget" <2026>/final?*|')
    assert Path(arc.get_document(d)["files"][0]["abs_path"]).is_file()
    assert raises(ValueError, arc.storage.abs_path, "../../outside.txt")


def t_audit():
    actions = {r["action"] for r in arc.get_audit_log(1000)}
    assert {"add", "edit", "delete", "restore", "purge", "type_create", "field_add"} <= actions, actions


def t_reopen():
    path = ROOT / "data"
    total = arc.search()["total"]
    arc.close()
    again = Archive(path)
    assert again.search()["total"] == total
    assert again.ensure_seeded(HERE / "profile.json") is None
    again.close()


TESTS = [t_schema, t_seed, t_suggest_types, t_create_type, t_add_document, t_duplicate_file,
         t_key_duplicates, t_validation, t_atomic, t_tags, t_search, t_multifile, t_update,
         t_delete_restore_purge, t_field_rules, t_filenames, t_audit, t_reopen]

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
        TMP.cleanup()
    except Exception:
        pass
    sys.exit(1 if failed else 0)
