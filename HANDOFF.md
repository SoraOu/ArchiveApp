# HANDOFF - Office Document Archive

Read this first, then `graphify-out/GRAPH_REPORT.md` (code map), then work. Last updated 2026-11-06 (after Phase 4b).

## 1. What this is
A desktop app (Python + Tkinter + SQLite) that works as a **finding aid** for an office's scanned documents:
scan -> file it (type, details, tags) -> search and open later. Built for the Municipal Nutrition Office (MNO)
in Mogpog, Marinduque, Philippines. The maintainer is the office's Information Management Officer
(BS Computer Engineering), working on a Windows PC. The mayor's office asked for it, but the task is to build it
for the MNO only, for now. Each office would run its **own separate copy**.

**Out of scope (decided):** workflows/approvals, integration with other department systems, calculations on
document data, retention/disposal tracking, a shared multi-office system.

## 2. Status
| Phase | Content | State |
|---|---|---|
| 0 | Setup .bat (folders, venv, packages, git, PyInstaller test) | Done, ran clean on the user's PC |
| 1 | db / storage / services / seeded types / tests | Done. User ran `test_phase1.py` on Windows: 18/18 pass |
| 2 | Main window, Add/Edit dialog, Recycle Bin | Done. **Confirmed working by the user on Windows** |
| 3 | Type Manager, Tag Manager, Settings, backup/restore, archive check, activity log | Done. **Confirmed working by the user on Windows** |
| 4a | Bulk import (File > Import folder of scans...) | Done. `test_phase4.py` 6/6 pass on Windows; screen **confirmed working by the user** |
| 4b | Scanner inbox / watch folder (toolbar button + File > Scanner inbox...) | Done. `test_phase4b.py` 8/8; screen **confirmed working by the user** |
| 4c | OCR (Tesseract, background thread, searchable text) | Not started. Tesseract is not installed yet |
| 4d | Thumbnails, export to Excel | Not started (export is low priority) |
| 5 | Read-only browser view via local server | Not started |
| 6 | Roles/login, confidential filtering, final .exe, auto-start | Not started |

Test suites (all pass): `test_phase1.py` (18), `test_phase3.py` (13), `test_phase4.py` (6), `test_phase4b.py` (8),
`dev/gui_smoke_phase2.py`, `dev/gui_smoke_phase3.py`.
The user reported that everything built so far works on their Windows PC. Caveat: the Tkinter screens added in 4a/4b
(`ui/import_dialog.py`, `ui/pending_window.py`) were never run by the assistant (that session had no Tkinter); only their
service logic was tested. They were verified by the user on Windows. When tkinter is missing in the sandbox, say so plainly.

## 3. Environment (user's machine)
- Windows, Python 3.14.5, Git 2.54. Project: `C:\Users\Admin\Desktop\JO things\Project\archive_system\ArchiveApp`.
- Virtual env at `ArchiveApp\.venv`; run with `.venv\Scripts\python`.
- **Device Guard** is active: always use `python -m pip ...` and `python -m PyInstaller ...`, never `pip` / `pyinstaller`
  directly. A test PyInstaller .exe built and ran fine.
- Libraries (requirements.txt): Pillow, PyMuPDF, openpyxl, pyinstaller, flask, waitress, pytesseract, watchdog.
  Tesseract OCR is **not installed** yet (only needed for OCR).
