r"""test_phase3.py - checks tag/type management, backup, restore and the archive check.
Uses a temporary folder and never touches your real data.

Run:  .venv\Scripts\python test_phase3.py
"""
import json
import sys
import tempfile
import traceback
from pathlib import Path

import backup
from services import Archive, ArchiveError, DuplicateError, InUseError

HERE = Path(__file__).resolve().parent
TMP = tempfile.TemporaryDirectory()
ROOT = Path(TMP.name)
SCANS = ROOT / "scans"
SCANS.mkdir()
arc = Archive(ROOT / "data")
arc.ensure_seeded(HERE / "profile.json")
S = {}


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


def tag_id(name):
    return arc.find_tag(name)


def t_setup():
    S["res"], S["eo"] = arc.find_type("Resolution"), arc.find_type("Executive Order")
    S["d1"] = arc.add_document(scan("a.pdf", b"aaa"), name="Doc A", type_id=S["res"],
                               details={"Ref No.": "1", "Source": "SB"}, tags=["Budget", "budgets", "Nutrition"])
    S["d2"] = arc.add_document(scan("b.pdf", b"bbb"), name="Doc B", type_id=S["res"],
                               details={"Ref No.": "2"}, tags=["budget plan", "Nutrition"])
    S["d3"] = arc.add_document(scan("c.pdf", b"ccc"), name="Doc C", type_id=S["eo"],
                               details={"Ref No.": "EO-1", "Source": "Mayor"}, tags=["Bud-get"])


def t_tag_rename():
    arc.rename_tag(tag_id("budget plan"), "Budget Plan")
    assert arc.get_document(S["d2"])["tags"] == ["Budget Plan", "Nutrition"]
    assert arc.search("budget plan")["total"] == 1
    assert raises(DuplicateError, arc.rename_tag, tag_id("Budget Plan"), "nutrition")
    assert raises(ValueError, arc.rename_tag, tag_id("Budget Plan"), "  ")
    arc.rename_tag(tag_id("Nutrition"), "NUTRITION")                       # case-only change is fine
    assert "NUTRITION" in arc.get_document(S["d1"])["tags"]


def t_similar_tags():
    sim = arc.similar_tag_map()
    b, bs, bg = tag_id("Budget"), tag_id("budgets"), tag_id("Bud-get")
    assert sim[b]["id"] in (bs, bg) and sim[bs]["id"] in (b, bg)
    assert sim[bg]["ratio"] == 1.0 and sim[bg]["id"] == b and sim[b]["ratio"] == 1.0   # same letters, other dash
    assert tag_id("NUTRITION") not in sim


def t_tag_merge():
    keep = tag_id("Budget")
    n = arc.merge_tags([tag_id("budgets"), tag_id("Bud-get"), keep], keep)     # target in sources is ignored
    assert n == 2
    assert arc.find_tag("budgets") is None and arc.find_tag("Bud-get") is None
    assert arc.get_document(S["d1"])["tags"] == ["Budget", "NUTRITION"]
    assert arc.get_document(S["d3"])["tags"] == ["Budget"]
    assert arc.search("bud-get")["total"] == 0 and arc.search("", tags=["budget"])["total"] == 2
    assert raises(ArchiveError, arc.merge_tags, [keep], 99999)


def t_tag_delete():
    n = arc.delete_tag(tag_id("Budget Plan"))
    assert n == 1 and arc.get_document(S["d2"])["tags"] == ["NUTRITION"]
    assert raises(ArchiveError, arc.delete_tag, 99999)
    arc.add_document(scan("d.pdf", b"ddd"), name="Temp", tags=["lonely"])
    arc.purge_after = None
    doc = arc.search("temp")["results"][0]["id"]
    arc.update_document(doc, tags=[])                                          # tag now unused
    assert arc.delete_unused_tags() == 1 and arc.find_tag("lonely") is None
    arc.delete_document(doc)
    arc.purge_document(doc)


def t_rename_type():
    arc.rename_type(S["eo"], "Executive Orders")
    assert arc.search("executive orders")["total"] == 1 and arc.find_type("executive order") is None
    assert raises(DuplicateError, arc.rename_type, S["eo"], "resolution")
    arc.rename_type(S["eo"], "Executive Order")
    assert arc.search("", type_id=S["eo"])["results"][0]["type_name"] == "Executive Order"


