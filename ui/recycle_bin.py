"""ui/recycle_bin.py - restore or permanently delete documents."""
import tkinter as tk
from tkinter import messagebox, ttk

from services import ArchiveError
from ui.type_dialogs import _center


class RecycleBin(tk.Toplevel):
    def __init__(self, parent, archive, on_change=None):
        super().__init__(parent)
        self.archive = archive
        self.on_change = on_change
        self.title("Recycle Bin")
        self.transient(parent)
        self.geometry("720x420")
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Deleted documents. Restore them, or delete them permanently "
                             "(this also deletes their files).").pack(anchor="w", pady=(0, 6))
        frame = ttk.Frame(body)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("name", "type", "deleted"), show="headings", selectmode="extended")
        for col, text, w in (("name", "Name", 340), ("type", "Type", 170), ("deleted", "Deleted on", 140)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor="w")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        row = ttk.Frame(body)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text="Close", command=self.destroy).pack(side="right")
        ttk.Button(row, text="Delete permanently", command=self._purge).pack(side="right", padx=6)
        ttk.Button(row, text="Restore", command=self._restore).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())
        self._load()
        _center(self, parent)

    def _load(self):
        self.tree.delete(*self.tree.get_children())
        for d in self.archive.list_deleted():
            self.tree.insert("", "end", iid=str(d["id"]),
                             values=(d["name"], d["type_name"] or "", (d["deleted_at"] or "").replace("T", " ")))

    def _changed(self):
        self._load()
        if self.on_change:
            self.on_change()

    def _restore(self):
        for iid in self.tree.selection():
            try:
                self.archive.restore_document(int(iid))
            except ArchiveError as e:
                messagebox.showerror("Cannot restore", str(e), parent=self)
        self._changed()

    def _purge(self):
        ids = self.tree.selection()
        if not ids:
            return
        if not messagebox.askyesno(
                "Delete permanently",
                f"Permanently delete {len(ids)} document(s) and their files?\nThis cannot be undone.",
                icon="warning", parent=self):
            return
        for iid in ids:
            try:
                self.archive.purge_document(int(iid))
            except ArchiveError as e:
                messagebox.showerror("Cannot delete", str(e), parent=self)
        self._changed()
