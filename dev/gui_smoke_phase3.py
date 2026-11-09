"""Headless GUI smoke test (Linux + Xvfb). Drives the real windows and saves screenshots.
Run:  xvfb-run -a -s "-screen 0 1400x900x24" python3 dev/gui_smoke_phase3.py
"""
import os, sys, tempfile, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageGrab
import services
from ui.main_window import MainWindow
from ui import tag_manager, type_manager, maintenance, settings_window, activity_log

SH = Path(tempfile.mkdtemp(prefix="shots_")); tmp = Path(tempfile.mkdtemp()); print("screenshots in", SH)
def shot(name):
    root.update_idletasks(); root.update(); time.sleep(0.2); root.update()
    ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).save(SH / f"{name}.png")
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg)
def pump(until, timeout=20):
    t = time.time()
    while not until() and time.time() - t < timeout: root.update(); time.sleep(0.02)
    return until()

arc = services.Archive(tmp/"data"); arc.ensure_seeded(HERE / "profile.json")
res, eo = arc.find_type("Resolution"), arc.find_type("Executive Order")
def mk(name, content): p = tmp/name; p.write_bytes(content); return p
arc.add_document(mk("a.pdf", b"a1"), name="Resolution 1", type_id=res, details={"Ref No.": "1", "Source": "SB"}, tags=["Budget", "Nutrition"])
arc.add_document(mk("b.pdf", b"b2"), name="Resolution 2", type_id=res, details={"Ref No.": "2"}, tags=["budgets", "nutrition programs"])
arc.add_document(mk("c.pdf", b"c3"), name="EO 1", type_id=eo, details={"Ref No.": "EO-1"}, tags=["Bud-get", "Nutrition Program"])

root = tk.Tk(); root.geometry("1320x780+0+0"); ttk.Style(root).theme_use("clam")
errors = []
root.report_callback_exception = lambda e, v, tb: errors.append("".join(traceback.format_exception(e, v, tb)))
calls = []
messagebox.askyesno = lambda *a, **k: (calls.append(("askyesno", a[:2])) or True)
messagebox.showinfo = lambda *a, **k: calls.append(("showinfo", a[:2]))
messagebox.showerror = lambda *a, **k: calls.append(("showerror", a[:2]))
mw = MainWindow(root, arc); root.update()

# ---------------- Tag Manager
tm = tag_manager.TagManager(root, arc, on_change=mw.refresh_all); tm.geometry("+80+60"); root.update()
names = [tm.tree.set(i, "tag") for i in tm.tree.get_children()]
ok(len(names) == 6, f"tag manager lists {names}")
shot("10_tag_manager")
sim = {tm.tree.set(i, "tag"): tm.tree.set(i, "similar") for i in tm.tree.get_children()}
ok(sim["Budget"] and sim["Bud-get"] and sim["nutrition programs"] == "Nutrition Program", f"similar column {sim}")
tm.dup_var.set(True); tm._load(); only = [tm.tree.set(i, "tag") for i in tm.tree.get_children()]
ok("Nutrition" not in only and "Budget" in only, f"duplicates filter {only}")
tm.dup_var.set(False); tm._load()
ids = [i for i in tm.tree.get_children() if tm.tree.set(i, "tag") in ("Budget", "budgets", "Bud-get")]
tm.tree.selection_set(ids); tag_manager.ask_choice = lambda *a, **k: "Budget"
tm.merge(); root.update()
ok(arc.find_tag("budgets") is None and arc.search("", tags=["budget"])["total"] == 3, "merge via UI -> 3 docs tagged Budget")
tid = [i for i in tm.tree.get_children() if tm.tree.set(i, "tag") == "nutrition programs"][0]
tm.tree.selection_set(tid); tag_manager.ask_text = lambda *a, **k: "Nutrition Programs"; tm.rename(); root.update()
ok(arc.find_tag("Nutrition Programs") is not None, "rename via UI")
tm.destroy(); root.update()
ok("Budget" in [mw.tag_list.get(i).split(" (")[0] for i in range(mw.tag_list.size())], "main window tag list refreshed after manager closed")

