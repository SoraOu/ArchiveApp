r"""apply_4d.py - applies the Phase 4d edits to services.py and ui\\main_window.py.
Run from the ArchiveApp folder:  .venv\\Scripts\\python apply_4d.py
Makes services.py.bak and ui\\main_window.py.bak first. Changes nothing if any edit does not match."""
import shutil
import sys
from pathlib import Path

SV = [
("import difflib\nimport json\n", "import csv\nimport difflib\nimport json\n"),
("import math\nimport re\nimport time\n", "import math\nimport os\nimport re\nimport time\n"),
("import storage\n\nDATA_TYPES", "import storage\nimport thumbs\n\nDATA_TYPES"),
("def _like(token):", '''def _csv_safe(value):
    """Stop Excel from running a cell that starts with = + - @ as a formula (CSV only)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def _like(token):'''),
("    # ------------------------------------------------------------ scanner inbox (watch folder)\n", '''    # ------------------------------------------------------------ thumbnails
    THUMB_SIZE = 96

    def thumbnail_for_document(self, doc_id, size=THUMB_SIZE):
        """Path of a small PNG of the document's first file, or None when there is no picture.
        Made on first request and cached in data\\\\thumbs, named by the file's content hash, so it
        never goes stale. The cache is not part of backups and is safe to delete (it is rebuilt).
        A file that cannot be read leaves a .none marker so it is not retried every time.
        Reads the database only; never commits."""
        row = self.conn.execute(
            "SELECT file_path, file_hash FROM document_files WHERE document_id=? "
            "ORDER BY sort_order, id LIMIT 1", (doc_id,)).fetchone()
        if not row or Path(row["file_path"]).suffix.lower() not in thumbs.THUMB_EXTS:
            return None
        size = int(size)
        dest = self.data_dir / "thumbs" / row["file_hash"][:2] / f"{row['file_hash']}_{size}.png"
        if dest.is_file():
            return dest
        marker = dest.with_suffix(".none")
        if marker.is_file() or not self.storage.exists(row["file_path"]):
            return None
        if thumbs.make_thumbnail(self.storage.abs_path(row["file_path"]), dest, size):
            return dest
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()
        except OSError:
            pass
        return None

    # ------------------------------------------------------------ export
    EXPORT_COLUMNS = ("Name", "Type", "Reference", "Document date", "Tags", "Confidential",
                      "Date added", "Files")

    def export_rows(self, query="", type_id=None, tags=None, date_from=None, date_to=None,
                    include_confidential=True, sort="added_desc", page_size=500):
        """Every document that matches the same filters as search() (not just the first page).
        Returns (headers, rows). Reads only."""
        rows, offset = [], 0
        while True:
            res = self.search(query=query, type_id=type_id, tags=tags, date_from=date_from,
                              date_to=date_to, include_confidential=include_confidential,
                              sort=sort, limit=page_size, offset=offset)
            for r in res["results"]:
                rows.append([r["name"], r["type_name"] or "", r["ref"], r["doc_date"] or "",
                             ", ".join(r["tags"]), "Yes" if r["is_confidential"] else "",
                             r["date_added"].replace("T", " "), r["file_count"]])
            offset += len(res["results"])
            if not res["results"] or offset >= res["total"]:
                break
        return list(self.EXPORT_COLUMNS), rows

    def export_file(self, path, **filters):
        """Write the matching documents to a .csv (UTF-8, opens in Excel) or .xlsx file.
        Takes the same filters as export_rows(). Returns the number of documents written."""
        path = Path(path)
        ext = path.suffix.lower()
        if ext not in (".csv", ".xlsx"):
            raise ArchiveError("Choose a file name ending in .csv or .xlsx")
        headers, rows = self.export_rows(**filters)
        tmp = path.with_name(path.name + ".tmp")
        try:
            if ext == ".csv":
                with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for r in rows:
                        writer.writerow([_csv_safe(c) for c in r])
            else:
                from openpyxl import Workbook
                from openpyxl.styles import Font
                wb = Workbook()
                ws = wb.active
                ws.title = "Documents"
                for ci, h in enumerate(headers, start=1):
                    ws.cell(1, ci, h).font = Font(bold=True)
                for ri, r in enumerate(rows, start=2):
                    for ci, v in enumerate(r, start=1):
                        cell = ws.cell(ri, ci, v)
                        if isinstance(v, str) and v.startswith("="):
                            cell.data_type = "s"                       # keep it text, never a formula
                for ci, h in enumerate(headers, start=1):
                    widest = max([len(str(h))] + [len(str(r[ci - 1])) for r in rows])
                    ws.column_dimensions[ws.cell(1, ci).column_letter].width = min(max(widest + 2, 10), 60)
                ws.freeze_panes = "A2"
                wb.save(tmp)
            os.replace(tmp, path)
        except OSError as e:
            raise ArchiveError(f"Could not write {path.name}: {e}")
        finally:
            tmp.unlink(missing_ok=True)
        with self.conn:
            self._log("export", None, f"{len(rows)} document(s) to {path.name}"
                      + ("" if filters.get("include_confidential", True) else " (confidential left out)"))
        return len(rows)

    # ------------------------------------------------------------ scanner inbox (watch folder)
'''),
]
MW = [
("import subprocess\nimport sys\n", "import subprocess\nimport sys\nimport time\n"),
("        self._pending_win = None\n\n        root.title(", '''        self._pending_win = None
        self._thumb_imgs = {}                  # doc id -> PhotoImage (must stay referenced)
        self._thumb_todo = []
        self._thumb_job = None
        self.show_thumbs = tk.BooleanVar(master=root, value=archive.get_setting("show_thumbnails", "1") == "1")

        root.title('''),
('        ttk.Style(root).configure("Treeview", rowheight=int(24 * scale))\n', '''        ttk.Style(root).configure("Treeview", rowheight=int(24 * scale))
        self._row_h = int(24 * scale)
        self._thumb_px = max(32, int(44 * scale))
'''),
('        file_menu.add_command(label="Import folder of scans...", command=self.import_folder)\n', '''        file_menu.add_command(label="Import folder of scans...", command=self.import_folder)
        file_menu.add_command(label="Export results...", command=self.export_results)
'''),
('        view.add_command(label="Clear filters", command=self.clear_filters)\n', '''        view.add_command(label="Clear filters", command=self.clear_filters)
        view.add_separator()
        view.add_checkbutton(label="Show thumbnails", variable=self.show_thumbs, command=self.toggle_thumbnails)
'''),
('        self.tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="browse")\n',
 '        self.tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="browse",\n                                 style="Results.Treeview")\n'),
('        self.tree.bind("<Delete>", lambda e: self.delete_document())\n', '''        self.tree.bind("<Delete>", lambda e: self.delete_document())
        self._apply_thumb_mode()
'''),
('''            self.tree.insert("", "end", iid=str(r["id"]), values=(
                r["name"], r["type_name"] or "", r["ref"], r["doc_date"] or "",
                ", ".join(r["tags"]), "Yes" if r["is_confidential"] else ""))
        shown, total = len(res["results"]), res["total"]
''', '''            self.tree.insert("", "end", iid=str(r["id"]), image=self._thumb_imgs.get(r["id"], ""), values=(
                r["name"], r["type_name"] or "", r["ref"], r["doc_date"] or "",
                ", ".join(r["tags"]), "Yes" if r["is_confidential"] else ""))
        self._queue_thumbs([r["id"] for r in res["results"]])
        shown, total = len(res["results"]), res["total"]
'''),
("    def _refresh_tags(self):\n", '''    # ------------------------------------------------------------ thumbnails
    def _apply_thumb_mode(self):
        on = self.show_thumbs.get()
        ttk.Style(self.root).configure("Results.Treeview", rowheight=self._thumb_px + 8 if on else self._row_h)
        self.tree.configure(show="tree headings" if on else "headings")
        self.tree.heading("#0", text="")
        self.tree.column("#0", width=self._thumb_px + 12, minwidth=self._thumb_px + 12,
                         stretch=False, anchor="center")

    def toggle_thumbnails(self):
        self.archive.set_setting("show_thumbnails", "1" if self.show_thumbs.get() else "0")
        self._apply_thumb_mode()
        self.refresh()

    def _queue_thumbs(self, ids):
        """Fill in thumbnails a few at a time so the list appears at once and stays responsive."""
        self._thumb_todo = [i for i in ids if i not in self._thumb_imgs] if self.show_thumbs.get() else []
        if self._thumb_todo and self._thumb_job is None:
            self._thumb_job = self.root.after(20, self._thumb_tick)

    def _thumb_tick(self):
        self._thumb_job = None
        start = time.monotonic()
        while self._thumb_todo and time.monotonic() - start < 0.05:
            doc_id = self._thumb_todo.pop(0)
            if not self.tree.exists(str(doc_id)):
                continue
            try:
                path = self.archive.thumbnail_for_document(doc_id, self._thumb_px)
                if path is None:
                    continue
                img = tk.PhotoImage(file=str(path))
            except Exception:
                log.exception("thumbnail failed")
                continue
            self._thumb_imgs[doc_id] = img
            self.tree.item(str(doc_id), image=img)
        if self._thumb_todo:
            self._thumb_job = self.root.after(15, self._thumb_tick)

    def export_results(self):
        """Save the documents matching the current search and filters to .xlsx or .csv."""
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Export results", defaultextension=".xlsx", initialfile="documents",
            filetypes=[("Excel workbook", "*.xlsx"), ("CSV (opens in Excel)", "*.csv")])
        if not path:
            return
        try:
            n = self.archive.export_file(
                path, query=self.search_var.get(), type_id=self._type_ids.get(self.type_var.get()),
                tags=sorted(self.sel_tags), sort=SORTS.get(self.sort_var.get(), "added_desc"))
        except Exception as e:
            log.exception("export failed")
            messagebox.showerror("Export failed", str(e), parent=self.root)
            return
        self.status.set(f"Exported {n} document(s) to {Path(path).name}")

    def _refresh_tags(self):
'''),
]


def load(path):
    raw = Path(path).read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def patch(path, edits, marker):
    text, crlf = load(path)
    if marker in text:
        return None, f"{path}: already patched, skipped"
    for i, (a, b) in enumerate(edits, start=1):
        if text.count(a) != 1:
            raise SystemExit(f"STOPPED. {path}: edit {i} matched {text.count(a)} times (needs 1). Nothing was changed.")
        text = text.replace(a, b)
    return (text.replace("\n", "\r\n") if crlf else text), f"{path}: {len(edits)} edits applied"


if __name__ == "__main__":
    jobs = [("services.py", SV, "def thumbnail_for_document"),
            (str(Path("ui") / "main_window.py"), MW, "def export_results")]
    for p, _, _ in jobs:
        if not Path(p).is_file():
            raise SystemExit(f"STOPPED. {p} not found. Run this from the ArchiveApp folder.")
    results = [(p,) + patch(p, e, m) for p, e, m in jobs]      # check everything before writing anything
    for p, new, msg in results:
        if new is not None:
            shutil.copy2(p, p + ".bak")
            Path(p).write_bytes(new.encode("utf-8"))
        print(msg)
    print("Done. Next: .venv\\Scripts\\python test_phase4d.py")
