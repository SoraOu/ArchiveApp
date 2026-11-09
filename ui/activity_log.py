"""ui/activity_log.py - who did what: the audit log."""
from tkinter import ttk

from ui.common import ModalWindow

ACTIONS = {
    "add": "Document added", "add_files": "Files added", "edit": "Document edited", "delete": "Moved to Recycle Bin",
    "restore": "Restored", "purge": "Deleted permanently", "type_create": "Type created",
    "type_rename": "Type renamed", "type_delete": "Type deleted", "types_merge": "Types merged",
    "field_add": "Field added", "field_update": "Field changed", "field_hide": "Field hidden",
    "field_show": "Field shown", "field_option_add": "Choice added", "tag_rename": "Tag renamed",
    "tags_merge": "Tags merged", "tag_delete": "Tag deleted", "tags_cleanup": "Unused tags deleted",
    "backup": "Backup", "orphans_removed": "Stray files removed",
}


class ActivityLog(ModalWindow):
    def __init__(self, parent, archive):
        super().__init__(parent, "Activity Log", "900x520", (700, 380))
        self.archive = archive
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="The most recent 500 actions, newest first.").pack(anchor="w")
        frame = ttk.Frame(body)
        frame.pack(fill="both", expand=True, pady=8)
        self.tree = ttk.Treeview(frame, columns=("when", "action", "doc", "details"), show="headings")
        for col, text, w in (("when", "When", 140), ("action", "Action", 170), ("doc", "Document", 260),
                             ("details", "Details", 280)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor="w")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        row = ttk.Frame(body)
        row.pack(fill="x")
        ttk.Button(row, text="Close", command=self.destroy).pack(side="right")
        ttk.Button(row, text="Refresh", command=self.load).pack(side="right", padx=6)
        self.load()

    def load(self):
        self.tree.delete(*self.tree.get_children())
        for r in self.archive.get_audit_log(500):
            self.tree.insert("", "end", values=(
                r["timestamp"].replace("T", " "), ACTIONS.get(r["action"], r["action"]),
                r["doc_name"] or (f"#{r['document_id']}" if r["document_id"] else ""), r["details"]))
