"""services.py - all business rules.

The desktop UI (and later the web server) should only call the Archive class here.
Rule used throughout: public methods commit their own work; helpers that start
with an underscore never commit, so they can be combined into one transaction.
"""
import difflib
import json
import math
import re
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import db
import storage

DATA_TYPES = ("text", "longtext", "number", "id", "year", "date", "name", "yesno", "dropdown")
_UNSET = object()
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%d-%b-%Y", "%b %d, %Y", "%B %d, %Y")


# ---------------------------------------------------------------- errors
class ArchiveError(Exception):
    pass


class DuplicateError(ArchiveError):
    """A type, field or tag with that name already exists."""


class InUseError(ArchiveError):
    """The change would break values already saved on documents."""


class DuplicateFileError(ArchiveError):
    """A file with identical content is already in the archive."""

    def __init__(self, matches):
        self.matches = matches  # {file path: [{"doc_id", "name", "is_deleted"}]}
        super().__init__("This file is already in the archive.")


# ---------------------------------------------------------------- helpers
def norm(text):
    return re.sub(r"\s+", " ", str(text if text is not None else "")).strip()


def key(text):
    return norm(text).casefold()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError("use a valid date, e.g. 2026-10-15")


def validate_value(data_type, value, options=None):
    """Return the cleaned value, None if blank. Raises ValueError with a readable message."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
    if data_type in ("text", "id", "name"):
        return norm(value)
    if data_type == "longtext":
        return str(value).strip()
    if data_type == "number":
        try:
            f = float(str(value).replace(",", ""))
        except ValueError:
            raise ValueError("must be a number")
        if not math.isfinite(f):
            raise ValueError("must be a number")
        return int(f) if f.is_integer() else f
    if data_type == "year":
        s = str(value)
        if not re.fullmatch(r"\d{4}", s) or not 1900 <= int(s) <= 2100:
            raise ValueError("must be a 4-digit year")
        return int(s)
    if data_type == "date":
        return _parse_date(value)
    if data_type == "yesno":
        s = str(value).strip().casefold()
        if s in ("yes", "y", "true", "1"):
            return True
        if s in ("no", "n", "false", "0"):
            return False
        raise ValueError("must be Yes or No")
    if data_type == "dropdown":
        for opt in options or []:
            if key(opt) == key(value):
                return opt
        raise ValueError("must be one of: " + ", ".join(options or []) if options else "no options defined yet")
    raise ValueError(f"unknown data type '{data_type}'")


def format_value(data_type, value):
    if value is None:
        return ""
    if data_type == "yesno":
        return "Yes" if value else "No"
    return str(value)


def _clean_options(options):
    out, seen = [], set()
    for o in options or []:
        o = norm(o)
        if o and key(o) not in seen:
            seen.add(key(o))
            out.append(o)
    return out


def _rank(candidates, text, limit=8, cutoff=0.7):
    """Order candidates for autosuggest: starts-with, then contains, then close spellings."""
    candidates = list(candidates)
    t = key(text)
    if not t:
        return candidates[:limit]
    starts, contains = [], []
    for c in candidates:
        ck = key(c)
        if ck.startswith(t):
            starts.append(c)
        elif t in ck:
            contains.append(c)
    out = starts + contains
    if len(out) < limit and len(t) >= 3:
        rest = {key(c): c for c in candidates if c not in out}
        for k in difflib.get_close_matches(t, list(rest), n=limit, cutoff=cutoff):
            out.append(rest[k])
    return out[:limit]


def suggest_from_list(candidates, text, limit=8):
    """Autosuggest over any list of strings (used for dropdown choices)."""
    return _rank(candidates, text, limit)


def _like(token):
    return "%" + token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# ---------------------------------------------------------------- main class
class Archive:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else storage.default_data_dir()
        self.storage = storage.Storage(self.data_dir)
        self.conn = db.connect(self.data_dir / "archive.db")
        db.migrate(self.conn)
        self._hash_cache = {}                  # (path, size, mtime) -> hash, for the scanner inbox

    def close(self):
        self.conn.close()

    # ------------------------------------------------------------ settings / audit
    def get_setting(self, name, default=None):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (name,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, name, value):
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (name, str(value)))

    def _log(self, action, doc_id=None, details=""):
        self.conn.execute(
            "INSERT INTO audit_log(timestamp, action, document_id, details) VALUES(?,?,?,?)",
            (_now(), action, doc_id, details))

    def get_audit_log(self, limit=200):
        rows = self.conn.execute(
            "SELECT a.*, d.name AS doc_name FROM audit_log a "
            "LEFT JOIN documents d ON d.id = a.document_id ORDER BY a.id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ document types
    def list_types(self):
        rows = self.conn.execute(
            "SELECT t.id, t.name, "
            "(SELECT COUNT(*) FROM type_fields f WHERE f.type_id=t.id AND f.is_active=1) AS field_count, "
            "(SELECT COUNT(*) FROM documents d WHERE d.type_id=t.id AND d.is_deleted=0) AS doc_count "
            "FROM doc_types t WHERE t.is_active=1 ORDER BY t.name_key").fetchall()
        return [dict(r) for r in rows]

    def find_type(self, name):
        row = self.conn.execute("SELECT id FROM doc_types WHERE name_key=?", (key(name),)).fetchone()
        return row["id"] if row else None

    def get_type(self, type_id, include_hidden=False):
        row = self.conn.execute("SELECT * FROM doc_types WHERE id=?", (type_id,)).fetchone()
        if not row:
            return None
        return {"id": row["id"], "name": row["name"],
                "fields": self._fields(type_id, active_only=not include_hidden)}

    def suggest_types(self, text, limit=8):
        return _rank([t["name"] for t in self.list_types()], text, limit)

    def similar_types(self, name, limit=5):
        """For the 'Did you mean...?' prompt before creating a new type."""
        return _rank([t["name"] for t in self.list_types()], name, limit)

    def create_type(self, name, fields=None):
        with self.conn:
            return self._create_type(name, fields)

    def _create_type(self, name, fields=None):
        name = norm(name)
        if not name:
            raise ValueError("Type name is required")
        if self.find_type(name) is not None:
            raise DuplicateError(f"Type '{name}' already exists")
        cur = self.conn.execute(
            "INSERT INTO doc_types(name, name_key, created_at) VALUES(?,?,?)",
            (name, key(name), _now()))
        type_id = cur.lastrowid
        for i, spec in enumerate(fields or []):
            self._add_field(type_id, spec, i)
        self._log("type_create", None, name)
        return type_id

    # ------------------------------------------------------------ type fields
    def _field_dict(self, row):
        d = dict(row)
        d["options"] = json.loads(d["options"]) if d["options"] else []
        for k in ("is_key", "is_required", "is_active"):
            d[k] = bool(d[k])
        return d

    def _fields(self, type_id, active_only=True):
        if type_id is None:
            return []
        sql = "SELECT * FROM type_fields WHERE type_id=?"
        if active_only:
            sql += " AND is_active=1"
        sql += " ORDER BY sort_order, id"
        return [self._field_dict(r) for r in self.conn.execute(sql, (type_id,))]

    def get_field(self, field_id):
        row = self.conn.execute("SELECT * FROM type_fields WHERE id=?", (field_id,)).fetchone()
        return self._field_dict(row) if row else None

    def _add_field(self, type_id, spec, sort_order):
        label = norm(spec.get("label"))
        data_type = spec.get("data_type", "text")
        if not label:
            raise ValueError("Field label is required")
        if data_type not in DATA_TYPES:
            raise ValueError(f"Unknown data type '{data_type}'")
        options = _clean_options(spec.get("options")) if data_type == "dropdown" else None
        try:
            cur = self.conn.execute(
                "INSERT INTO type_fields(type_id, label, label_key, data_type, options, is_key, "
                "is_required, sort_order) VALUES(?,?,?,?,?,?,?,?)",
                (type_id, label, key(label), data_type,
                 json.dumps(options) if options is not None else None,
                 1 if spec.get("is_key") else 0, 1 if spec.get("is_required") else 0, sort_order))
        except Exception as e:
            if "UNIQUE" in str(e):
                raise DuplicateError(f"Field '{label}' already exists on this type")
            raise
        return cur.lastrowid

    def add_field(self, type_id, label, data_type="text", options=None, is_key=False, required=False):
        if self.get_type(type_id) is None:
            raise ArchiveError("Type not found")
        with self.conn:
            top = self.conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) FROM type_fields WHERE type_id=?",
                (type_id,)).fetchone()[0]
            field_id = self._add_field(
                type_id, {"label": label, "data_type": data_type, "options": options,
                          "is_key": is_key, "is_required": required}, top + 1)
            self._log("field_add", None, f"type {type_id}: {norm(label)}")
        return field_id

    def _field_values(self, field_id):
        """Every value currently saved for a field (including documents in the Recycle Bin)."""
        f = self.get_field(field_id)
        if not f:
            return []
        out = []
        for row in self.conn.execute("SELECT details FROM documents WHERE type_id=?", (f["type_id"],)):
            v = json.loads(row["details"]).get(str(field_id))
            if v is not None:
                out.append(v)
        return out

    def update_field(self, field_id, label=None, data_type=None, options=None,
                     is_key=None, required=None):
        f = self.get_field(field_id)
        if not f:
            raise ArchiveError("Field not found")
        used = self._field_values(field_id)
        with self.conn:
            effective_type = f["data_type"]
            if data_type is not None and data_type != f["data_type"]:
                if data_type not in DATA_TYPES:
                    raise ValueError(f"Unknown data type '{data_type}'")
                if used:
                    raise InUseError(
                        f"'{f['label']}' already has saved values, so its data type is locked.")
                effective_type = data_type
                self.conn.execute("UPDATE type_fields SET data_type=?, options=? WHERE id=?",
                                  (data_type, json.dumps([]) if data_type == "dropdown" else None, field_id))
            if label is not None:
                new = norm(label)
                if not new:
                    raise ValueError("Field label is required")
                try:
                    self.conn.execute("UPDATE type_fields SET label=?, label_key=? WHERE id=?",
                                      (new, key(new), field_id))
                except Exception as e:
                    if "UNIQUE" in str(e):
                        raise DuplicateError(f"Field '{new}' already exists on this type")
                    raise
            if options is not None and effective_type == "dropdown":
                opts = _clean_options(options)
                keep = {key(o) for o in opts}
                gone = sorted({str(v) for v in used if key(v) not in keep})
                if gone:
                    raise InUseError("These options are in use and cannot be removed: " + ", ".join(gone))
                self.conn.execute("UPDATE type_fields SET options=? WHERE id=?",
                                  (json.dumps(opts), field_id))
            if is_key is not None:
                self.conn.execute("UPDATE type_fields SET is_key=? WHERE id=?", (1 if is_key else 0, field_id))
            if required is not None:
                self.conn.execute("UPDATE type_fields SET is_required=? WHERE id=?", (1 if required else 0, field_id))
            self._log("field_update", None, f"field {field_id}")

    def hide_field(self, field_id):
        """Hide a field from forms. Saved values are kept."""
        with self.conn:
            self.conn.execute("UPDATE type_fields SET is_active=0 WHERE id=?", (field_id,))
            self._log("field_hide", None, f"field {field_id}")

    def add_field_option(self, field_id, option):
        """Add a choice to a dropdown field (e.g. a missing barangay). Returns the stored text."""
        f = self.get_field(field_id)
        if not f or f["data_type"] != "dropdown":
            raise ArchiveError("Not a dropdown field")
        option = norm(option)
        if not option:
            raise ValueError("Option cannot be empty")
        for existing in f["options"]:
            if key(existing) == key(option):
                return existing
        with self.conn:
            self.conn.execute("UPDATE type_fields SET options=? WHERE id=?",
                              (json.dumps(f["options"] + [option]), field_id))
            self._log("field_option_add", None, f"field {field_id}: {option}")
        return option

    def suggest_field_labels(self, text, limit=8):
        """Existing field names (with their data type) to reuse while defining a new type."""
        rows = self.conn.execute(
            "SELECT label, data_type, COUNT(*) AS c FROM type_fields "
            "GROUP BY label_key ORDER BY c DESC, label_key").fetchall()
        by_label = {r["label"]: {"label": r["label"], "data_type": r["data_type"]} for r in rows}
        return [by_label[l] for l in _rank(by_label.keys(), text, limit)]

    # ------------------------------------------------------------ tags
    def list_tags(self):
        rows = self.conn.execute(
            "SELECT t.id, t.name, COUNT(d.id) AS uses FROM tags t "
            "LEFT JOIN document_tags dt ON dt.tag_id=t.id "
            "LEFT JOIN documents d ON d.id=dt.document_id AND d.is_deleted=0 "
            "GROUP BY t.id ORDER BY uses DESC, t.name_key").fetchall()
        return [dict(r) for r in rows]

    def suggest_tags(self, text, limit=8, exclude=()):
        skip = {key(x) for x in exclude}
        names = [t["name"] for t in self.list_tags() if key(t["name"]) not in skip]
        return _rank(names, text, limit)

    def _get_or_create_tag(self, name):
        name = norm(name)
        row = self.conn.execute("SELECT id FROM tags WHERE name_key=?", (key(name),)).fetchone()
        if row:
            return row["id"]
        return self.conn.execute(
            "INSERT INTO tags(name, name_key, created_at) VALUES(?,?,?)",
            (name, key(name), _now())).lastrowid

    def _set_tags(self, doc_id, tags):
        seen, ids = set(), []
        for t in tags or []:
            t = norm(t)
            if t and key(t) not in seen:
                seen.add(key(t))
                ids.append(self._get_or_create_tag(t))
        self.conn.execute("DELETE FROM document_tags WHERE document_id=?", (doc_id,))
        for tag_id in ids:
            self.conn.execute("INSERT INTO document_tags(document_id, tag_id) VALUES(?,?)", (doc_id, tag_id))

    # ------------------------------------------------------------ details / search text
    def _normalize_details(self, type_id, details):
        """details may be keyed by field id or by field label. Returns {str(field_id): value}."""
        fields = self._fields(type_id)
        if details and type_id is None:
            raise ValueError("Pick a document type before filling in type details")
        every = self._fields(type_id, active_only=False)   # hidden fields keep their saved values
        by_id = {f["id"]: f for f in every}
        by_label = {key(f["label"]): f for f in every}
        out, errors = {}, []
        for k, v in (details or {}).items():
            f = by_id.get(int(k)) if str(k).isdigit() else None
            f = f or by_label.get(key(k))
            if f is None:
                errors.append(f"unknown field '{k}'")
                continue
            try:
                val = validate_value(f["data_type"], v, f["options"])
            except ValueError as e:
                errors.append(f"{f['label']}: {e}")
                continue
            if val is not None:
                out[str(f["id"])] = val
        for f in fields:
            if f["is_required"] and str(f["id"]) not in out:
                errors.append(f"{f['label']}: required")
        if errors:
            raise ValueError("; ".join(errors))
        return out

    def _refresh_search_text(self, doc_id):
        row = self.conn.execute(
            "SELECT d.name, d.notes, d.details, d.type_id, t.name AS type_name "
            "FROM documents d LEFT JOIN doc_types t ON t.id=d.type_id WHERE d.id=?", (doc_id,)).fetchone()
        parts = [row["name"], row["type_name"] or "", row["notes"]]
        fields = {str(f["id"]): f for f in self._fields(row["type_id"], active_only=False)}
        for fid, val in json.loads(row["details"]).items():
            if fid in fields:
                parts.append(format_value(fields[fid]["data_type"], val))
        parts += [r[0] for r in self.conn.execute(
            "SELECT t.name FROM document_tags dt JOIN tags t ON t.id=dt.tag_id WHERE dt.document_id=?", (doc_id,))]
        parts += [r[0] for r in self.conn.execute(
            "SELECT original_filename FROM document_files WHERE document_id=?", (doc_id,))]
        text = " ".join(p for p in parts if p).casefold()
        self.conn.execute("UPDATE documents SET search_text=? WHERE id=?", (text, doc_id))

    def find_key_duplicates(self, type_id, details, exclude_id=None):
        """Documents of the same type with identical values in the type's key fields
        (e.g. same Year + Version). Used for a warning, never blocks saving."""
        keys = [f for f in self._fields(type_id) if f["is_key"]]
        if not keys:
            return []
        clean = self._normalize_details(type_id, details)
        want = {str(f["id"]): clean.get(str(f["id"])) for f in keys}
        if any(v is None for v in want.values()):
            return []
        out = []
        for row in self.conn.execute(
                "SELECT id, name, details FROM documents WHERE type_id=? AND is_deleted=0", (type_id,)):
            if exclude_id is not None and row["id"] == exclude_id:
                continue
            d = json.loads(row["details"])
            if all(d.get(k) is not None and key(d.get(k)) == key(v) for k, v in want.items()):
                out.append({"id": row["id"], "name": row["name"]})
        return out

    # ------------------------------------------------------------ files
    def _hash_matches(self, file_hash):
        rows = self.conn.execute(
            "SELECT d.id, d.name, d.is_deleted FROM document_files f "
            "JOIN documents d ON d.id=f.document_id WHERE f.file_hash=?", (file_hash,)).fetchall()
        return [{"doc_id": r["id"], "name": r["name"], "is_deleted": bool(r["is_deleted"])} for r in rows]

    def check_duplicate_files(self, file_paths):
        """Call before saving. Returns {path: [matching documents]} (empty if all are new)."""
        found = {}
        for p in file_paths:
            matches = self._hash_matches(storage.sha256_file(p))
            if matches:
                found[str(p)] = matches
        return found

    def _prepare_files(self, file_paths, allow_duplicates):
        if isinstance(file_paths, (str, Path)):
            file_paths = [file_paths]
        paths = [Path(p) for p in file_paths]
        if not paths:
            raise ValueError("Select at least one file")
        infos, dups = [], {}
        for p in paths:
            if not p.is_file():
                raise FileNotFoundError(f"File not found: {p}")
            h = storage.sha256_file(p)
            infos.append((p, h, p.stat().st_size))
            matches = self._hash_matches(h)
            if matches:
                dups[str(p)] = matches
        if dups and not allow_duplicates:
            raise DuplicateFileError(dups)
        return infos

    def _store_files(self, doc_id, display_name, infos, copied, start_seq):
        for i, (path, h, size) in enumerate(infos):
            rel = self.storage.store_file(path, doc_id, display_name, seq=start_seq + i, expected_hash=h)
            copied.append(rel)
            self.conn.execute(
                "INSERT INTO document_files(document_id, file_path, original_filename, file_hash, "
                "size_bytes, sort_order) VALUES(?,?,?,?,?,?)",
                (doc_id, rel, path.name, h, size, start_seq + i))

    # ------------------------------------------------------------ documents
    def add_document(self, file_paths, name=None, type_id=None, doc_date=None, details=None,
                     tags=None, notes="", confidential=False, allow_duplicate_files=False):
        infos = self._prepare_files(file_paths, allow_duplicate_files)
        name = norm(name) or infos[0][0].stem
        if type_id is not None and self.get_type(type_id) is None:
            raise ValueError("Document type not found")
        try:
            date_val = validate_value("date", doc_date)
        except ValueError as e:
            raise ValueError(f"Document date: {e}")
        clean = self._normalize_details(type_id, details)
        ts = _now()
        copied = []
        try:
            with self.conn:
                doc_id = self.conn.execute(
                    "INSERT INTO documents(name, type_id, doc_date, details, notes, is_confidential, "
                    "date_added, last_edited) VALUES(?,?,?,?,?,?,?,?)",
                    (name, type_id, date_val, json.dumps(clean), str(notes or "").strip(),
                     1 if confidential else 0, ts, ts)).lastrowid
                self._store_files(doc_id, name, infos, copied, 0)
                self._set_tags(doc_id, tags)
                self._refresh_search_text(doc_id)
                self._log("add", doc_id, name)
        except Exception:
            for rel in copied:
                self.storage.delete_file(rel)
            raise
        return doc_id

    def add_files(self, doc_id, file_paths, allow_duplicate_files=False):
        """Attach more scanned files (e.g. extra pages) to an existing document."""
        row = self.conn.execute("SELECT name FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not row:
            raise ArchiveError("Document not found")
        infos = self._prepare_files(file_paths, allow_duplicate_files)
        start = self.conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM document_files WHERE document_id=?",
            (doc_id,)).fetchone()[0]
        copied = []
        try:
            with self.conn:
                self._store_files(doc_id, row["name"], infos, copied, start)
                self.conn.execute("UPDATE documents SET last_edited=? WHERE id=?", (_now(), doc_id))
                self._refresh_search_text(doc_id)
                self._log("add_files", doc_id, f"{len(infos)} file(s)")
        except Exception:
            for rel in copied:
                self.storage.delete_file(rel)
            raise

    def get_document(self, doc_id):
        row = self.conn.execute(
            "SELECT d.*, t.name AS type_name FROM documents d "
            "LEFT JOIN doc_types t ON t.id=d.type_id WHERE d.id=?", (doc_id,)).fetchone()
        if not row:
            return None
        doc = dict(row)
        doc.pop("search_text", None)
        for k in ("is_confidential", "is_deleted"):
            doc[k] = bool(doc[k])
        values = json.loads(doc["details"])
        doc["details"] = values
        doc["fields"] = [
            {"field_id": f["id"], "label": f["label"], "data_type": f["data_type"],
             "options": f["options"], "is_key": f["is_key"], "value": values.get(str(f["id"]))}
            for f in self._fields(doc["type_id"], active_only=False)
            if f["is_active"] or values.get(str(f["id"])) is not None]
        doc["tags"] = [r[0] for r in self.conn.execute(
            "SELECT t.name FROM document_tags dt JOIN tags t ON t.id=dt.tag_id "
            "WHERE dt.document_id=? ORDER BY t.name_key", (doc_id,))]
        doc["files"] = [
            {"id": r["id"], "path": r["file_path"], "abs_path": str(self.storage.abs_path(r["file_path"])),
             "original_filename": r["original_filename"], "size_bytes": r["size_bytes"],
             "hash": r["file_hash"], "exists": self.storage.exists(r["file_path"])}
            for r in self.conn.execute(
                "SELECT * FROM document_files WHERE document_id=? ORDER BY sort_order", (doc_id,))]
        return doc

    def update_document(self, doc_id, name=None, type_id=_UNSET, doc_date=_UNSET, details=None,
                        tags=None, notes=None, confidential=None):
        """Only the arguments you pass are changed. Changing the type clears type details
        unless new details are passed. Passing details replaces all type details."""
        row = self.conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not row:
            raise ArchiveError("Document not found")
        new_type = row["type_id"] if type_id is _UNSET else type_id
        if new_type is not None and self.get_type(new_type) is None:
            raise ValueError("Document type not found")
        if type_id is not _UNSET and new_type != row["type_id"] and details is None:
            details = {}
        new_details = row["details"] if details is None else json.dumps(self._normalize_details(new_type, details))
        new_name = row["name"]
        if name is not None:
            new_name = norm(name)
            if not new_name:
                raise ValueError("Name cannot be empty")
        new_date = row["doc_date"]
        if doc_date is not _UNSET:
            try:
                new_date = validate_value("date", doc_date)
            except ValueError as e:
                raise ValueError(f"Document date: {e}")
        with self.conn:
            self.conn.execute(
                "UPDATE documents SET name=?, type_id=?, doc_date=?, details=?, notes=?, "
                "is_confidential=?, last_edited=? WHERE id=?",
                (new_name, new_type, new_date, new_details,
                 row["notes"] if notes is None else str(notes).strip(),
                 row["is_confidential"] if confidential is None else (1 if confidential else 0),
                 _now(), doc_id))
            if tags is not None:
                self._set_tags(doc_id, tags)
            self._refresh_search_text(doc_id)
            self._log("edit", doc_id, new_name)

    def delete_document(self, doc_id):
        """Move to the Recycle Bin (files are kept)."""
        with self.conn:
            cur = self.conn.execute(
                "UPDATE documents SET is_deleted=1, deleted_at=? WHERE id=? AND is_deleted=0", (_now(), doc_id))
            if cur.rowcount == 0:
                raise ArchiveError("Document not found or already deleted")
            self._log("delete", doc_id)

    def restore_document(self, doc_id):
        with self.conn:
            cur = self.conn.execute(
                "UPDATE documents SET is_deleted=0, deleted_at=NULL WHERE id=? AND is_deleted=1", (doc_id,))
            if cur.rowcount == 0:
                raise ArchiveError("Document is not in the Recycle Bin")
            self._log("restore", doc_id)

    def list_deleted(self):
        rows = self.conn.execute(
            "SELECT d.id, d.name, t.name AS type_name, d.deleted_at FROM documents d "
            "LEFT JOIN doc_types t ON t.id=d.type_id WHERE d.is_deleted=1 ORDER BY d.deleted_at DESC").fetchall()
        return [dict(r) for r in rows]

    def purge_document(self, doc_id):
        """Permanently delete a document that is already in the Recycle Bin, including its files."""
        row = self.conn.execute("SELECT name, is_deleted FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not row:
            raise ArchiveError("Document not found")
        if not row["is_deleted"]:
            raise ArchiveError("Move the document to the Recycle Bin before deleting it permanently")
        paths = [r[0] for r in self.conn.execute(
            "SELECT file_path FROM document_files WHERE document_id=?", (doc_id,))]
        with self.conn:
            self.conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
            self._log("purge", doc_id, row["name"])
        for rel in paths:
            self.storage.delete_file(rel)

    # ------------------------------------------------------------ search
    def search(self, query="", type_id=None, tags=None, date_from=None, date_to=None,
               include_confidential=True, sort="added_desc", limit=200, offset=0):
        """Returns {"total": n, "results": [...]}. Every word in the query must match somewhere
        (name, type, notes, type details, tags, original file names)."""
        where, params = ["d.is_deleted = 0"], []
        for token in key(query).split():
            where.append("d.search_text LIKE ? ESCAPE '\\'")
            params.append(_like(token))
        if type_id is not None:
            where.append("d.type_id = ?")
            params.append(type_id)
        for tg in tags or []:
            where.append("EXISTS (SELECT 1 FROM document_tags dt JOIN tags t ON t.id=dt.tag_id "
                         "WHERE dt.document_id=d.id AND t.name_key=?)")
            params.append(key(tg))
        if date_from:
            where.append("d.doc_date >= ?")
            params.append(validate_value("date", date_from))
        if date_to:
            where.append("d.doc_date <= ?")
            params.append(validate_value("date", date_to))
        if not include_confidential:
            where.append("d.is_confidential = 0")
        where_sql = " AND ".join(where)
        order = {
            "added_desc": "d.date_added DESC, d.id DESC",
            "added_asc": "d.date_added ASC, d.id ASC",
            "name": "d.name COLLATE NOCASE, d.id",
            "date_desc": "d.doc_date IS NULL, d.doc_date DESC, d.id DESC",
        }.get(sort, "d.date_added DESC, d.id DESC")
        limit = max(1, min(int(limit), 500))

        total = self.conn.execute(f"SELECT COUNT(*) FROM documents d WHERE {where_sql}", params).fetchone()[0]
        rows = self.conn.execute(
            f"SELECT d.id, d.name, d.type_id, t.name AS type_name, d.doc_date, d.details, "
            f"d.is_confidential, d.date_added, "
            f"(SELECT COUNT(*) FROM document_files f WHERE f.document_id=d.id) AS file_count "
            f"FROM documents d LEFT JOIN doc_types t ON t.id=d.type_id "
            f"WHERE {where_sql} ORDER BY {order} LIMIT ? OFFSET ?", params + [limit, int(offset)]).fetchall()

        tag_map = defaultdict(list)
        ids = [r["id"] for r in rows]
        if ids:
            for r in self.conn.execute(
                    "SELECT dt.document_id, t.name FROM document_tags dt JOIN tags t ON t.id=dt.tag_id "
                    f"WHERE dt.document_id IN ({','.join('?' * len(ids))}) ORDER BY t.name_key", ids):
                tag_map[r["document_id"]].append(r["name"])

        key_fields = {}
        results = []
        for r in rows:
            if r["type_id"] not in key_fields:
                key_fields[r["type_id"]] = [f for f in self._fields(r["type_id"]) if f["is_key"]]
            values = json.loads(r["details"])
            ref = " | ".join(
                format_value(f["data_type"], values.get(str(f["id"])))
                for f in key_fields[r["type_id"]] if values.get(str(f["id"])) is not None)
            results.append({
                "id": r["id"], "name": r["name"], "type_id": r["type_id"], "type_name": r["type_name"],
                "doc_date": r["doc_date"], "ref": ref, "tags": tag_map[r["id"]],
                "file_count": r["file_count"], "is_confidential": bool(r["is_confidential"]),
                "date_added": r["date_added"]})
        return {"total": total, "results": results}

    # ------------------------------------------------------------ tag management
    def find_tag(self, name):
        row = self.conn.execute("SELECT id FROM tags WHERE name_key=?", (key(name),)).fetchone()
        return row["id"] if row else None

    def _docs_with_tag(self, tag_id):
        return {r[0] for r in self.conn.execute(
            "SELECT document_id FROM document_tags WHERE tag_id=?", (tag_id,))}

    def rename_tag(self, tag_id, new_name):
        new = norm(new_name)
        if not new:
            raise ValueError("Tag name cannot be empty")
        if not self.conn.execute("SELECT 1 FROM tags WHERE id=?", (tag_id,)).fetchone():
            raise ArchiveError("Tag not found")
        clash = self.conn.execute("SELECT id FROM tags WHERE name_key=? AND id<>?", (key(new), tag_id)).fetchone()
        if clash:
            raise DuplicateError(f"A tag named \u201c{new}\u201d already exists. Merge the tags instead.")
        with self.conn:
            old = self.conn.execute("SELECT name FROM tags WHERE id=?", (tag_id,)).fetchone()["name"]
            self.conn.execute("UPDATE tags SET name=?, name_key=? WHERE id=?", (new, key(new), tag_id))
            for d in self._docs_with_tag(tag_id):
                self._refresh_search_text(d)
            self._log("tag_rename", None, f"{old} -> {new}")

    def merge_tags(self, source_ids, target_id):
        """Move every document from the source tags onto the target tag, then remove the sources.
        Returns the number of documents affected."""
        sources = [i for i in dict.fromkeys(source_ids) if i != target_id]
        target = self.conn.execute("SELECT name FROM tags WHERE id=?", (target_id,)).fetchone()
        if not target:
            raise ArchiveError("Target tag not found")
        docs = set()
        with self.conn:
            names = []
            for sid in sources:
                row = self.conn.execute("SELECT name FROM tags WHERE id=?", (sid,)).fetchone()
                if not row:
                    continue
                names.append(row["name"])
                docs |= self._docs_with_tag(sid)
                self.conn.execute(
                    "INSERT OR IGNORE INTO document_tags(document_id, tag_id) "
                    "SELECT document_id, ? FROM document_tags WHERE tag_id=?", (target_id, sid))
                self.conn.execute("DELETE FROM tags WHERE id=?", (sid,))
            for d in docs:
                self._refresh_search_text(d)
            self._log("tags_merge", None, f"{', '.join(names)} -> {target['name']}")
        return len(docs)

    def delete_tag(self, tag_id):
        """Remove a tag from every document and delete it. Returns the number of documents affected."""
        row = self.conn.execute("SELECT name FROM tags WHERE id=?", (tag_id,)).fetchone()
        if not row:
            raise ArchiveError("Tag not found")
        with self.conn:
            docs = self._docs_with_tag(tag_id)
            self.conn.execute("DELETE FROM tags WHERE id=?", (tag_id,))
            for d in docs:
                self._refresh_search_text(d)
            self._log("tag_delete", None, row["name"])
        return len(docs)

    def delete_unused_tags(self):
        with self.conn:
            cur = self.conn.execute("DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM document_tags)")
            if cur.rowcount:
                self._log("tags_cleanup", None, f"{cur.rowcount} unused tag(s) deleted")
        return cur.rowcount

    def similar_tag_map(self, cutoff=0.82):
        """{tag_id: {"id", "name", "ratio"}} - the closest other tag, when it is similar enough
        to be a likely duplicate (typo, plural, different spacing)."""
        tags = [(t["id"], t["name"]) for t in self.list_tags()]
        flat = {tid: re.sub(r"[\W_]+", "", key(name)) for tid, name in tags}
        best = {}
        for i, (a_id, a_name) in enumerate(tags):
            for b_id, b_name in tags[i + 1:]:
                a, b = flat[a_id], flat[b_id]
                if len(a) < 3 or len(b) < 3:
                    continue
                if a == b:
                    ratio = 1.0
                else:
                    sm = difflib.SequenceMatcher(None, a, b)
                    if sm.real_quick_ratio() < cutoff or sm.quick_ratio() < cutoff:
                        continue
                    ratio = sm.ratio()
                    if ratio < cutoff:
                        continue
                for x, other_id, other_name in ((a_id, b_id, b_name), (b_id, a_id, a_name)):
                    if x not in best or ratio > best[x]["ratio"]:
                        best[x] = {"id": other_id, "name": other_name, "ratio": ratio}
        return best

    # ------------------------------------------------------------ type management
    def rename_type(self, type_id, new_name):
        new = norm(new_name)
        if not new:
            raise ValueError("Type name cannot be empty")
        row = self.conn.execute("SELECT name FROM doc_types WHERE id=?", (type_id,)).fetchone()
        if not row:
            raise ArchiveError("Type not found")
        clash = self.conn.execute("SELECT id FROM doc_types WHERE name_key=? AND id<>?", (key(new), type_id)).fetchone()
        if clash:
            raise DuplicateError(f"A type named \u201c{new}\u201d already exists. Merge the types instead.")
        with self.conn:
            self.conn.execute("UPDATE doc_types SET name=?, name_key=? WHERE id=?", (new, key(new), type_id))
            for r in self.conn.execute("SELECT id FROM documents WHERE type_id=?", (type_id,)).fetchall():
                self._refresh_search_text(r["id"])
            self._log("type_rename", None, f"{row['name']} -> {new}")

    def delete_type(self, type_id):
        """Only possible when no document (including the Recycle Bin) uses the type."""
        row = self.conn.execute("SELECT name FROM doc_types WHERE id=?", (type_id,)).fetchone()
        if not row:
            raise ArchiveError("Type not found")
        n = self.conn.execute("SELECT COUNT(*) FROM documents WHERE type_id=?", (type_id,)).fetchone()[0]
        if n:
            raise InUseError(f"{n} document(s) use \u201c{row['name']}\u201d. Merge it into another type instead.")
        with self.conn:
            self.conn.execute("DELETE FROM doc_types WHERE id=?", (type_id,))
            self._log("type_delete", None, row["name"])

    def merge_types(self, source_id, target_id):
        """Move all documents of the source type into the target type, then delete the source type.
        Fields are matched by name. Source fields the target lacks are added to the target, so
        nothing is lost. Raises InUseError if a matching field's values cannot be converted."""
        if source_id == target_id:
            raise ValueError("Choose two different types")
        src = self.get_type(source_id, include_hidden=True)
        tgt = self.get_type(target_id, include_hidden=True)
        if not src or not tgt:
            raise ArchiveError("Type not found")
        tfields = {f["label_key"]: f for f in tgt["fields"]}
        moved = 0
        added = 0
        with self.conn:
            top = self.conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM type_fields WHERE type_id=?",
                                    (target_id,)).fetchone()[0]
            mapping = {}                                   # source field id -> target field dict
            for sf in src["fields"]:
                tf = tfields.get(sf["label_key"])
                if tf is None:
                    top += 1
                    new_id = self._add_field(target_id, {
                        "label": sf["label"], "data_type": sf["data_type"], "options": sf["options"],
                        "is_key": sf["is_key"]}, top)
                    if not sf["is_active"]:
                        self.conn.execute("UPDATE type_fields SET is_active=0 WHERE id=?", (new_id,))
                    tf = self.get_field(new_id)
                    tfields[sf["label_key"]] = tf
                    added += 1
                elif sf["data_type"] == "dropdown" and tf["data_type"] == "dropdown":
                    extra = [o for o in sf["options"] if key(o) not in {key(x) for x in tf["options"]}]
                    if extra:
                        tf["options"] = tf["options"] + extra
                        self.conn.execute("UPDATE type_fields SET options=? WHERE id=?",
                                          (json.dumps(tf["options"]), tf["id"]))
                mapping[sf["id"]] = (sf, tf)
            for row in self.conn.execute("SELECT id, details FROM documents WHERE type_id=?",
                                         (source_id,)).fetchall():
                new_details = {}
                for k, v in json.loads(row["details"]).items():
                    pair = mapping.get(int(k))
                    if not pair:
                        continue
                    sf, tf = pair
                    if sf["data_type"] != tf["data_type"] or tf["data_type"] == "dropdown":
                        try:
                            v = validate_value(tf["data_type"], v, tf["options"])
                        except ValueError:
                            raise InUseError(
                                f"Cannot merge: the value \u201c{v}\u201d of \u201c{sf['label']}\u201d does not fit "
                                f"the target field ({tf['data_type']}).")
                    new_details[str(tf["id"])] = v
                self.conn.execute("UPDATE documents SET type_id=?, details=? WHERE id=?",
                                  (target_id, json.dumps(new_details), row["id"]))
                moved += 1
            self.conn.execute("DELETE FROM doc_types WHERE id=?", (source_id,))
            for r in self.conn.execute("SELECT id FROM documents WHERE type_id=?", (target_id,)).fetchall():
                self._refresh_search_text(r["id"])
            self._log("types_merge", None, f"{src['name']} -> {tgt['name']} ({moved} documents)")
        return {"documents_moved": moved, "fields_added": added}

    def field_use_count(self, field_id):
        return len(self._field_values(field_id))

    def show_field(self, field_id):
        with self.conn:
            self.conn.execute("UPDATE type_fields SET is_active=1 WHERE id=?", (field_id,))
            self._log("field_show", None, f"field {field_id}")

    def move_field(self, field_id, step):
        """Move a field up (step=-1) or down (step=+1) in the form."""
        f = self.get_field(field_id)
        if not f:
            raise ArchiveError("Field not found")
        ids = [x["id"] for x in self._fields(f["type_id"], active_only=False)]
        i = ids.index(field_id)
        j = i + step
        if not 0 <= j < len(ids):
            return
        ids[i], ids[j] = ids[j], ids[i]
        with self.conn:
            for n, fid in enumerate(ids):
                self.conn.execute("UPDATE type_fields SET sort_order=? WHERE id=?", (n, fid))

    # ------------------------------------------------------------ backup bookkeeping
    def backup_status(self):
        last = self.get_setting("last_backup")
        days = None
        if last:
            try:
                days = (datetime.now() - datetime.fromisoformat(last)).days
            except ValueError:
                last = None
        try:
            reminder = int(self.get_setting("backup_reminder_days", "7") or 7)
        except ValueError:
            reminder = 7
        docs = self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        return {"last_backup": last, "days_ago": days, "backup_dir": self.get_setting("backup_dir"),
                "reminder_days": reminder, "documents": docs}

    def backup_due(self):
        st = self.backup_status()
        if st["documents"] == 0:
            return False
        return st["days_ago"] is None or st["days_ago"] >= st["reminder_days"]

    def record_backup(self, info):
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings(key, value) VALUES('last_backup', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (_now(),))
            self._log("backup", None, f"{info.get('files_copied', 0)} new file(s) to {info.get('destination', '')}")

    # ------------------------------------------------------------ archive check
    def check_integrity(self, verify_hashes=False, progress=None, cancel=None):
        """Look for problems: database errors, files the database lists but are missing on disk,
        files on disk the database does not know about, and (optionally) changed file contents."""
        report = {"database_ok": True, "database_message": "ok", "missing_files": [], "orphan_files": [],
                  "changed_files": [], "files_checked": 0}
        rows = [r[0] for r in self.conn.execute("PRAGMA integrity_check")]
        report["database_ok"] = rows == ["ok"]
        report["database_message"] = "; ".join(rows)
        listed = self.conn.execute(
            "SELECT f.file_path, f.file_hash, f.document_id, d.name FROM document_files f "
            "JOIN documents d ON d.id=f.document_id").fetchall()
        known = set()
        for n, r in enumerate(listed, start=1):
            if cancel and cancel():
                break
            known.add(r["file_path"])
            report["files_checked"] += 1
            if not self.storage.exists(r["file_path"]):
                report["missing_files"].append(
                    {"doc_id": r["document_id"], "name": r["name"], "path": r["file_path"]})
            elif verify_hashes and storage.sha256_file(self.storage.abs_path(r["file_path"])) != r["file_hash"]:
                report["changed_files"].append(
                    {"doc_id": r["document_id"], "name": r["name"], "path": r["file_path"]})
            if progress:
                progress(n, len(listed), r["file_path"])
        report["orphan_files"] = [p for p in self.storage.all_files() if p not in known]
        return report

    def remove_orphan_files(self, rels):
        """Delete files that no document refers to. Re-checks each one first. Returns how many were removed."""
        removed = 0
        for rel in rels:
            if self.conn.execute("SELECT 1 FROM document_files WHERE file_path=?", (rel,)).fetchone():
                continue
            if self.storage.exists(rel):
                self.storage.delete_file(rel)
                removed += 1
        if removed:
            with self.conn:
                self._log("orphans_removed", None, f"{removed} file(s)")
        return removed

    # ------------------------------------------------------------ bulk import
    IMPORT_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp")
    REVIEW_TAG = "Needs details"

    def scan_folder(self, folder, recursive=True, extensions=None):
        """List the scan files in a folder (sorted). Hidden files, Office temp files (~$...)
        and files inside the archive's own data folder are left out."""
        folder = Path(folder)
        if not folder.is_dir():
            raise ArchiveError(f"Folder not found: {folder}")
        exts = tuple(e.lower() for e in (extensions or self.IMPORT_EXTENSIONS))
        data_root = self.data_dir.resolve()
        found = []
        for p in (folder.rglob("*") if recursive else folder.glob("*")):
            if not p.is_file() or p.suffix.lower() not in exts:
                continue
            if p.name.startswith(("~$", ".")):
                continue
            rp = p.resolve()
            if data_root == rp or data_root in rp.parents:
                continue
            found.append(p)
        return sorted(found, key=lambda x: str(x).casefold())

    def import_files(self, file_paths, type_id=None, tags=None, doc_date=None, confidential=False,
                     review_tag=REVIEW_TAG, skip_duplicates=True, progress=None, cancel=None):
        """File many scans at once: one document per file, named after the file.
        Each document is saved on its own, so a stop or a crash keeps what was already done.
        Returns {"imported": [{doc_id, name, path}], "skipped": [{path, matches}],
                 "failed": [{path, error}], "cancelled": bool}.
        review_tag (default "Needs details") is added to every imported document so the
        office can find them later and fill in the details. Pass None to skip it."""
        if type_id is not None:
            t = self.get_type(type_id)
            if t is None:
                raise ArchiveError("Document type not found")
            needed = [f["label"] for f in t["fields"] if f["is_required"]]
            if needed:
                raise ArchiveError(
                    "This type has required details (" + ", ".join(needed) + ") that a bulk import "
                    "cannot fill in. Choose a type without required details, or no type.")
        all_tags = list(tags or [])
        if review_tag and key(review_tag) not in {key(x) for x in all_tags}:
            all_tags.append(review_tag)
        paths = [Path(p) for p in file_paths]
        report = {"imported": [], "skipped": [], "failed": [], "cancelled": False}
        for n, p in enumerate(paths, start=1):
            if cancel and cancel():
                report["cancelled"] = True
                break
            try:
                doc_id = self.add_document(p, type_id=type_id, doc_date=doc_date, tags=all_tags,
                                           confidential=confidential,
                                           allow_duplicate_files=not skip_duplicates)
                report["imported"].append({"doc_id": doc_id, "name": p.stem, "path": str(p)})
            except DuplicateFileError as e:
                first = next(iter(e.matches.values()))
                report["skipped"].append({"path": str(p), "matches": first})
            except (ValueError, ArchiveError, OSError) as e:
                report["failed"].append({"path": str(p), "error": str(e)})
            if progress:
                progress(n, len(paths), p.name)
        with self.conn:
            self._log("bulk_import", None,
                      f"{len(report['imported'])} imported, {len(report['skipped'])} duplicate(s) skipped, "
                      f"{len(report['failed'])} failed" + (" (stopped early)" if report["cancelled"] else ""))
        return report

    # ------------------------------------------------------------ scanner inbox (watch folder)
    WATCH_SETTLE_SECONDS = 3

    def get_watch_folder(self):
        value = (self.get_setting("watch_folder") or "").strip()
        return Path(value) if value else None

    def set_watch_folder(self, folder):
        """Choose the folder your scanner saves to. Empty text turns the inbox off."""
        folder = str(folder or "").strip()
        if folder:
            p = Path(folder)
            if not p.is_dir():
                raise ArchiveError(f"Folder not found: {p}")
            rp, root = p.resolve(), self.data_dir.resolve()
            if rp == root or root in rp.parents:
                raise ArchiveError("Choose a folder outside the archive's own data folder.")
        self.set_setting("watch_folder", folder)
        with self.conn:
            self._log("watch_folder", None, folder or "(off)")

    def _cached_hash(self, path, st):
        k = (str(path), st.st_size, st.st_mtime_ns)
        h = self._hash_cache.get(k)
        if h is None:
            h = storage.sha256_file(path)
            if len(self._hash_cache) > 5000:
                self._hash_cache.clear()
            self._hash_cache[k] = h
        return h

    def _ignored_hashes(self):
        try:
            data = json.loads(self.get_setting("ignored_hashes") or "{}")
        except ValueError:
            data = {}
        return data if isinstance(data, dict) else {}

    def ignored_count(self):
        return len(self._ignored_hashes())

    def pending_files(self):
        """Scans waiting in the watch folder: not yet filed (by content) and not dismissed.
        Files modified in the last few seconds are still being written by the scanner and are
        only counted in "busy". Returns {"folder", "files": [{path, name, size, modified}], "busy", "error"}."""
        folder = self.get_watch_folder()
        out = {"folder": str(folder) if folder else None, "files": [], "busy": 0, "error": None}
        if folder is None:
            return out
        try:
            paths = self.scan_folder(folder, recursive=False)
        except ArchiveError as e:
            out["error"] = str(e)
            return out
        ignored = self._ignored_hashes()
        now = time.time()
        for p in paths:
            try:
                st = p.stat()
                if now - st.st_mtime < self.WATCH_SETTLE_SECONDS:
                    out["busy"] += 1
                    continue
                h = self._cached_hash(p, st)
            except OSError:                                   # locked by the scanner
                out["busy"] += 1
                continue
            if h in ignored or self._hash_matches(h):
                continue
            out["files"].append({"path": str(p), "name": p.name, "size": st.st_size, "modified": st.st_mtime})
        out["files"].sort(key=lambda f: (f["modified"], f["name"].casefold()))
        return out

    def ignore_files(self, paths):
        """Dismiss scans from the inbox (the files stay in the folder). Returns how many were dismissed."""
        ignored = self._ignored_hashes()
        n = 0
        for p in paths:
            p = Path(p)
            h = self._cached_hash(p, p.stat())
            if h not in ignored:
                ignored[h] = p.name
                n += 1
        self.set_setting("ignored_hashes", json.dumps(ignored))
        if n:
            with self.conn:
                self._log("inbox_dismiss", None, f"{n} file(s)")
        return n

    def clear_ignored(self):
        """Bring dismissed scans back into the inbox. Returns how many were restored."""
        n = self.ignored_count()
        self.set_setting("ignored_hashes", "{}")
        if n:
            with self.conn:
                self._log("inbox_restore", None, f"{n} file(s)")
        return n

    # ------------------------------------------------------------ starter types (profile.json)
    def seed_from_profile(self, profile_path):
        """Create the document types in a profile file. Existing types are never changed,
        only missing fields are added. Safe to run more than once."""
        data = json.loads(Path(profile_path).read_text(encoding="utf-8"))
        summary = {"types_created": 0, "types_existing": 0, "fields_added": 0}
        with self.conn:
            for t in data.get("document_types", []):
                type_id = self.find_type(t["name"])
                if type_id is None:
                    self._create_type(t["name"], t.get("fields", []))
                    summary["types_created"] += 1
                    summary["fields_added"] += len(t.get("fields", []))
                    continue
                summary["types_existing"] += 1
                have = {f["label_key"] for f in self._fields(type_id, active_only=False)}
                top = self.conn.execute(
                    "SELECT COALESCE(MAX(sort_order), -1) FROM type_fields WHERE type_id=?",
                    (type_id,)).fetchone()[0]
                for spec in t.get("fields", []):
                    if key(spec["label"]) not in have:
                        top += 1
                        self._add_field(type_id, spec, top)
                        summary["fields_added"] += 1
        return summary

    def ensure_seeded(self, profile_path=None):
        """Load profile.json once, the first time the app runs. Returns the summary or None."""
        if self.get_setting("profile_seeded"):
            return None
        path = Path(profile_path) if profile_path else storage.app_dir() / "profile.json"
        if not path.exists():
            return None
        summary = self.seed_from_profile(path)
        self.set_setting("profile_seeded", "1")
        return summary