# ---------------- Type Manager
ty = type_manager.TypeManager(root, arc, on_change=mw.refresh_all); ty.geometry("+60+60"); root.update()
ty.types.selection_set(str(res)); ty._load_fields(); root.update(); shot("11_type_manager")
ok([ty.fields.set(i, "label") for i in ty.fields.get_children()] == ["Ref No.", "Source"], "type manager shows fields of Resolution")
dlg = type_manager.FieldDialog(ty, arc, res); dlg.label_var.set("Series"); dlg.type_var.set("Number"); dlg._save(); ty._done(res)
ok("Series" in [ty.fields.set(i, "label") for i in ty.fields.get_children()], "add field via dialog")
fid = [i for i in ty.fields.get_children() if ty.fields.set(i, "label") == "Ref No."][0]
ed = type_manager.FieldDialog(ty, arc, res, arc.get_field(int(fid))); root.update()
ok(str(ed.type_cb.cget("state")) == "disabled", "data type locked for a field that has values")
ed.label_var.set("Reference No."); ed._save(); ty._done(res, int(fid))
ok(arc.get_field(int(fid))["label"] == "Reference No.", "edit field label via dialog")
ty.fields.selection_set(fid); ty.toggle_field(); ok(ty.fields.set(fid, "status") == "Hidden", "hide field"); ty.toggle_field()
ty.fields.selection_set(str(arc.get_type(res)["fields"][1]["id"])); ty.move_field(-1)
ty.types.selection_set(str(res)); type_manager.ask_text = lambda *a, **k: "Resolutions"; ty.rename_type(); root.update()
ok(arc.find_type("Resolutions") == res, "rename type via UI")
ty.types.selection_set(str(eo)); type_manager.ask_choice = lambda *a, **k: "Resolutions"; ty.merge_type(); root.update()
ok(arc.find_type("Executive Order") is None and arc.get_document(3)["type_name"] == "Resolutions", "merge types via UI")
ty.types.selection_set(str(res)); ty.delete_type(); ok(calls[-1][0] == "showerror", "delete type in use shows an error")
ty.destroy(); root.update()

# ---------------- Settings + backup
usb = tmp/"usb"; usb.mkdir()
st = settings_window.SettingsWindow(root, arc, on_change=mw._update_title); st.geometry("+100+80"); root.update()
st.office_var.set("MNO Mogpog"); st.backup_var.set(str(usb)); st.days_var.set("5"); root.update(); shot("12_settings")
st._save(); root.update()
ok(arc.get_setting("backup_dir") == str(usb) and arc.get_setting("backup_reminder_days") == "5", "settings saved")
ok(root.title() == "MNO Mogpog - Document Archive", f"title {root.title()!r}")
ok(arc.backup_due(), "backup due (never backed up)")
import ui.main_window as mwmod
real_start = mwmod.start_backup
started = []
mwmod.start_backup = lambda *a, **k: started.append(1)
calls.clear(); mw._startup_checks()
ok(calls and calls[0][0] == "askyesno" and "No backup" in calls[0][1][1] and started, "startup reminder asked and backup started on Yes")
calls.clear(); started.clear(); mw._startup_checks(); ok(not calls and not started, "reminder not repeated the same day")
mwmod.start_backup = real_start

# ---------------- Backup dialog (real thread)
bd = maintenance.BackupDialog(root, arc, str(usb)); bd.geometry("+150+120"); root.update()
ok(pump(lambda: bd._finished), "backup finished")
root.update(); shot("13_backup_done")
ok(bd.ok and arc.backup_status()["days_ago"] == 0 and not arc.backup_due(), "backup recorded, no longer due")
ok((usb / "OfficeArchiveBackup" / "db_snapshots").is_dir() and len(list((usb/"OfficeArchiveBackup"/"archive").rglob("*.pdf"))) == 3, "backup folder has snapshot and 3 files")
bd._on_button(); root.update()

# ---------------- Check archive
ck = maintenance.CheckDialog(root, arc); ck.geometry("+120+80"); root.update()
ck.start(); ok(pump(lambda: not ck._running), "check finished"); root.update()
txt = ck.text.get("1.0", "end"); ok("Everything looks fine" in txt, "check reports no problems"); shot("14_check_ok")
first = arc.get_document(1)["files"][0]; os.rename(first["abs_path"], first["abs_path"] + ".moved")
ck.start(); pump(lambda: not ck._running); root.update(); txt = ck.text.get("1.0", "end")
ok("missing" in txt and "issue(s) found" in txt and str(ck.orphan_btn.cget("state")) == "normal", "check finds a missing file and a stray file"); shot("15_check_problems")
ck._delete_orphans(); pump(lambda: not ck._running); root.update()
ok(ck._orphans == [], "stray file deleted")
os.rename(first["abs_path"] + ".moved", first["abs_path"]) if os.path.exists(first["abs_path"] + ".moved") else None
ck._close(); root.update()

# ---------------- Activity log
al = activity_log.ActivityLog(root, arc); al.geometry("+80+60"); root.update(); shot("16_activity_log")
rows = [al.tree.item(i, "values") for i in al.tree.get_children()]
ok(any(r[1] == "Tags merged" for r in rows) and any(r[1] == "Types merged" for r in rows) and any(r[1] == "Backup" for r in rows), f"activity log shows {len(rows)} rows incl. merges and backup")
al.destroy(); root.update()
mw.refresh_all(); shot("17_main_after")
print("ERRORS:", errors if errors else "none")
root.destroy()
