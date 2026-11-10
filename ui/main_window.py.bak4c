"""ui/main_window.py - the main window: search, tag filter, results, preview."""
import logging
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import db
from services import format_value
from ui.activity_log import ActivityLog
from ui.add_dialog import FILE_TYPES, DocumentDialog, open_with_default_app
from ui.import_dialog import ImportDialog
from ui.pending_window import PendingWindow
from ui.maintenance import CheckDialog, start_backup
from ui.preview import Preview
from ui.recycle_bin import RecycleBin
from ui.settings_window import SettingsWindow
from ui.tag_manager import TagManager
from ui.type_manager import TypeManager

log = logging.getLogger("archive")

SORTS = {"Newest added": "added_desc", "Oldest added": "added_asc",
         "Name (A-Z)": "name", "Document date (newest)": "date_desc"}
ALL_TYPES = "All types"


class MainWindow:
    def __init__(self, root, archive):
        self.root = root
        self.archive = archive
        self.sel_tags = set()
        self._type_ids = {}
        self._tag_names = []
        self._after_id = None
        self._current_id = None
        self._current_files = []
        self._pending_win = None

        root.title("Office Document Archive")
        root.geometry("1320x780")
        root.minsize(1050, 620)
        scale = root.winfo_fpixels("1i") / 96
        ttk.Style(root).configure("Treeview", rowheight=int(24 * scale))
        base = tkfont.nametofont("TkDefaultFont")
        self.bold = base.copy()
        self.bold.configure(weight="bold")
        self.title_font = base.copy()
        self.title_font.configure(weight="bold", size=base.cget("size") + 2)

        self._build_menu()
        self._build_top()
        self._build_body()
        self._build_status()
        self._bind_keys()
        self._update_title()
        self.refresh_all()
        self.search_entry.focus_set()
        self.root.after(1500, self._startup_checks)
        self.root.after(2500, self._poll_pending)

    # ------------------------------------------------------------ layout
    def _build_menu(self):
        bar = tk.Menu(self.root)
        file_menu = tk.Menu(bar, tearoff=0)
        file_menu.add_command(label="Add Document...", accelerator="Ctrl+N", command=self.add_document)
        file_menu.add_command(label="Scanner inbox...", command=self.open_pending)
        file_menu.add_command(label="Import folder of scans...", command=self.import_folder)
        file_menu.add_command(label="Recycle Bin", command=self.open_recycle_bin)
        file_menu.add_separator()
        file_menu.add_command(label="Back up now", command=self.backup_now)
        file_menu.add_command(label="Settings...", command=self.open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        bar.add_cascade(label="File", menu=file_menu)
        manage = tk.Menu(bar, tearoff=0)
        manage.add_command(label="Document Types...", command=self.open_type_manager)
        manage.add_command(label="Tags...", command=self.open_tag_manager)
        bar.add_cascade(label="Manage", menu=manage)
        tools = tk.Menu(bar, tearoff=0)
        tools.add_command(label="Check archive...", command=self.check_archive)
        tools.add_command(label="Activity Log...", command=self.open_activity_log)
        bar.add_cascade(label="Tools", menu=tools)
        view = tk.Menu(bar, tearoff=0)
        view.add_command(label="Refresh", accelerator="F5", command=self.refresh_all)
        view.add_command(label="Clear filters", command=self.clear_filters)
        bar.add_cascade(label="View", menu=view)
        helpm = tk.Menu(bar, tearoff=0)
        helpm.add_command(label="About", command=self.about)
        bar.add_cascade(label="Help", menu=helpm)
        self.root.config(menu=bar)

    def _build_top(self):
        top = ttk.Frame(self.root, padding=(10, 8))
        top.pack(fill="x")
        ttk.Button(top, text="+ Add Document", command=self.add_document).pack(side="left")
        self.pending_btn = ttk.Button(top, text="Scanner inbox", command=self.open_pending)
        self.pending_btn.pack(side="left", padx=(8, 0))
        ttk.Label(top, text="Search").pack(side="left", padx=(18, 4))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(top, textvariable=self.search_var, width=38)
        self.search_entry.pack(side="left")
        self.search_var.trace_add("write", lambda *a: self._schedule_refresh())
        ttk.Label(top, text="Type").pack(side="left", padx=(14, 4))
        self.type_var = tk.StringVar(value=ALL_TYPES)
        self.type_cb = ttk.Combobox(top, textvariable=self.type_var, state="readonly", width=24)
        self.type_cb.pack(side="left")
        self.type_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(top, text="Sort").pack(side="left", padx=(14, 4))
        self.sort_var = tk.StringVar(value="Newest added")
        sort_cb = ttk.Combobox(top, textvariable=self.sort_var, state="readonly", width=22, values=list(SORTS))
        sort_cb.pack(side="left")
        sort_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(top, text="Clear filters", command=self.clear_filters).pack(side="left", padx=(14, 0))

    def _build_body(self):
        body = ttk.PanedWindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        # tag sidebar
        left = ttk.Frame(body, width=220)
        head = ttk.Frame(left)
        head.pack(fill="x")
        ttk.Label(head, text="Tags", font=self.bold).pack(side="left")
        ttk.Button(head, text="Clear", width=6, command=self.clear_tags).pack(side="right")
        self.tag_filter_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.tag_filter_var).pack(fill="x", pady=4)
        self.tag_filter_var.trace_add("write", lambda *a: self._refresh_tags())
        lf = ttk.Frame(left)
        lf.pack(fill="both", expand=True)
        self.tag_list = tk.Listbox(lf, selectmode="multiple", exportselection=False, activestyle="none")
        tsb = ttk.Scrollbar(lf, orient="vertical", command=self.tag_list.yview)
        self.tag_list.configure(yscrollcommand=tsb.set)
        self.tag_list.pack(side="left", fill="both", expand=True)
        tsb.pack(side="left", fill="y")
        self.tag_list.bind("<<ListboxSelect>>", self._on_tag_select)
        body.add(left, weight=0)

        # results
        mid = ttk.Frame(body)
        cols = ("name", "type", "ref", "date", "tags", "conf")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="browse")
        for col, text, w, stretch in (("name", "Name", 210, True), ("type", "Type", 110, False),
                                      ("ref", "Reference", 95, False), ("date", "Doc date", 80, False),
                                      ("tags", "Tags", 110, True), ("conf", "Conf.", 42, False)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, minwidth=40, stretch=stretch, anchor="w")
        vsb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.open_file())
        self.tree.bind("<Return>", lambda e: self.open_file())
        self.tree.bind("<Delete>", lambda e: self.delete_document())
        body.add(mid, weight=3)

        # preview + details
        base = tkfont.nametofont("TkDefaultFont")
        right = ttk.Frame(body, width=380)
        right.rowconfigure(0, weight=3)
        right.rowconfigure(2, weight=2)
        right.columnconfigure(0, weight=1)
        self.preview = Preview(right, width=380, height=360)
        self.preview.grid(row=0, column=0, sticky="nsew")
        self.file_list = tk.Listbox(right, height=3, exportselection=False)
        self.file_list.bind("<<ListboxSelect>>", self._on_file_pick)
        self.file_list.bind("<Double-1>", lambda e: self.open_file())
        self.file_list.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.file_list.grid_remove()
        dframe = ttk.Frame(right)
        dframe.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        self.details = tk.Text(dframe, height=9, wrap="word", state="disabled", relief="flat",
                               bg=self.root.cget("bg"), borderwidth=0, font=base)
        dsb = ttk.Scrollbar(dframe, orient="vertical", command=self.details.yview)
        self.details.configure(yscrollcommand=dsb.set)
        self.details.pack(side="left", fill="both", expand=True)
        dsb.pack(side="left", fill="y")
        self.details.tag_configure("title", font=self.title_font, spacing3=4)
        self.details.tag_configure("label", font=self.bold)
        btns = ttk.Frame(right)
        btns.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        self.open_btn = ttk.Button(btns, text="Open", command=self.open_file)
        self.folder_btn = ttk.Button(btns, text="Folder", command=self.show_in_folder)
        self.edit_btn = ttk.Button(btns, text="Edit", command=self.edit_document)
        self.delete_btn = ttk.Button(btns, text="Delete", command=self.delete_document)
        for i, b in enumerate((self.open_btn, self.folder_btn, self.edit_btn, self.delete_btn)):
            btns.columnconfigure(i, weight=1, uniform="b")
            b.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 4, 0))
        body.add(right, weight=1)
        self.body = body
        self._set_buttons(False)
        self.preview.clear()
        self.root.after(80, self._set_sashes)

    def _set_sashes(self):
        """Start with a roomy results table: tags 220 px, preview 420 px, the rest for results."""
        try:
            self.root.update_idletasks()
            total = self.body.winfo_width()
            if total > 700:
                self.body.sashpos(0, 220)
                self.body.sashpos(1, total - 420)
        except tk.TclError:
            pass

    def _build_status(self):
        self.status = tk.StringVar()
        ttk.Label(self.root, textvariable=self.status, relief="sunken", anchor="w",
                  padding=(8, 2)).pack(fill="x", side="bottom")

    def _bind_keys(self):
        self.root.bind("<Control-n>", lambda e: self.add_document())
        self.root.bind("<Control-f>", lambda e: (self.search_entry.focus_set(), self.search_entry.select_range(0, "end")))
        self.root.bind("<F5>", lambda e: self.refresh_all())

    def _set_buttons(self, enabled):
        state = "normal" if enabled else "disabled"
        for b in (self.open_btn, self.folder_btn, self.edit_btn, self.delete_btn):
            b.configure(state=state)

    # ------------------------------------------------------------ data refresh
    def refresh_all(self, select=None):
        types = self.archive.list_types()
        self._type_ids = {t["name"]: t["id"] for t in types}
        names = [ALL_TYPES] + [t["name"] for t in types]
        self.type_cb.configure(values=names)
        if self.type_var.get() not in names:
            self.type_var.set(ALL_TYPES)
        self._refresh_tags()
        self.refresh(select=select)

    def _schedule_refresh(self):
        if self._after_id:
            self.root.after_cancel(self._after_id)
        self._after_id = self.root.after(250, self.refresh)

    def refresh(self, select=None):
        self._after_id = None
        type_id = self._type_ids.get(self.type_var.get())
        try:
            res = self.archive.search(
                query=self.search_var.get(), type_id=type_id, tags=sorted(self.sel_tags),
                sort=SORTS.get(self.sort_var.get(), "added_desc"), limit=500)
        except Exception as e:
            log.exception("search failed")
            self.status.set(f"Search error: {e}")
            return
        keep = select if select is not None else self._current_id
        self.tree.delete(*self.tree.get_children())
        for r in res["results"]:
            self.tree.insert("", "end", iid=str(r["id"]), values=(
                r["name"], r["type_name"] or "", r["ref"], r["doc_date"] or "",
                ", ".join(r["tags"]), "Yes" if r["is_confidential"] else ""))
        shown, total = len(res["results"]), res["total"]
        filtering = bool(self.search_var.get().strip() or type_id or self.sel_tags)
        self.status.set(
            (f"{shown} of {total} documents shown" if shown < total else f"{total} document(s)")
            + (" (filtered)" if filtering else ""))
        if keep is not None and self.tree.exists(str(keep)):
            self.tree.selection_set(str(keep))
            self.tree.focus(str(keep))
            self.tree.see(str(keep))
        else:
            self._current_id = None
            self._show_details(None)

    def _refresh_tags(self):
        needle = self.tag_filter_var.get().strip().casefold()
        all_tags = self.archive.list_tags()
        self.sel_tags &= {t["name"] for t in all_tags}          # tags renamed or deleted elsewhere
        tags = [t for t in all_tags if t["uses"] > 0 or t["name"] in self.sel_tags]
        self._tag_names = []
        self.tag_list.delete(0, "end")
        for t in tags:
            if needle and needle not in t["name"].casefold():
                continue
            self._tag_names.append(t["name"])
            self.tag_list.insert("end", f"{t['name']} ({t['uses']})")
            if t["name"] in self.sel_tags:
                self.tag_list.selection_set("end")

    def _on_tag_select(self, ev=None):
        picked = set(self.tag_list.curselection())
        for i, name in enumerate(self._tag_names):
            if i in picked:
                self.sel_tags.add(name)
            else:
                self.sel_tags.discard(name)
        self.refresh()

    def clear_tags(self):
        self.sel_tags.clear()
        self._refresh_tags()
        self.refresh()

    def clear_filters(self):
        self.sel_tags.clear()
        self.tag_filter_var.set("")
        self.type_var.set(ALL_TYPES)
        self.search_var.set("")
        self._refresh_tags()
        self.refresh()

    # ------------------------------------------------------------ selection / details
    def _on_select(self, ev=None):
        sel = self.tree.selection()
        self._current_id = int(sel[0]) if sel else None
        self._show_details(self._current_id)

    def _show_details(self, doc_id):
        t = self.details
        t.configure(state="normal")
        t.delete("1.0", "end")
        self.file_list.grid_remove()
        self._current_files = []
        doc = self.archive.get_document(doc_id) if doc_id is not None else None
        if not doc:
            t.configure(state="disabled")
            self._set_buttons(False)
            self.preview.clear()
            return

        def row(label, value):
            if value not in (None, ""):
                t.insert("end", f"{label}: ", "label")
                t.insert("end", f"{value}\n")

        t.insert("end", doc["name"] + "\n", "title")
        row("Type", doc["type_name"] or "(none)")
        row("Document date", doc["doc_date"])
        for f in doc["fields"]:
            row(f["label"], format_value(f["data_type"], f["value"]))
        row("Tags", ", ".join(doc["tags"]))
        row("Notes", doc["notes"])
        row("Files", len(doc["files"]) if len(doc["files"]) > 1 else "")
        row("Confidential", "Yes" if doc["is_confidential"] else "")
        row("Added", doc["date_added"].replace("T", " "))
        t.configure(state="disabled")

        self._current_files = [Path(f["abs_path"]) for f in doc["files"]]
        if len(self._current_files) > 1:
            self.file_list.delete(0, "end")
            for i, f in enumerate(doc["files"], start=1):
                self.file_list.insert("end", f"{i}. {f['original_filename']}")
            self.file_list.selection_set(0)
            self.file_list.grid()
        if self._current_files:
            self.preview.show(self._current_files[0])
        else:
            self.preview.clear("No file attached")
        self._set_buttons(True)

    def _on_file_pick(self, ev=None):
        sel = self.file_list.curselection()
        if sel and sel[0] < len(self._current_files):
            self.preview.show(self._current_files[sel[0]])

    def _selected_file(self):
        if not self._current_files:
            return None
        sel = self.file_list.curselection() if self.file_list.winfo_ismapped() else ()
        return self._current_files[sel[0] if sel else 0]

    # ------------------------------------------------------------ actions
    def open_file(self):
        path = self._selected_file()
        if path is None:
            return
        if not path.exists():
            messagebox.showerror("File missing", f"The file could not be found:\n{path}", parent=self.root)
            return
        try:
            open_with_default_app(path)
        except Exception as e:
            messagebox.showerror("Cannot open file", str(e), parent=self.root)

    def show_in_folder(self):
        path = self._selected_file()
        if path is None:
            return
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", "/select,", str(path)])
            else:
                open_with_default_app(path.parent)
        except Exception as e:
            messagebox.showerror("Cannot open folder", str(e), parent=self.root)

    def add_document(self, prefill=None):
        while True:
            paths = filedialog.askopenfilenames(parent=self.root, title="Select scanned file(s)",
                                                filetypes=FILE_TYPES)
            if not paths:
                return
            dlg = DocumentDialog(self.root, self.archive, files=paths, prefill=prefill)
            self.root.wait_window(dlg)
            if not dlg.result:
                return
            self.refresh_all(select=dlg.result["doc_id"])
            prefill = dlg.result["prefill"]
            if not dlg.result["another"]:
                return

    def open_pending(self):
        win = self._pending_win
        try:
            if win is not None and win.winfo_exists():
                win.deiconify()
                win.lift()
                return
        except tk.TclError:
            pass
        self._pending_win = PendingWindow(self.root, self.archive, on_change=self._after_inbox_change)

    def _after_inbox_change(self, doc_id):
        if doc_id is not None:
            self.refresh_all(select=doc_id)
        self._poll_pending(reschedule=False)

    def _poll_pending(self, reschedule=True):
        """Show how many scans are waiting on the toolbar button (checked every 10 seconds)."""
        try:
            n = len(self.archive.pending_files()["files"])
            self.pending_btn.configure(text=f"Scanner inbox ({n})" if n else "Scanner inbox")
        except Exception:
            log.exception("inbox check failed")
        if reschedule:
            self.root.after(10000, self._poll_pending)

    def import_folder(self):
        dlg = ImportDialog(self.root, self.archive)
        self.root.wait_window(dlg)
        if dlg.result and dlg.result["imported"]:
            self.refresh_all()
            self.status.set(f"Imported {len(dlg.result['imported'])} document(s). "
                            f"Tick the tag \u201c{self.archive.REVIEW_TAG}\u201d to fill in their details.")

    def edit_document(self):
        if self._current_id is None:
            return
        dlg = DocumentDialog(self.root, self.archive, doc_id=self._current_id)
        self.root.wait_window(dlg)
        if dlg.result:
            self.refresh_all(select=dlg.result["doc_id"])
            self._show_details(dlg.result["doc_id"])

    def delete_document(self):
        if self._current_id is None:
            return
        doc = self.archive.get_document(self._current_id)
        if not doc:
            return
        if not messagebox.askyesno(
                "Delete document", f"Move \u201c{doc['name']}\u201d to the Recycle Bin?\n"
                "You can restore it from File > Recycle Bin.", parent=self.root):
            return
        self.archive.delete_document(self._current_id)
        self._current_id = None
        self.refresh_all()
        self.status.set(f"Moved \u201c{doc['name']}\u201d to the Recycle Bin")

    def open_recycle_bin(self):
        RecycleBin(self.root, self.archive, on_change=self.refresh_all)

    def _update_title(self):
        office = (self.archive.get_setting("office_name", "") or "").strip()
        self.root.title(f"{office} - Document Archive" if office else "Office Document Archive")

    def _startup_checks(self):
        """Once a day at most: remind about backups that are overdue."""
        try:
            if not self.archive.backup_due():
                return
            today = date.today().isoformat()
            if self.archive.get_setting("backup_prompt_date") == today:
                return
            self.archive.set_setting("backup_prompt_date", today)
            st = self.archive.backup_status()
            when = ("No backup has been made yet." if st["days_ago"] is None
                    else f"The last backup was {st['days_ago']} day(s) ago.")
            if messagebox.askyesno("Backup reminder", f"{when}\n\nBack up now?", parent=self.root):
                self.backup_now()
        except Exception:
            log.exception("backup reminder failed")

    def backup_now(self):
        start_backup(self.root, self.archive)

    def open_settings(self):
        SettingsWindow(self.root, self.archive, on_change=self._update_title).run()

    def open_type_manager(self):
        TypeManager(self.root, self.archive, on_change=self.refresh_all).run()

    def open_tag_manager(self):
        TagManager(self.root, self.archive, on_change=self.refresh_all).run()

    def check_archive(self):
        CheckDialog(self.root, self.archive).run()

    def open_activity_log(self):
        ActivityLog(self.root, self.archive).run()

    def about(self):
        n_docs = self.archive.search(limit=1)["total"]
        messagebox.showinfo(
            "About", "Office Document Archive\n\n"
            f"Documents: {n_docs}\nDocument types: {len(self.archive.list_types())}\n"
            f"Database version: {db.schema_version(self.archive.conn)}\n\n"
            f"Data folder:\n{self.archive.data_dir}", parent=self.root)
