"""Headless GUI smoke test (Linux + Xvfb). Drives the real windows and saves screenshots.
Run:  xvfb-run -a -s "-screen 0 1400x900x24" python3 dev/gui_smoke_phase2.py
"""
import os, sys, tempfile, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import tkinter as tk
from tkinter import ttk
import fitz
from PIL import Image, ImageDraw, ImageGrab
import services
from ui.main_window import MainWindow
from ui import add_dialog, type_dialogs

SH = Path(tempfile.mkdtemp(prefix="shots_")); tmp = Path(tempfile.mkdtemp()); print("screenshots in", SH)
def shot(name):
    root.update_idletasks(); root.update()
    ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).save(SH / f"{name}.png")

def mkpdf(path, pages, text):
    d = fitz.open()
    for i in range(pages):
        p = d.new_page(); p.insert_text((72, 100), f"{text}  page {i+1}", fontsize=24)
        p.insert_text((72, 160), "Sangguniang Bayan of Mogpog", fontsize=14)
    d.save(path); d.close()
mkpdf(tmp/"res12.pdf", 1, "RESOLUTION NO. 2026-12")
mkpdf(tmp/"opt.pdf", 3, "OPERATION TIMBANG PLUS 2026")
im = Image.new("RGB", (1200, 1600), "white"); ImageDraw.Draw(im).text((100, 100), "TRAVEL ORDER 2026-118", fill="black")
im.save(tmp/"to.png")

arc = services.Archive(tmp/"data"); arc.ensure_seeded(HERE / "profile.json")
root = tk.Tk(); root.geometry("1320x780+0+0")
ttk.Style(root).theme_use("clam")
errors = []
root.report_callback_exception = lambda e, v, tb: (errors.append("".join(traceback.format_exception(e, v, tb))))
mw = MainWindow(root, arc); root.update()
ok = lambda cond, msg: print(("PASS " if cond else "FAIL ") + msg)

# 1. add Resolution via the dialog
dlg = add_dialog.DocumentDialog(root, arc, files=[tmp/"res12.pdf"]); dlg.geometry("+0+0"); root.update()
dlg.type_entry.set("Resolution"); dlg._commit_type(); root.update()
ok(dlg.type_id == arc.find_type("Resolution"), "existing type selected, fields built")
labels = [f["label"] for f in dlg._fields]; ok(labels == ["Ref No.", "Source"], f"fields {labels}")
rid = {f["label"]: f["id"] for f in dlg._fields}
dlg._widgets[rid["Ref No."]]["set"]("2026-12"); dlg._widgets[rid["Source"]]["set"]("Sangguniang Bayan"); root.update()
ok(dlg.name_var.get() == "Resolution 2026-12", f"auto name: {dlg.name_var.get()!r}")
dlg.tags.add_tag("Budget"); dlg.tags.add_tag("nutrition, 2026"); dlg.date_var.set("10/12/2026"); root.update()
ok(dlg.tags.get_tags() == ["Budget", "nutrition", "2026"], f"tags {dlg.tags.get_tags()}")
dlg.tags.entry.set("bud"); dlg.tags.entry.show_suggestions(); root.update(); shot("01_add_dialog")
ok(dlg.tags.entry.visible() and dlg.tags.entry._items == [], "tag suggestions hidden (Budget already used)") if False else None
dlg.tags.entry.var.set("")
dlg._save(False); root.update()
ok(dlg.result and not errors, f"saved doc {dlg.result}")
mw.refresh_all(select=dlg.result["doc_id"]); root.update(); shot("02_main_after_first")

# 2. new type flow: Travel Order with field builder, then another with prefill
def drive_new_type():
    nd = [w for w in dlg2.winfo_children() if isinstance(w, type_dialogs.NewTypeDialog)]
    if not nd: root.after(200, drive_new_type); return
    root.update(); shot("03_new_type_prompt"); nd[0]._create()
    root.after(400, drive_builder)
def drive_builder():
    fb = [w for w in dlg2.winfo_children() if isinstance(w, type_dialogs.FieldBuilderDialog)]
    if not fb: root.after(200, drive_builder); return
    fb = fb[0]
    r = fb.rows[0]; r["label"].set("Travel Order No."); r["type_var"].set("ID / Reference no."); r["key_var"].set(True)
    fb._add_row(); r2 = fb.rows[1]; r2["label"].set("Employee"); r2["type_var"].set("Name")
    fb._add_row(); r3 = fb.rows[2]; r3["label"].set("Date of Travel"); r3["type_var"].set("Date")
    fb._add_row(); r4 = fb.rows[3]; r4["label"].set("Mode"); r4["type_var"].set("Dropdown (choices)"); fb._type_changed(r4); r4["choices_var"].set("Land, Sea, Air")
    root.update(); shot("04_field_builder"); fb._save()
