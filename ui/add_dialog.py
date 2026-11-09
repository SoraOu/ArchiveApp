"""ui/add_dialog.py - Add / Edit Document window."""
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import services
from services import ArchiveError, format_value, norm, suggest_from_list
from ui.preview import Preview
from ui.type_dialogs import FieldBuilderDialog, ask_new_type, _center
from ui.widgets import AutoSuggestEntry, TagInput

FILE_TYPES = [("Scans and documents", "*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp"),
              ("All files", "*.*")]
HINTS = {"date": "YYYY-MM-DD", "year": "4 digits", "number": "number"}


def open_with_default_app(path):
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)                                   # noqa: only exists on Windows
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class DocumentDialog(tk.Toplevel):
    """Add a document (files given) or edit one (doc_id given). Check .result after it closes:
    None if cancelled, else {"doc_id", "another", "prefill"}."""

    def __init__(self, parent, archive, files=None, doc_id=None, prefill=None):
        super().__init__(parent)
        self.archive = archive
        self.doc_id = doc_id
        self.files = [Path(f) for f in (files or [])]      # add mode: files to file
        self.new_files = []                                  # edit mode: extra files to attach
        self.result = None
        self.type_id = None
        self._type_name = ""
        self._busy = False
        self._fields = []
        self._widgets = {}
        self._auto_name = ""
        self._doc = None
        self._display_files = []

        self.title("Edit Document" if doc_id else "Add Document")
        self.transient(parent.winfo_toplevel())
        self.minsize(980, 680)
        self._build()
        if doc_id:
            self._load_document()
        elif prefill:
            self._apply_prefill(prefill)
        self._refresh_files()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())
        _center(self, parent.winfo_toplevel())
        self.wait_visibility()
        self._regrab()
        self.type_entry.focus_entry()

    # ------------------------------------------------------------ layout
    def _build(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(root, text="Scanned file(s)", padding=6)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.preview = Preview(left, width=340, height=430)
        self.preview.pack(fill="both", expand=True)
        self.file_list = tk.Listbox(left, height=4, exportselection=False)
        self.file_list.pack(fill="x", pady=(6, 4))
        self.file_list.bind("<<ListboxSelect>>", self._on_file_select)
        self.file_list.bind("<Double-1>", self._open_selected_file)
        row = ttk.Frame(left)
        row.pack(fill="x")
        ttk.Button(row, text="Add files...", command=self._add_files).pack(side="left")
        self.remove_btn = ttk.Button(row, text="Remove", command=self._remove_file)
        self.remove_btn.pack(side="left", padx=4)

        right = ttk.Frame(root)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)
        r = 0
        ttk.Label(right, text="Document type").grid(row=r, column=0, sticky="w", pady=4)
        self.type_entry = AutoSuggestEntry(
            right, self.archive.suggest_types, on_select=lambda t: self._commit_type(),
            on_commit=lambda t: self._commit_type(), show_button=True, max_rows=10)
        self.type_entry.entry.bind("<FocusOut>", lambda e: self._commit_type(), add="+")
        self.type_entry.grid(row=r, column=1, sticky="ew", padx=(8, 0), pady=4)
        ttk.Label(right, text="Pick an existing type or type a new one", foreground="#666").grid(
            row=r, column=2, sticky="w", padx=8)

        r += 1
        ttk.Label(right, text="Name").grid(row=r, column=0, sticky="w", pady=4)
        self.name_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.name_var).grid(row=r, column=1, sticky="ew", padx=(8, 0), pady=4)
        ttk.Label(right, text="Blank = use the file name", foreground="#666").grid(
            row=r, column=2, sticky="w", padx=8)

        r += 1
        ttk.Label(right, text="Document date").grid(row=r, column=0, sticky="w", pady=4)
        self.date_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.date_var, width=18).grid(row=r, column=1, sticky="w", padx=(8, 0), pady=4)
        ttk.Label(right, text="YYYY-MM-DD or MM/DD/YYYY", foreground="#666").grid(
            row=r, column=2, sticky="w", padx=8)

        r += 1
        self.fields_frame = ttk.LabelFrame(right, text="Details", padding=8)
        self.fields_frame.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        self.fields_frame.columnconfigure(1, weight=1)
        self.fields_frame.grid_remove()

        r += 1
        ttk.Label(right, text="Tags").grid(row=r, column=0, sticky="nw", pady=6)
        self.tags = TagInput(right, self.archive.suggest_tags)
        self.tags.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=6)

        r += 1
        ttk.Label(right, text="Notes").grid(row=r, column=0, sticky="nw", pady=4)
        self.notes = tk.Text(right, height=4, wrap="word", relief="solid", borderwidth=1)
        self.notes.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4)

        r += 1
        self.conf_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(right, text="Confidential (hidden from browser users later)",
                        variable=self.conf_var).grid(row=r, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=4)

        right.rowconfigure(r + 1, weight=1)
        bottom = ttk.Frame(right)
        bottom.grid(row=r + 2, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(bottom, text="Cancel", command=self._cancel).pack(side="right")
        ttk.Button(bottom, text="Save", command=lambda: self._save(False)).pack(side="right", padx=6)
        if not self.doc_id:
            ttk.Button(bottom, text="Save and add another",
                       command=lambda: self._save(True)).pack(side="right")

    # ------------------------------------------------------------ helpers
    def _regrab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _field_options(self, field_id):
        for f in self._fields:
            if f["id"] == field_id:
                return f["options"]
        return []

    # ------------------------------------------------------------ files
    def _all_files(self):
        if self.doc_id:
            return [Path(f["abs_path"]) for f in self._doc["files"]] + self.new_files
        return self.files

    def _refresh_files(self, select=0):
        files = self._all_files()
        self._display_files = files
        self.file_list.delete(0, "end")
        for i, p in enumerate(files, start=1):
            self.file_list.insert("end", f"{i}. {p.name}")
        if files:
            idx = min(select, len(files) - 1)
            self.file_list.selection_set(idx)
            self.preview.show(files[idx])
        else:
            self.preview.clear("No file selected")
        self.remove_btn.configure(state="normal" if self._removable() else "disabled")

    def _removable(self):
        if self.doc_id:
            return bool(self.new_files)
        return len(self.files) > 1

    def _on_file_select(self, ev=None):
        sel = self.file_list.curselection()
        if sel and sel[0] < len(self._display_files):
            self.preview.show(self._display_files[sel[0]])

    def _open_selected_file(self, ev=None):
        sel = self.file_list.curselection()
        if sel:
            try:
                open_with_default_app(self._display_files[sel[0]])
            except Exception as e:
                messagebox.showerror("Cannot open file", str(e), parent=self)

    def _add_files(self):
        paths = filedialog.askopenfilenames(parent=self, title="Add scanned files", filetypes=FILE_TYPES)
        self._regrab()
        if not paths:
            return
        target = self.new_files if self.doc_id else self.files
        for p in paths:
            if Path(p) not in target:
                target.append(Path(p))
        self._refresh_files(select=len(self._all_files()) - 1)

    def _remove_file(self):
        sel = self.file_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if self.doc_id:
            existing = len(self._doc["files"])
            if idx < existing:
                messagebox.showinfo("Cannot remove", "Files already in the archive cannot be removed here.", parent=self)
                self._regrab()
                return
            del self.new_files[idx - existing]
        elif len(self.files) > 1:
            del self.files[idx]
        self._refresh_files(select=max(idx - 1, 0))

    # ------------------------------------------------------------ type handling
    def _commit_type(self):
        if self._busy:
            return
        text = norm(self.type_entry.get())
        if text.casefold() == self._type_name.casefold():
            return
        self._busy = True
        try:
            if not text:
                self._set_type(None)
                return
            tid = self.archive.find_type(text)
            if tid is None:
                tid = self._create_new_type(text)
                self._regrab()
                if tid is None:
                    self.type_entry.set(self._type_name)
                    return
            self._set_type(tid)
        finally:
            self._busy = False

    def _create_new_type(self, text):
        similar = [s for s in self.archive.similar_types(text) if s.casefold() != text.casefold()]
        choice = ask_new_type(self, text, similar)
        self._regrab()
        if choice is None:
            return None
        if choice[0] == "existing":
            return self.archive.find_type(choice[1])
        fields = FieldBuilderDialog(self, self.archive, text).show()
        self._regrab()
        if fields is None:
            return None
        try:
            return self.archive.create_type(text, fields)
        except (ValueError, ArchiveError) as e:
            messagebox.showerror("Cannot create type", str(e), parent=self)
            self._regrab()
            return None

    def _set_type(self, type_id):
        self.type_id = type_id
        for w in self.fields_frame.winfo_children():
            w.destroy()
        self._widgets = {}
        self._fields = []
        if type_id is None:
            self._type_name = ""
            self.type_entry.set("")
            self.fields_frame.grid_remove()
            self._update_auto_name()
            return
        t = self.archive.get_type(type_id)
        self._type_name = t["name"]
        self.type_entry.set(t["name"])
        self._fields = t["fields"]
        self.fields_frame.configure(text=f"{t['name']} details")
        if not self._fields:
            ttk.Label(self.fields_frame, text="This type has no extra details.", foreground="#666").grid(
                row=0, column=0, sticky="w")
        for i, f in enumerate(self._fields):
            self._add_field_row(i, f)
        self.fields_frame.grid()
        self._update_auto_name()

    # ------------------------------------------------------------ type fields
    def _add_field_row(self, i, f):
        frame = self.fields_frame
        ttk.Label(frame, text=f["label"] + (" *" if f["is_required"] else "")).grid(
            row=i, column=0, sticky="nw", padx=(0, 8), pady=3)
        dt = f["data_type"]
        if dt == "dropdown":
            ent = AutoSuggestEntry(
                frame, lambda text, f=f: suggest_from_list(self._field_options(f["id"]), text, 12),
                on_select=lambda t, f=f: self._commit_dropdown(f),
                on_commit=lambda t, f=f: self._commit_dropdown(f), show_button=True, max_rows=10)
            ent.entry.bind("<FocusOut>", lambda e, f=f: self._commit_dropdown(f), add="+")
            ent.var.trace_add("write", lambda *a: self._update_auto_name())
            ent.grid(row=i, column=1, sticky="ew", pady=3)
            self._widgets[f["id"]] = {"get": ent.get, "set": ent.set, "kind": "dropdown"}
        elif dt == "yesno":
            var = tk.StringVar()
            ttk.Combobox(frame, textvariable=var, values=["", "Yes", "No"], state="readonly",
                         width=10).grid(row=i, column=1, sticky="w", pady=3)
            self._widgets[f["id"]] = {"get": var.get, "set": var.set, "kind": "yesno"}
        elif dt == "longtext":
            txt = tk.Text(frame, height=3, wrap="word", relief="solid", borderwidth=1)
            txt.grid(row=i, column=1, sticky="ew", pady=3)

            def put(value, txt=txt):
                txt.delete("1.0", "end")
                txt.insert("1.0", value)
            self._widgets[f["id"]] = {"get": lambda txt=txt: txt.get("1.0", "end").strip(),
                                      "set": put, "kind": "longtext"}
        else:
            var = tk.StringVar()
            ttk.Entry(frame, textvariable=var).grid(row=i, column=1, sticky="ew", pady=3)
            var.trace_add("write", lambda *a: self._update_auto_name())
            self._widgets[f["id"]] = {"get": var.get, "set": var.set, "kind": dt}
            if dt in HINTS:
                ttk.Label(frame, text=HINTS[dt], foreground="#666").grid(row=i, column=2, sticky="w", padx=8)

    def _commit_dropdown(self, f):
        if self._busy:
            return
        w = self._widgets.get(f["id"])
        if not w:
            return
        text = norm(w["get"]())
        if not text:
            return
        for opt in f["options"]:
            if opt.casefold() == text.casefold():
                if opt != w["get"]():
                    w["set"](opt)
                return
        self._busy = True
        try:
            if messagebox.askyesno("New choice", f"\u201c{text}\u201d is not in the list for {f['label']}.\n"
                                   "Add it as a new choice?", parent=self):
                opt = self.archive.add_field_option(f["id"], text)
                f["options"].append(opt)
                w["set"](opt)
            else:
                w["set"]("")
        finally:
            self._busy = False
            self._regrab()

    def _update_auto_name(self):
        if not self.type_id:
            return
        current = self.name_var.get().strip()
        if self.doc_id and current:
            return
        parts = []
        for f in self._fields:
            if f["is_key"] and f["id"] in self._widgets:
                v = self._widgets[f["id"]]["get"]().strip()
                if v:
                    parts.append(v)
        suggestion = " ".join([self._type_name] + parts) if parts else ""
        if current == "" or current == self._auto_name:
            self.name_var.set(suggestion)
            self._auto_name = suggestion

    def _set_field_value(self, f, value):
        w = self._widgets.get(f["id"])
        if w is not None and value is not None:
            w["set"](format_value(f["data_type"], value))

    # ------------------------------------------------------------ load / prefill
    def _load_document(self):
        doc = self.archive.get_document(self.doc_id)
        self._doc = doc
        self._set_type(doc["type_id"])
        self._type_name = doc["type_name"] or ""
        self.name_var.set(doc["name"])
        self._auto_name = ""
        self.date_var.set(doc["doc_date"] or "")
        for f in self._fields:
            self._set_field_value(f, doc["details"].get(str(f["id"])))
        self.tags.set_tags(doc["tags"])
        self.notes.insert("1.0", doc["notes"])
        self.conf_var.set(doc["is_confidential"])

    def _apply_prefill(self, p):
        if p.get("type_id"):
            self._set_type(p["type_id"])
            for f in self._fields:
                self._set_field_value(f, p.get("details", {}).get(f["id"]))
            self._update_auto_name()

    def _make_prefill(self, details):
        keep = {fid: v for fid, v in details.items()
                if next(f for f in self._fields if f["id"] == fid)["data_type"] != "id"}
        return {"type_id": self.type_id, "details": keep}

    # ------------------------------------------------------------ save
    def _collect_details(self):
        out = {}
        for f in self._fields:
            w = self._widgets[f["id"]]
            if w["kind"] == "dropdown":
                self._commit_dropdown(f)
            val = w["get"]().strip()
            if val:
                out[f["id"]] = val
        return out

    def _ref_text(self, details):
        return " | ".join(str(details[f["id"]]) for f in self._fields if f["is_key"] and f["id"] in details)

    def _confirm(self, title, message):
        ok = messagebox.askyesno(title, message, parent=self, icon="warning")
        self._regrab()
        return ok

    def _save(self, another):
        if self._busy:
            return
        self._commit_type()
        details = self._collect_details()
        name = norm(self.name_var.get())
        doc_date = self.date_var.get().strip() or None
        tags = self.tags.get_tags()
        pending = self.tags.entry.get().strip()
        if pending:
            tags.append(pending)
        notes = self.notes.get("1.0", "end").strip()
        confidential = self.conf_var.get()
        try:
            if self.doc_id is None and not self.files:
                raise ValueError("Select at least one file.")
            new_files = self.files if self.doc_id is None else self.new_files
            allow = False
            dups = self.archive.check_duplicate_files(new_files) if new_files else {}
            if dups:
                lines = []
                for path, matches in dups.items():
                    lines.append(f"\u2022 {Path(path).name}  is already filed as  \u201c{matches[0]['name']}\u201d"
                                 + (" (in the Recycle Bin)" if matches[0]["is_deleted"] else ""))
                if not self._confirm("File already in the archive",
                                     "\n".join(lines) + "\n\nFile it again anyway?"):
                    return
                allow = True
            if self.type_id:
                merged = dict(details)
                dup_docs = self.archive.find_key_duplicates(self.type_id, merged, exclude_id=self.doc_id)
                if dup_docs:
                    ref = self._ref_text(details)
                    if not self._confirm(
                            "Possible duplicate",
                            f"\u201c{dup_docs[0]['name']}\u201d already has the same {self._type_name} "
                            f"details ({ref}).\n\nSave this one anyway?"):
                        return
            if self.doc_id is None:
                doc_id = self.archive.add_document(
                    self.files, name=name, type_id=self.type_id, doc_date=doc_date, details=details,
                    tags=tags, notes=notes, confidential=confidential, allow_duplicate_files=allow)
            else:
                doc_id = self.doc_id
                full = dict(details)
                if self._doc and self.type_id == self._doc["type_id"]:
                    shown = {f["id"] for f in self._fields}
                    for k, v in self._doc["details"].items():
                        if int(k) not in shown:
                            full[int(k)] = v        # keep values of hidden fields
                self.archive.update_document(
                    doc_id, name=name, type_id=self.type_id, doc_date=doc_date, details=full,
                    tags=tags, notes=notes, confidential=confidential)
                if self.new_files:
                    self.archive.add_files(doc_id, self.new_files, allow_duplicate_files=allow)
        except ValueError as e:
            messagebox.showerror("Please check the form", str(e), parent=self)
            self._regrab()
            return
        except (ArchiveError, OSError) as e:
            messagebox.showerror("Could not save", str(e), parent=self)
            self._regrab()
            return
        self.result = {"doc_id": doc_id, "another": another,
                       "prefill": self._make_prefill(details) if another and self.type_id else None}
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()