- Scanner folder: chosen inside the app (Scanner inbox > Choose folder...), stored in the `watch_folder` setting; its path is not known to the assistant.
- Data stays on that PC only (no cloud sync). Default data folder: `ArchiveApp\data` (override with `data_dir` in config.ini).
- Do not put `data\`, `backups\`, `samples\`, `config.ini` or scans into Git or into any handoff. They are confidential.

## 4. Decisions and why (the part the code graph cannot show)
1. **Hybrid document types.** Every document has *common fields* (name, type, document date, tags, notes, confidential
   flag) plus *type fields* defined per type. Starter types are seeded from `profile.json`; new types and their fields are
   created while filing ("This is a new type, create it?"). Why: the office has 20+ document types and pre-encoding all of
   them was too much work, but a fully dynamic system risks mess, so seed the known ones and keep a manager for cleanup.
2. **Type fields are stored as JSON on the document, keyed by field id** (`documents.details`), so renaming a field never
   breaks data. Fields are never deleted, only hidden. A field's data type locks once it holds values.
3. **Key fields** (`type_fields.is_key`) define duplicate detection (e.g. Year+Version). A match only *warns*; it never blocks saving.
4. **Free-form tags** with autosuggest (prefix, contains, then fuzzy). Case-insensitive uniqueness via a `name_key` column (casefold).
   Tag Manager handles rename/merge/delete and flags likely duplicates.
5. **Files are copied into the archive** (`data\archive\YYYY\MM\<id>_<name>.<ext>`), never linked. DB stores paths relative with forward slashes.
6. **Soft delete + Recycle Bin**, permanent delete only from the bin. Audit log for every change.
7. **SQLite, one writer.** Only the main PC touches the DB file; WAL mode. Never place it on a network share.
8. **Separate installation per office.** Type setups can later be shared by export/import with a preview that only *adds*, never overwrites.
9. **Nothing office-specific in code.** Starter types live in `profile.json`; office name etc. in settings.
10. **Backups are incremental folder copies** (DB snapshots via SQLite backup API + mirrored `archive\`), restored with `restore.py` into a new empty folder.
11. **Scope kept small on purpose** (see section 1). Resist adding workflow features.
12. **Bulk import** (`Archive.scan_folder`, `Archive.import_files`): one document per file, named after the file stem; each
    document is committed on its own (a stop or crash keeps earlier work); files already in the archive (by content hash) are
    skipped, not filed twice; every imported document gets the tag "Needs details" (`Archive.REVIEW_TAG`, can be switched off) so
    the office can filter for them and fill in details later; types that have required fields are refused (bulk import cannot fill
    them); hidden files, `~$` temp files and anything inside the data folder are ignored.
13. **Scanner inbox** (`get/set_watch_folder`, `pending_files`, `ignore_files`, `clear_ignored`): **polling, not `watchdog`**
    (window refreshes every 4 s, toolbar count every 10 s; no background thread, so no SQLite threading issues). A scan is
    "pending" when it sits directly in the watch folder (sub-folders are not watched), its content hash is not in the archive
    (Recycle Bin counts as in the archive) and it was not dismissed. Files modified in the last 3 s are treated as still being
    written. Hashes are cached by (path, size, mtime) in `Archive._hash_cache`. Dismissed scans are stored as JSON in the
    `ignored_hashes` setting (**no schema change**). The app never moves, renames or deletes the scanner's originals; filing copies them.

## 5. Architecture and conventions
```
app.py            start-up, DPI, logging, seeds profile.json once
db.py             schema + migrations (PRAGMA user_version). Add a new entry to MIGRATIONS; never edit old ones
storage.py        hashing, safe copy (tmp then os.replace), path guard, data-dir lookup
services.py       ALL rules. class Archive. The UI and the future web server call only this
                  (includes bulk import and the scanner inbox, see decisions 12-13)
backup.py/restore.py   backup + restore (pure functions, no UI)
ui/               Tkinter screens (main_window, add_dialog, type_dialogs, type_manager, tag_manager,
                  settings_window, maintenance, activity_log, recycle_bin, preview, widgets, common,
                  import_dialog, pending_window)