def t_field_management():
    fields = arc.get_type(S["res"])["fields"]
    ref, src = fields[0]["id"], fields[1]["id"]
    arc.move_field(src, -1)
    assert [f["label"] for f in arc.get_type(S["res"])["fields"]] == ["Source", "Ref No."]
    arc.move_field(src, -1)                                                    # already first: no change
    arc.move_field(ref, 1)                                                     # already last: no change
    assert [f["label"] for f in arc.get_type(S["res"])["fields"]] == ["Source", "Ref No."]
    arc.hide_field(src)
    t = arc.get_type(S["res"], include_hidden=True)
    assert [f["is_active"] for f in t["fields"]] == [False, True]
    arc.show_field(src)
    assert len(arc.get_type(S["res"])["fields"]) == 2
    assert arc.field_use_count(ref) == 2 and arc.field_use_count(src) == 1


def t_delete_type():
    new = arc.create_type("Scratch Type", [{"label": "Foo", "data_type": "text"}])
    arc.delete_type(new)
    assert arc.find_type("Scratch Type") is None
    assert raises(InUseError, arc.delete_type, S["res"])                       # documents use it
    assert raises(ArchiveError, arc.delete_type, 99999)


def t_merge_types():
    # source: Memo (Memo No. id, Date date, Priority dropdown, Remarks text); target: Letter
    memo = arc.create_type("Memo", [
        {"label": "Memo No.", "data_type": "id", "is_key": True}, {"label": "Date", "data_type": "date"},
        {"label": "Priority", "data_type": "dropdown", "options": ["Low", "High"]},
        {"label": "Remarks", "data_type": "text"}])
    letter = arc.create_type("Letter", [
        {"label": "memo no.", "data_type": "text"}, {"label": "Priority", "data_type": "dropdown", "options": ["Normal", "High"]},
        {"label": "Subject", "data_type": "text"}])
    m1 = arc.add_document(scan("m1.pdf", b"m1"), name="Memo 1", type_id=memo, tags=["x"],
                          details={"Memo No.": "M-1", "Date": "2026-01-02", "Priority": "Low", "Remarks": "rush"})
    l1 = arc.add_document(scan("l1.pdf", b"l1"), name="Letter 1", type_id=letter, details={"Subject": "Hello"})
    res = arc.merge_types(memo, letter)
    assert res == {"documents_moved": 1, "fields_added": 2}, res                # Date + Remarks were added
    assert arc.find_type("Memo") is None
    d = arc.get_document(m1)
    vals = {f["label"]: f["value"] for f in d["fields"]}
    assert d["type_name"] == "Letter" and vals["memo no."] == "M-1" and vals["Priority"] == "Low", vals
    assert vals["Date"] == "2026-01-02" and vals["Remarks"] == "rush"
    prio = next(f for f in arc.get_type(letter)["fields"] if f["label"] == "Priority")
    assert prio["options"] == ["Normal", "High", "Low"]                         # options united
    assert arc.search("rush", type_id=letter)["total"] == 1 and arc.get_document(l1)["type_name"] == "Letter"
    # conflicting values stop the merge and change nothing
    a = arc.create_type("Alpha", [{"label": "Count", "data_type": "text"}])
    b = arc.create_type("Beta", [{"label": "Count", "data_type": "number"}])
    ad = arc.add_document(scan("al.pdf", b"al"), name="Alpha doc", type_id=a, details={"Count": "many"})
    assert raises(InUseError, arc.merge_types, a, b)
    assert arc.find_type("Alpha") == a and arc.get_document(ad)["type_id"] == a
    assert raises(ValueError, arc.merge_types, a, a)


def t_audit_names():
    log = arc.get_audit_log(500)
    assert any(r["action"] == "tags_merge" for r in log) and any(r["action"] == "types_merge" for r in log)
    adds = [r for r in log if r["action"] == "add" and r["doc_name"] == "Doc A"]
    assert adds


def t_backup_status():
    st = arc.backup_status()
    assert st["last_backup"] is None and st["days_ago"] is None and st["reminder_days"] == 7
    assert arc.backup_due()
    arc.record_backup({"files_copied": 3, "destination": "x"})
    assert not arc.backup_due() and arc.backup_status()["days_ago"] == 0
    arc.set_setting("last_backup", "2020-01-01T00:00:00")
    assert arc.backup_due()
    arc.set_setting("backup_reminder_days", "9999")
    assert not arc.backup_due()
    arc.set_setting("backup_reminder_days", "7")