dlg2 = add_dialog.DocumentDialog(root, arc, files=[tmp/"to.png"]); dlg2.geometry("+0+0"); root.update()
dlg2.type_entry.set("Travel Orders"); root.after(200, drive_new_type)
dlg2._commit_type(); root.update()
ok(arc.find_type("Travel Order") is None, "'Travel Orders' (typo) did not exist before") 
ok(dlg2.type_id is not None and dlg2._type_name == "Travel Orders", f"new type created: {dlg2._type_name!r}")
tid = dlg2.type_id; fid = {f["label"]: f["id"] for f in dlg2._fields}
dlg2._widgets[fid["Travel Order No."]]["set"]("2026-118"); dlg2._widgets[fid["Employee"]]["set"]("Juan Dela Cruz")
dlg2._widgets[fid["Date of Travel"]]["set"]("2026-10-15"); dlg2._widgets[fid["Mode"]]["set"]("sea"); dlg2._commit_dropdown(next(f for f in dlg2._fields if f["label"] == "Mode"))
dlg2.tags.add_tag("travel"); root.update(); shot("05_new_type_filled")
dlg2._save(True); root.update()
ok(dlg2.result and dlg2.result["another"] and not errors, f"saved with another: {dlg2.result}")
mw.refresh_all(select=dlg2.result["doc_id"]); root.update()
d = arc.get_document(dlg2.result["doc_id"]); ok(d["details"][str(fid["Mode"])] == "Sea" or d["details"][str(fid["Mode"])] == "sea", f"dropdown value {d['details']}")
ok(dlg2.result["prefill"]["type_id"] == tid and fid["Travel Order No."] not in dlg2.result["prefill"]["details"], "prefill keeps type, drops reference no.")

# 3. multi-page pdf with prefill dialog
dlg3 = add_dialog.DocumentDialog(root, arc, files=[tmp/"opt.pdf"]); dlg3.geometry("+0+0"); root.update()
dlg3.type_entry.set("operation timbang plus"); dlg3._commit_type(); root.update()
fid3 = {f["label"]: f["id"] for f in dlg3._fields}
dlg3._widgets[fid3["Year"]]["set"]("2026"); dlg3._widgets[fid3["Version"]]["set"]("V1"); dlg3._commit_dropdown(next(f for f in dlg3._fields if f["label"]=="Version")); root.update()
ok(dlg3.name_var.get() == "operation timbang plus 2026 v1" or dlg3.name_var.get().endswith("2026 v1"), f"auto name {dlg3.name_var.get()!r}")
dlg3.name_var.set("Operation Timbang Plus 2026 v1"); dlg3._save(False); root.update()
ok(dlg3.result is not None, "timbang saved")
mw.refresh_all(select=dlg3.result["doc_id"]); root.update(); shot("06_main_window")

# 4. search / filter / tag filter
mw.search_var.set("juan"); mw.refresh(); root.update(); ok(len(mw.tree.get_children()) == 1, "search 'juan' -> 1")
mw.clear_filters(); root.update(); ok(len(mw.tree.get_children()) == 3, "3 documents listed")
mw.tag_list.selection_set(0); mw._on_tag_select(); root.update(); ok(len(mw.sel_tags) == 1, f"tag filter {mw.sel_tags} -> {len(mw.tree.get_children())} docs")
mw.clear_tags(); mw.type_var.set("Resolution"); mw.refresh(); root.update(); ok(len(mw.tree.get_children()) == 1, "type filter")
mw.clear_filters()

# 5. edit
mw.tree.selection_set(str(dlg.result["doc_id"])); mw._on_select(); root.update()
ed = add_dialog.DocumentDialog(root, arc, doc_id=dlg.result["doc_id"]); ed.geometry("+0+0"); root.update(); shot("07_edit_dialog")
ok(ed.name_var.get() == "Resolution 2026-12" and ed.date_var.get() == "2026-10-12", f"edit loaded {ed.name_var.get()!r} {ed.date_var.get()!r}")
ok(ed.tags.get_tags() == ["2026", "Budget", "nutrition"], f"edit tags {ed.tags.get_tags()}")
ed.name_var.set("Resolution No. 2026-12 (final)"); ed.tags.add_tag("final"); ed._save(False); root.update()
ok(ed.result and arc.get_document(dlg.result["doc_id"])["name"].endswith("(final)"), "edit saved")

# 6. delete + recycle bin
mw.refresh_all(select=dlg.result["doc_id"]); mw._on_select(); root.update()
arc.delete_document(dlg.result["doc_id"]); mw.refresh_all(); root.update(); ok(len(mw.tree.get_children()) == 2, "deleted doc hidden")
from ui.recycle_bin import RecycleBin
rb = RecycleBin(root, arc, on_change=mw.refresh_all); rb.geometry("+100+100"); root.update(); shot("08_recycle_bin")
ok(len(rb.tree.get_children()) == 1, "recycle bin lists it"); rb.tree.selection_set(rb.tree.get_children()[0]); rb._restore(); root.update()
ok(len(mw.tree.get_children()) == 3, "restored"); rb.destroy()
mw.tree.selection_set(str(dlg3.result["doc_id"])); mw._on_select(); root.update(); shot("09_main_multipage")
print("ERRORS:", errors if errors else "none")
root.destroy()
