"""ui/tag_manager.py - rename, merge and delete tags; find likely duplicates."""
import tkinter as tk
from tkinter import messagebox, ttk

from services import ArchiveError, DuplicateError
from ui.common import ModalWindow, ask_choice, ask_text


class TagManager(ModalWindow):
    def __init__(self, parent, archive, on_change=None):
        super().__init__(parent, "Tag Manager", "780x580", (680, 440))
        self.archive, self.on_change = archive, on_change
        self.changed = False
        self._sort = ("tag", False)
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)

        top = ttk.Frame(body)
        top.pack(fill="x")
        ttk.Label(top, text="Filter").pack(side="left")
        self.filter_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.filter_var, width=28).pack(side="left", padx=6)
        self.filter_var.trace_add("write", lambda *a: self._load())
        self.dup_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Only possible duplicates", variable=self.dup_var,
                        command=self._load).pack(side="left", padx=10)
        self.count_lbl = ttk.Label(top, text="")
        self.count_lbl.pack(side="right")

        frame = ttk.Frame(body)
        frame.pack(fill="both", expand=True, pady=8)
        self.tree = ttk.Treeview(frame, columns=("tag", "uses", "similar"), show="headings", selectmode="extended")
        for col, text, w, anchor in (("tag", "Tag", 280, "w"), ("uses", "Documents", 90, "e"),
                                     ("similar", "Looks like", 260, "w")):
            self.tree.heading(col, text=text, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=w, anchor=anchor)
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<Double-1>", lambda e: self.rename())

        row = ttk.Frame(body)
        row.pack(fill="x")
        for text, cmd in (("Rename", self.rename), ("Merge...", self.merge), ("Delete", self.delete),
                          ("Delete unused tags", self.delete_unused)):
            ttk.Button(row, text=text, command=cmd).pack(side="left", padx=(0, 4))
        ttk.Button(row, text="Close", command=self.destroy).pack(side="right")
        ttk.Label(body, foreground="#666", justify="left", wraplength=700, text=(
            "Tip: select two or more tags (Ctrl+click) and press Merge to combine them. "
            "\u201cLooks like\u201d points at the tag with the most similar spelling.")).pack(anchor="w", pady=(8, 0))
        self.bind("<Destroy>", self._on_destroy)
        self._load()

    def _on_destroy(self, ev):
        if ev.widget is self and self.changed and self.on_change:
            self.on_change()

    def _sort_by(self, col):
        self._sort = (col, not self._sort[1]) if self._sort[0] == col else (col, False)
        self._load()

    def _load(self):
        keep = set(self.tree.selection())
        needle = self.filter_var.get().strip().casefold()
        sim = self.archive.similar_tag_map()
        tags = self.archive.list_tags()
        rows = []
        for t in tags:
            if needle and needle not in t["name"].casefold():
                continue
            if self.dup_var.get() and t["id"] not in sim:
                continue
            rows.append(t)
        col, desc = self._sort
        if col == "uses":
            rows.sort(key=lambda t: (t["uses"], t["name"].casefold()), reverse=desc)
        elif col == "similar":
            rows.sort(key=lambda t: sim.get(t["id"], {}).get("name", "\uffff").casefold(), reverse=desc)
        else:
            rows.sort(key=lambda t: t["name"].casefold(), reverse=desc)
        self.tree.delete(*self.tree.get_children())
        for t in rows:
            s = sim.get(t["id"])
            self.tree.insert("", "end", iid=str(t["id"]), values=(t["name"], t["uses"], s["name"] if s else ""))
        for iid in keep:
            if self.tree.exists(iid):
                self.tree.selection_add(iid)
        self.count_lbl.configure(text=f"{len(rows)} of {len(tags)} tags")

    def _selected(self):
        return [int(i) for i in self.tree.selection()]

    def _tag_name(self, tag_id):
        return self.tree.set(str(tag_id), "tag")

    def _done(self):
        self.changed = True
        self._load()

    def _error(self, title, e):
        messagebox.showerror(title, str(e), parent=self)
        self.regrab()

    def rename(self):
        ids = self._selected()
        if len(ids) != 1:
            return
        old = self._tag_name(ids[0])
        new = ask_text(self, "Rename tag", f"New name for \u201c{old}\u201d:", old)
        self.regrab()
        if not new or new == old:
            return
        try:
            self.archive.rename_tag(ids[0], new)
        except DuplicateError:
            if messagebox.askyesno("Tag exists", f"A tag named \u201c{new}\u201d already exists.\n"
                                   f"Merge \u201c{old}\u201d into it?", parent=self):
                self.archive.merge_tags([ids[0]], self.archive.find_tag(new))
            self.regrab()
        except (ValueError, ArchiveError) as e:
            return self._error("Cannot rename", e)
        self._done()

    def merge(self):
        ids = self._selected()
        if not ids:
            return
        all_tags = {t["id"]: t for t in self.archive.list_tags()}
        if len(ids) == 1:
            others = [t["name"] for i, t in all_tags.items() if i != ids[0]]
            if not others:
                return
            sim = self.archive.similar_tag_map().get(ids[0])
            target_name = ask_choice(self, "Merge tag", f"Merge \u201c{self._tag_name(ids[0])}\u201d into which tag?",
                                     sorted(others, key=str.casefold), default=sim["name"] if sim else None, button="Merge")
            self.regrab()
            if not target_name:
                return
            sources, target = ids, self.archive.find_tag(target_name)
        else:
            names = [all_tags[i]["name"] for i in ids]
            best = max(ids, key=lambda i: all_tags[i]["uses"])
            keep_name = ask_choice(self, "Merge tags", "Keep which spelling? The other selected tags are merged into it.",
                                   names, default=all_tags[best]["name"], button="Merge")
            self.regrab()
            if not keep_name:
                return
            target = self.archive.find_tag(keep_name)
            sources = [i for i in ids if i != target]
        try:
            n = self.archive.merge_tags(sources, target)
        except (ValueError, ArchiveError) as e:
            return self._error("Cannot merge", e)
        messagebox.showinfo("Merged", f"Done. {n} document(s) now use \u201c{all_tags[target]['name']}\u201d.", parent=self)
        self.regrab()
        self._done()

    def delete(self):
        ids = self._selected()
        if not ids:
            return
        total = sum(int(self.tree.set(str(i), "uses")) for i in ids)
        if not messagebox.askyesno("Delete tags", f"Delete {len(ids)} tag(s)? They will be removed from {total} document(s). "
                                   "The documents themselves are not affected.", parent=self):
            self.regrab()
            return
        self.regrab()
        for i in ids:
            try:
                self.archive.delete_tag(i)
            except ArchiveError as e:
                return self._error("Cannot delete", e)
        self._done()

    def delete_unused(self):
        if not messagebox.askyesno("Delete unused tags", "Delete every tag that no document uses?", parent=self):
            self.regrab()
            return
        self.regrab()
        n = self.archive.delete_unused_tags()
        messagebox.showinfo("Done", f"{n} unused tag(s) deleted.", parent=self)
        self.regrab()
        self._done()
