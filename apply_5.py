r"""apply_5.py - applies the Phase 5 edits to services.py, app.py and ui\main_window.py.
Run from the ArchiveApp folder:  .venv\Scripts\python apply_5.py
Needs webserver.py, test_phase5.py (same folder) and ui\web_dialog.py already in place.
Makes .bak5 backups first. Changes nothing if any edit does not match."""
import shutil
from pathlib import Path

SV = [
('    def __init__(self, data_dir=None):\n',
 '    def __init__(self, data_dir=None, read_only=False):\n'),
('        db.migrate(self.conn)\n',
 '''        db.migrate(self.conn)
        if read_only:                          # the browser view: SQLite itself refuses every write
            self.conn.execute("PRAGMA query_only = ON")
'''),
('    # ------------------------------------------------------------ scanner inbox (watch folder)\n', '''    # ------------------------------------------------------------ public (browser) views
    # Everything the browser view shows goes through these methods. They never return confidential
    # or deleted documents, and none of them can be told to. They only read the database.
    def _is_public(self, doc_id):
        return self.conn.execute(
            "SELECT 1 FROM documents WHERE id=? AND is_deleted=0 AND is_confidential=0",
            (doc_id,)).fetchone() is not None

    def public_search(self, query="", type_id=None, tags=None, sort="added_desc", limit=50, offset=0):
        res = self.search(query=query, type_id=type_id, tags=tags, include_confidential=False,
                          sort=sort, limit=limit, offset=offset)
        for r in res["results"]:
            r.pop("is_confidential", None)
        return res

    def public_types(self):
        """Types that have at least one public document, with the number of public documents."""
        rows = self.conn.execute(
            "SELECT t.id, t.name, COUNT(d.id) AS doc_count FROM doc_types t "
            "JOIN documents d ON d.type_id=t.id AND d.is_deleted=0 AND d.is_confidential=0 "
            "WHERE t.is_active=1 GROUP BY t.id ORDER BY t.name_key").fetchall()
        return [dict(r) for r in rows]

    def public_tags(self):
        """Tags used by at least one public document, counting public documents only."""
        rows = self.conn.execute(
            "SELECT t.name, COUNT(d.id) AS count FROM tags t "
            "JOIN document_tags dt ON dt.tag_id=t.id "
            "JOIN documents d ON d.id=dt.document_id AND d.is_deleted=0 AND d.is_confidential=0 "
            "GROUP BY t.id ORDER BY t.name_key").fetchall()
        return [dict(r) for r in rows]

    def public_document(self, doc_id):
        """What the browser may show about a document, or None. No server paths are included."""
        if not self._is_public(doc_id):
            return None
        d = self.get_document(doc_id)
        return {
            "id": d["id"], "name": d["name"], "type_name": d["type_name"], "doc_date": d["doc_date"],
            "notes": d["notes"], "date_added": d["date_added"], "tags": d["tags"],
            "fields": [{"label": f["label"], "value": format_value(f["data_type"], f["value"])}
                       for f in d["fields"] if f["value"] not in (None, "")],
            "files": [{"id": f["id"], "name": f["original_filename"], "size_bytes": f["size_bytes"],
                       "exists": f["exists"]} for f in d["files"]]}

    def public_file(self, doc_id, file_id):
        """{"path", "name"} of one stored file of a public document, or None."""
        if not self._is_public(doc_id):
            return None
        row = self.conn.execute(
            "SELECT file_path, original_filename FROM document_files WHERE id=? AND document_id=?",
            (file_id, doc_id)).fetchone()
        if not row or not self.storage.exists(row["file_path"]):
            return None
        return {"path": self.storage.abs_path(row["file_path"]), "name": row["original_filename"]}

    def public_thumbnail(self, doc_id, size=THUMB_SIZE):
        if not self._is_public(doc_id):
            return None
        return self.thumbnail_for_document(doc_id, size)

    # ------------------------------------------------------------ browser view settings
    WEB_DEFAULT_PORT = 8080

    def web_settings(self):
        try:
            port = int(self.get_setting("web_port", self.WEB_DEFAULT_PORT))
        except (TypeError, ValueError):
            port = self.WEB_DEFAULT_PORT
        return {"enabled": self.get_setting("web_enabled", "0") == "1", "port": port}

    def set_web_settings(self, enabled, port):
        try:
            port = int(str(port).strip())
        except ValueError:
            raise ArchiveError("The port must be a number between 1024 and 65535.")
        if not 1024 <= port <= 65535:
            raise ArchiveError("The port must be a number between 1024 and 65535.")
        self.set_setting("web_enabled", "1" if enabled else "0")
        self.set_setting("web_port", port)
        with self.conn:
            self._log("web_settings", None, f"browser view {'on' if enabled else 'off'}, port {port}")

    # ------------------------------------------------------------ scanner inbox (watch folder)
'''),
]
APP = [
('    MainWindow(root, archive)\n', '''    MainWindow(root, archive)
    try:                                       # read-only browser view, only if switched on in Tools > Browser view
        import webserver
        running, message = webserver.autostart(data_dir, archive)
        log.info(message)
        if not running and archive.web_settings()["enabled"]:
            messagebox.showwarning("Browser view", message)
    except Exception:
        log.exception("browser view failed to start")
'''),
]
MW = [
('from ui.type_manager import TypeManager\n', 'from ui.type_manager import TypeManager\nfrom ui.web_dialog import WebDialog\n'),
('        tools.add_command(label="Activity Log...", command=self.open_activity_log)\n',
 '        tools.add_command(label="Activity Log...", command=self.open_activity_log)\n'
 '        tools.add_command(label="Browser view...", command=self.open_web_dialog)\n'),
('    def open_settings(self):\n', '''    def open_web_dialog(self):
        WebDialog(self.root, self.archive).run()

    def open_settings(self):
'''),
]


def patch(path, edits, marker):
    raw = Path(path).read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    if marker in text:
        return None, f"{path}: already patched, skipped"
    for i, (a, b) in enumerate(edits, start=1):
        if text.count(a) != 1:
            raise SystemExit(f"STOPPED. {path}: edit {i} matched {text.count(a)} times (needs 1). "
                             "Nothing was changed.")
        text = text.replace(a, b)
    return (text.replace("\n", "\r\n") if crlf else text), f"{path}: {len(edits)} edits applied"


if __name__ == "__main__":
    jobs = [("services.py", SV, "def public_search"), ("app.py", APP, "import webserver"),
            (str(Path("ui") / "main_window.py"), MW, "WebDialog")]
    for need in ["webserver.py", "test_phase5.py", str(Path("ui") / "web_dialog.py")] + [j[0] for j in jobs]:
        if not Path(need).is_file():
            raise SystemExit(f"STOPPED. {need} not found. Run this from the ArchiveApp folder "
                             "(webserver.py and test_phase5.py go there, web_dialog.py goes in ui\\).")
    results = [(p,) + patch(p, e, m) for p, e, m in jobs]      # check everything before writing anything
    for p, new, msg in results:
        if new is not None:
            shutil.copy2(p, p + ".bak5")
            Path(p).write_bytes(new.encode("utf-8"))
        print(msg)
    print(r"Done. Next: .venv\Scripts\python test_phase5.py")
