"""ui/type_manager.py - rename, merge and delete document types; edit their fields."""
import tkinter as tk
from tkinter import messagebox, ttk

from services import ArchiveError, DuplicateError, InUseError, norm
from ui.common import ModalWindow, ask_choice, ask_text
from ui.type_dialogs import DATA_TYPE_NAMES

_NAME_TO_TYPE = {v: k for k, v in DATA_TYPE_NAMES.items()}


class FieldDialog(ModalWindow):
    """Add a field to a type, or edit an existing one."""

    def __init__(self, parent, archive, type_id, field=None):
        super().__init__(parent, "Edit field" if field else "Add field")
        self.archive, self.type_id, self.field = archive, type_id, field
        self.done = False
        self.resizable(False, False)
        in_use = archive.field_use_count(field["id"]) if field else 0
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text="Field name").grid(row=0, column=0, sticky="w", pady=4)
        self.label_var = tk.StringVar(value=field["label"] if field else "")
        label = ttk.Entry(body, textvariable=self.label_var, width=34)
        label.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=4)

        ttk.Label(body, text="Data type").grid(row=1, column=0, sticky="w", pady=4)
        self.type_var = tk.StringVar(value=DATA_TYPE_NAMES[field["data_type"]] if field else DATA_TYPE_NAMES["text"])
        self.type_cb = ttk.Combobox(body, textvariable=self.type_var, state="readonly", width=32,
                                    values=list(DATA_TYPE_NAMES.values()))
        self.type_cb.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=4)
        self.type_cb.bind("<<ComboboxSelected>>", lambda e: self._type_changed())
        if in_use:
            self.type_cb.configure(state="disabled")
            ttk.Label(body, foreground="#666", wraplength=330, justify="left",
                      text=f"The data type is locked because {in_use} document(s) already have a value.").grid(
                row=2, column=1, sticky="w", padx=(10, 0))

        ttk.Label(body, text="Choices").grid(row=3, column=0, sticky="nw", pady=4)
        box = ttk.Frame(body)
        box.grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=4)
        self.choices = tk.Text(box, width=34, height=7, wrap="word", relief="solid", borderwidth=1)
        self.choices.pack(fill="x")
        ttk.Label(box, text="One choice per line (dropdown fields only).", foreground="#666").pack(anchor="w")
        if field and field["options"]:
            self.choices.insert("1.0", "\n".join(field["options"]))

        self.key_var = tk.BooleanVar(value=bool(field and field["is_key"]))
        ttk.Checkbutton(body, text="Use for duplicate check (e.g. Year + Version)",
                        variable=self.key_var).grid(row=4, column=1, sticky="w", padx=(10, 0), pady=4)

        row = ttk.Frame(body)
        row.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(row, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(row, text="Save", command=self._save).pack(side="right", padx=6)
        self._type_changed()
        label.focus_set()

    def _type_changed(self):
        is_dd = _NAME_TO_TYPE.get(self.type_var.get()) == "dropdown"
        self.choices.configure(state="normal" if is_dd else "disabled", bg="white" if is_dd else "#eee")

    def _choice_list(self):
        raw = self.choices.get("1.0", "end").replace(",", "\n").splitlines()
        return [o for o in (norm(x) for x in raw) if o]

    def _save(self):
        label = norm(self.label_var.get())
        if not label:
            messagebox.showerror("Field name", "Please enter a field name.", parent=self)
            self.regrab()
            return
        data_type = _NAME_TO_TYPE.get(self.type_var.get(), "text")
        try:
            if self.field is None:
                self.archive.add_field(self.type_id, label, data_type,
                                       self._choice_list() if data_type == "dropdown" else None,
                                       is_key=self.key_var.get())
            else:
                kwargs = {"label": label, "is_key": self.key_var.get()}
                if str(self.type_cb.cget("state")) != "disabled":
                    kwargs["data_type"] = data_type
                if data_type == "dropdown":
                    kwargs["options"] = self._choice_list()
                self.archive.update_field(self.field["id"], **kwargs)
        except (ValueError, ArchiveError) as e:
            messagebox.showerror("Cannot save field", str(e), parent=self)
            self.regrab()
            return
        self.done = True
        self.destroy()


class TypeManager(ModalWindow):
    def __init__(self, parent, archive, on_change=None):
        super().__init__(parent, "Document Types", "1000x560", (880, 460))
        self.archive, self.on_change = archive, on_change
        self.changed = False
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(pane)
        ttk.Label(left, text="Document types", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self.types = ttk.Treeview(left, columns=("name", "docs"), show="headings", selectmode="browse")
        self.types.heading("name", text="Type")
        self.types.heading("docs", text="Documents")
        self.types.column("name", width=190)
        self.types.column("docs", width=80, anchor="e")
        self.types.pack(fill="both", expand=True, pady=4)
        self.types.bind("<<TreeviewSelect>>", lambda e: self._load_fields())
        row = ttk.Frame(left)
        row.pack(fill="x")
        for text, cmd in (("Rename", self.rename_type), ("Merge into...", self.merge_type), ("Delete", self.delete_type)):
            ttk.Button(row, text=text, command=cmd).pack(side="left", padx=(0, 4))
        pane.add(left, weight=1)

        right = ttk.Frame(pane)
        self.fields_title = ttk.Label(right, text="Fields", font=("TkDefaultFont", 10, "bold"))
        self.fields_title.pack(anchor="w")
        self.fields = ttk.Treeview(right, columns=("label", "dtype", "choices", "key", "status"),
                                   show="headings", selectmode="browse")
        for col, text, w in (("label", "Field", 150), ("dtype", "Data type", 130), ("choices", "Choices", 170),
                             ("key", "Dup. check", 85), ("status", "Status", 65)):
            self.fields.heading(col, text=text)
            self.fields.column(col, width=w, anchor="w")
        self.fields.pack(fill="both", expand=True, pady=4)
        self.fields.bind("<Double-1>", lambda e: self.edit_field())
        row2 = ttk.Frame(right)
        row2.pack(fill="x")
        for text, cmd in (("Add field", self.add_field), ("Edit", self.edit_field),
                          ("Hide / Show", self.toggle_field), ("Up", lambda: self.move_field(-1)),
                          ("Down", lambda: self.move_field(1))):
            ttk.Button(row2, text=text, command=cmd).pack(side="left", padx=(0, 4))
        ttk.Label(right, foreground="#666", justify="left", wraplength=520, text=(
            "Hiding a field removes it from new forms but keeps the values already saved. "
            "Fields cannot be deleted, so no data is ever lost.")).pack(anchor="w", pady=(8, 0))
        pane.add(right, weight=3)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(bottom, text="Close", command=self.destroy).pack(side="right")
        self.bind("<Destroy>", self._on_destroy)
        self._load_types()

    def _on_destroy(self, ev):
        if ev.widget is self and self.changed and self.on_change:
            self.on_change()

    # ---- data
    def _selected_type(self):
        sel = self.types.selection()
        return int(sel[0]) if sel else None

    def _selected_field(self):
        sel = self.fields.selection()
        return int(sel[0]) if sel else None

    def _load_types(self, select=None):
        keep = select if select is not None else self._selected_type()
        self.types.delete(*self.types.get_children())
        for t in self.archive.list_types():
            self.types.insert("", "end", iid=str(t["id"]), values=(t["name"], t["doc_count"]))
        kids = self.types.get_children()
        if keep is not None and self.types.exists(str(keep)):
            self.types.selection_set(str(keep))
        elif kids:
            self.types.selection_set(kids[0])
        self._load_fields()

    def _load_fields(self, select=None):
        keep = select if select is not None else self._selected_field()
        self.fields.delete(*self.fields.get_children())
        tid = self._selected_type()
        if tid is None:
            self.fields_title.configure(text="Fields")
            return
        t = self.archive.get_type(tid, include_hidden=True)
        self.fields_title.configure(text=f"Fields of \u201c{t['name']}\u201d")
        for f in t["fields"]:
            self.fields.insert("", "end", iid=str(f["id"]), values=(
                f["label"], DATA_TYPE_NAMES.get(f["data_type"], f["data_type"]),
                ", ".join(f["options"])[:80], "Yes" if f["is_key"] else "", "" if f["is_active"] else "Hidden"))
        if keep is not None and self.fields.exists(str(keep)):
            self.fields.selection_set(str(keep))

    def _done(self, select_type=None, select_field=None):
        self.changed = True
        self._load_types(select_type)
        if select_field is not None:
            self._load_fields(select_field)

    def _error(self, title, e):
        messagebox.showerror(title, str(e), parent=self)
        self.regrab()

    # ---- type actions
    def rename_type(self):
        tid = self._selected_type()
        if tid is None:
            return
        old = self.archive.get_type(tid)["name"]
        new = ask_text(self, "Rename type", f"New name for \u201c{old}\u201d:", old)
        self.regrab()
        if not new or new == old:
            return
        try:
            self.archive.rename_type(tid, new)
        except (ValueError, ArchiveError) as e:
            return self._error("Cannot rename", e)
        self._done(tid)

    def merge_type(self):
        tid = self._selected_type()
        if tid is None:
            return
        src = self.archive.get_type(tid)["name"]
        others = [t["name"] for t in self.archive.list_types() if t["id"] != tid]
        if not others:
            return self._error("Merge", "There is no other type to merge into.")
        target = ask_choice(
            self, "Merge types",
            f"Merge \u201c{src}\u201d into which type?\n\nAll its documents move to that type and \u201c{src}\u201d is "
            "removed. Fields are matched by name; fields the other type does not have are added to it, so "
            "nothing is lost.", others, button="Merge")
        self.regrab()
        if not target:
            return
        if not messagebox.askyesno("Confirm merge", f"Merge \u201c{src}\u201d into \u201c{target}\u201d?\nThis cannot be undone.",
                                   parent=self):
            self.regrab()
            return
        self.regrab()
        try:
            res = self.archive.merge_types(tid, self.archive.find_type(target))
        except (ValueError, ArchiveError) as e:
            return self._error("Cannot merge", e)
        messagebox.showinfo("Merged", f"{res['documents_moved']} document(s) moved to \u201c{target}\u201d.\n"
                            f"{res['fields_added']} field(s) added to it.", parent=self)
        self.regrab()
        self._done(self.archive.find_type(target))

    def delete_type(self):
        tid = self._selected_type()
        if tid is None:
            return
        name = self.archive.get_type(tid)["name"]
        if not messagebox.askyesno("Delete type", f"Delete the type \u201c{name}\u201d?\n"
                                   "This only works if no document uses it.", parent=self):
            self.regrab()
            return
        self.regrab()
        try:
            self.archive.delete_type(tid)
        except (ValueError, ArchiveError) as e:
            return self._error("Cannot delete", e)
        self._done()

    # ---- field actions
    def add_field(self):
        tid = self._selected_type()
        if tid is None:
            return
        dlg = FieldDialog(self, self.archive, tid).run()
        self.regrab()
        if dlg.done:
            self._done(tid)

    def edit_field(self):
        tid, fid = self._selected_type(), self._selected_field()
        if tid is None or fid is None:
            return
        dlg = FieldDialog(self, self.archive, tid, self.archive.get_field(fid)).run()
        self.regrab()
        if dlg.done:
            self._done(tid, fid)

    def toggle_field(self):
        fid = self._selected_field()
        if fid is None:
            return
        f = self.archive.get_field(fid)
        if f["is_active"]:
            self.archive.hide_field(fid)
        else:
            self.archive.show_field(fid)
        self._done(self._selected_type(), fid)

    def move_field(self, step):
        fid = self._selected_field()
        if fid is None:
            return
        self.archive.move_field(fid, step)
        self._done(self._selected_type(), fid)