def t_backup_and_restore():
    dest = ROOT / "usb"
    dest.mkdir()
    seen = []
    info = backup.run_backup(arc.data_dir, dest, progress=lambda i, n, name: seen.append((i, n)))
    n_files = len(arc.storage.all_files())
    assert info["files_total"] == n_files == info["files_copied"] and seen[-1] == (n_files, n_files)
    again = backup.run_backup(arc.data_dir, dest)
    assert again["files_copied"] == 0                                           # nothing new to copy
    newdoc = arc.add_document(scan("later.pdf", b"added later"), name="Later doc", tags=["late"])
    third = backup.run_backup(arc.data_dir, dest)
    assert third["files_copied"] == 1
    snaps = backup.list_snapshots(dest)
    assert len(snaps) >= 2 and snaps[0].name == third["snapshot"]
    # pruning keeps only the newest snapshots
    import time
    for _ in range(3):
        time.sleep(1.05)
        backup.run_backup(arc.data_dir, dest, keep_snapshots=2)
    assert len(backup.list_snapshots(dest)) == 2
    # destination checks
    assert raises(backup.BackupError, backup.run_backup, arc.data_dir, arc.data_dir / "archive")
    assert raises(backup.BackupError, backup.run_backup, arc.data_dir, ROOT / "nope")
    cancelled = False
    try:
        backup.run_backup(arc.data_dir, dest, cancel=lambda: True)
    except backup.BackupError as e:
        cancelled = "cancelled" in str(e)
    assert cancelled
    # restore into a new folder and open it
    out = ROOT / "restored"
    res = backup.restore_backup(dest, out)
    assert res["documents"] == arc.search(include_confidential=True, limit=500)["total"] + len(arc.list_deleted())
    assert res["missing_files"] == [], res
    other = Archive(out)
    assert other.search("later")["total"] == 1
    doc = other.get_document(newdoc)
    assert Path(doc["files"][0]["abs_path"]).read_bytes() == b"added later" and doc["files"][0]["exists"]
    assert len(other.list_types()) == len(arc.list_types())
    other.close()
    assert raises(backup.BackupError, backup.restore_backup, dest, out)          # target not empty
    assert raises(backup.BackupError, backup.restore_backup, ROOT / "scans", ROOT / "r2")   # no snapshots


def t_check_integrity():
    rep = arc.check_integrity()
    assert rep["database_ok"] and rep["missing_files"] == [] and rep["orphan_files"] == [] and rep["changed_files"] == []
    doc = arc.get_document(S["d1"])
    path = Path(doc["files"][0]["abs_path"])
    original = path.read_bytes()
    path.write_bytes(b"tampered")
    assert arc.check_integrity()["changed_files"] == []                          # fast check does not read contents
    rep = arc.check_integrity(verify_hashes=True)
    assert [c["doc_id"] for c in rep["changed_files"]] == [S["d1"]]
    path.write_bytes(original)
    path.rename(path.with_name("moved.pdf"))
    rep = arc.check_integrity()
    assert [m["doc_id"] for m in rep["missing_files"]] == [S["d1"]] and len(rep["orphan_files"]) == 1
    orphan = rep["orphan_files"][0]
    assert orphan.endswith("moved.pdf")
    assert arc.remove_orphan_files([doc["files"][0]["path"]]) == 0               # still referenced: refused
    assert arc.remove_orphan_files([orphan]) == 1
    # a leftover temp file is reported as an orphan too
    leftover = arc.storage.archive_dir / "2026" / "01" / "x.pdf.tmp"
    leftover.parent.mkdir(parents=True, exist_ok=True)
    leftover.write_bytes(b"x")
    assert arc.check_integrity()["orphan_files"] == ["2026/01/x.pdf.tmp"]
    arc.remove_orphan_files(["2026/01/x.pdf.tmp"])
    arc.storage.archive_dir.joinpath(doc["files"][0]["path"]).parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(original)                                                    # put the file back
    assert arc.check_integrity(verify_hashes=True)["missing_files"] == []


TESTS = [t_setup, t_tag_rename, t_similar_tags, t_tag_merge, t_tag_delete, t_rename_type,
         t_field_management, t_delete_type, t_merge_types, t_audit_names, t_backup_status,
         t_backup_and_restore, t_check_integrity]

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