```
Conventions that matter:
- **UI never touches SQL.** Add logic to `services.py` and test it in `test_phase*.py` first.
- In `Archive`, **public methods commit their own work; helpers starting with `_` never commit**, so they can be combined
  in one `with self.conn:` transaction. Never nest a public method inside another's transaction.
- `Archive` holds **one SQLite connection** (`check_same_thread=False`). For the Phase 5 server use one `Archive`/connection
  per thread, and keep the server **read-only**.
- Search is `documents.search_text` (casefolded) + LIKE. `_refresh_search_text(doc_id)` must run whenever a name, type name,
  tag, detail value or file name changes. FTS5 could replace it later behind `search()`.
- Modal dialogs: after a nested dialog or messagebox closes, call `regrab()`/`_regrab()` or the parent loses its grab.
- **Tkinter name collisions bit us three times.** Never define a method or attribute on a widget/Toplevel named like a Tk
  internal (`_options`, `_name`, `_w`, `master`, `children`...). Scan after UI edits:
  ```python
  import tkinter as tk, re, glob
  reserved = set(dir(tk.Toplevel)) | set(dir(tk.Frame))
  for f in glob.glob("ui/*.py"):
      for m in re.finditer(r"^\s+def (\w+)\(self", open(f).read(), re.M):
          if m.group(1) in reserved and m.group(1) != "__init__": print(f, m.group(1))
  ```
- Autosuggest popups are `Listbox.place()`d on the toplevel (not separate windows) so they work inside modal dialogs.
- Windows-hostile characters in names are sanitized in `storage.sanitize_filename`.

## 6. Data model (schema version 1)
`doc_types(id, name, name_key, is_active)` - `type_fields(id, type_id, label, label_key, data_type, options JSON, is_key,
is_required, is_active, sort_order)` - `documents(id, name, type_id, doc_date, details JSON, notes, is_confidential,
search_text, date_added, last_edited, is_deleted, deleted_at)` - `document_files(id, document_id, file_path, original_filename,
file_hash, size_bytes, sort_order)` - `tags(id, name, name_key)` - `document_tags` - `audit_log` - `settings(key, value)`.
Data types: text, longtext, number, id, year, date, name, yesno, dropdown.

## 7. Starter types (`profile.json`, 6 of ~20)
Operation Timbang Plus (Year, Version v1/v2), BNS Database (Year, Quarter), BNC Directory (Year, Barangay dropdown),
Activity Design (Year, Fund Source, Activity Name), Resolution (Ref No., Source), Executive Order (Ref No., Source).
**Verify:** the 37 Mogpog barangays in the Barangay dropdown were typed from memory. Remaining ~14 types still to be collected
from the user (format: `Type: detail (data type), ...`). Unanswered question: what "Source" holds for Resolutions/Executive Orders.

## 8. Next steps (suggested order)
1. **4c OCR**: first have the user install Tesseract (Windows build, with the English data, plus Filipino/Tagalog if wanted) and
   point the app at it. Run OCR in a background thread, store the text in a new column or table (needs a migration, see db.py),
   feed it into `search_text`/search. Decide: OCR on import/filing automatically vs. a "scan now" button.
2. 4d thumbnails in the results list; export a result list to Excel (low priority).
3. **Phase 5** read-only browser view: Flask + waitress in a background thread inside the same app, bound to `0.0.0.0`, reusing `services.py`,
   write routes refused. Use one `Archive`/connection per server thread. Office network setup: static IP via DHCP reservation,
   firewall rule for one port on the Private profile, sleep disabled. Never expose to the internet.
4. **Phase 6**: view-only roles/login if wanted, hide confidential documents from browser users, final build with
   `python -m PyInstaller` (prefer `--onedir`; single-file exes unpack on every start and are more often flagged), `profile.json`
   and `config.ini` beside the exe, auto-start, update the README.
5. Pending housekeeping: Type setup export/import with preview; Data Privacy Act (RA 10173) review for documents with personal data; BitLocker; offsite backup.
6. **Data still needed from the user** (see section 7): the remaining ~14 document types, a check of the 37 barangays, and what "Source" holds.
7. Housekeeping seen in the graph report: two `.tar.gz` delivery files sit in the project folder (safe to delete after extracting; add
   `*.tar.gz` to `.gitignore`), and the Phase 4 work should be committed to Git (the graph still shows the old commit).
8. Optional refactor before Phase 5: `services.py` / `Archive` keeps growing (84 edges, low cohesion 0.10). Consider moving bulk import
   and the scanner inbox into their own module (e.g. `inbox.py` with helper functions called from `Archive`) while keeping
   `Archive` as the only entry point for the UI and the web server. Only do this with tests green before and after.
9. Possible small follow-ups seen in 4a/4b: watch sub-folders in the inbox; optional "move filed scans to a Filed sub-folder"; a count of
   "Needs details" documents somewhere visible.

## 9. Working with this user
Direct and concise; minimal scaffolding; clean, ready-to-use files. Test before sending and say plainly what is untested.
Give runnable commands with `.venv\Scripts\python`. Do not claim something works on Windows unless the user confirmed it.
Ask at most one question at a time.
Delivery that worked: send changes as a `.tar.gz` that keeps the folder layout; the user puts it in `ArchiveApp`, runs
`tar -xzf <name>.tar.gz` there, then `.venv\Scripts\python test_phaseN.py`, then `.venv\Scripts\python app.py`.
The user confirms back with a screenshot or "works". Tell them which files a tarball overwrites.

## 10. The code graph (graphify)
`graphify-out/` was rebuilt after Phase 4b with `graphify update .` (code only, no LLM): 616 nodes, 1608 edges, 21 clusters,
34 files. It includes `ImportDialog`, `PendingWindow`, `test_phase4.py`, `test_phase4b.py` and the new `Archive` methods.
Biggest hubs now: `Archive` (84 edges), `MainWindow` (54), `ArchiveError` (48), `DocumentDialog` (41), `PendingWindow` (22).
It reports `Built from commit 1f9a61ad` (same as before), i.e. the Phase 4 work is probably not committed to Git yet. Rerun
`graphify update .` after the next phase.
- Start with `graphify-out/GRAPH_REPORT.md` (core abstractions: `Archive`, `MainWindow`, `DocumentDialog`).
- Query: `graphify query "how is a backup recorded" --graph graphify-out/graph.json`, `graphify explain "Archive"`, `graphify path "A" "B"`.
- It maps **structure only**. For decisions and intent use this file. After code changes run `graphify update .`;
  for the docs (this file, README) run `/graphify . --update` in your assistant so they join the graph.
- Install: `uv tool install graphifyy` (or `pipx install graphifyy`), then `graphify install`.
