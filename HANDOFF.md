# HANDOFF - Office Document Archive

Read this first, then `graphify-out/GRAPH_REPORT.md` (code map), then work. Last updated: 2026-11-10. This file is kept current by `tools\handoff_tool.py` (see section 11): the task board in section 8 drives the chat bundles, and every milestone must be recorded here.

## 1. What this is
A desktop app (Python + Tkinter + SQLite) that works as a **finding aid** for an office's scanned documents:
scan -> file it (type, details, tags) -> search and open later. Built for the Municipal Nutrition Office (MNO)
in Mogpog, Marinduque, Philippines. The maintainer is the office's Information Management Officer
(BS Computer Engineering), working on a Windows PC. The mayor's office asked for it, but the task is to build it
for the MNO only, for now. Each office would run its **own separate copy**.

**Out of scope (decided):** workflows/approvals, integration with other department systems, calculations on
document data, retention/disposal tracking, a shared multi-office system.

## 2. Status
Generated from the task board (section 8). Do not edit by hand; run `python tools\handoff_tool.py --sync`.
<!-- STATUS:START -->
| Id | Task | Status |
|---|---|---|
| s0 | Setup: folders, venv, packages, git, PyInstaller test | Done |
| p1 | Phase 1: database, storage, services, seeded types, tests | Done |
| p2 | Phase 2: main window, Add/Edit dialog, Recycle Bin | Done |
| p3 | Phase 3: managers, settings, backup/restore, archive check, activity log | Done |
| h1 | Handoff package: graphify graph, HANDOFF.md, helper tools | Done |
| w1 | Verify Phases 2 and 3 on Windows and fix what breaks | Done |
| 4a1 | Phase 4a: bulk import, logic and tests | Done |
| 4a2 | Phase 4a: bulk import window | Done |
| 4b | Phase 4b: watch folder for the scanner | Next |
| 4c | Phase 4c: OCR text search | To do |
| 4d | Phase 4d: thumbnails and export | To do |
| 5 | Phase 5: read-only browser view | To do |
| 6 | Phase 6: roles, confidential filtering, final build | To do |
| x1 | Type setup export/import with preview | To do |
| x2 | Data Privacy Act review, BitLocker, offsite backup | To do |

8 of 15 tasks done.
<!-- STATUS:END -->

Phases 2 and 3 were tested headless on Linux only. **The user has not yet confirmed them on Windows.**

Test suites (all pass): `test_phase1.py` (18), `test_phase3.py` (13), `dev/gui_smoke_phase2.py`, `dev/gui_smoke_phase3.py`.
**Untested on Windows:** `os.startfile`, `explorer /select`, high-DPI behaviour, the `vista` ttk theme, PyMuPDF 2.1
import name (code tries `pymupdf` then `fitz`). First thing to do: ask the user how Phase 2/3 behaved on their PC.

## 3. Environment (user's machine)
- Windows, Python 3.14.5, Git 2.54. Project: `C:\Users\Admin\Desktop\JO things\Project\archive_system\ArchiveApp`.
- Virtual env at `ArchiveApp\.venv`; run with `.venv\Scripts\python`.
- **Device Guard** is active: always use `python -m pip ...` and `python -m PyInstaller ...`, never `pip` / `pyinstaller`
  directly. A test PyInstaller .exe built and ran fine.
- Libraries (requirements.txt): Pillow, PyMuPDF, openpyxl, pyinstaller, flask, waitress, pytesseract, watchdog.
  Tesseract OCR is **not installed** yet (only needed for OCR).
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

## 5. Architecture and conventions
```
app.py            start-up, DPI, logging, seeds profile.json once
db.py             schema + migrations (PRAGMA user_version). Add a new entry to MIGRATIONS; never edit old ones
storage.py        hashing, safe copy (tmp then os.replace), path guard, data-dir lookup
services.py       ALL rules. class Archive. The UI and the future web server call only this
backup.py/restore.py   backup + restore (pure functions, no UI)
ui/               Tkinter screens (main_window, add_dialog, type_dialogs, type_manager, tag_manager,
                  settings_window, maintenance, activity_log, recycle_bin, preview, widgets, common)
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

## 8. Task board
One task per line: `- [status] id | title | files | what the chat should do`. Status is `done`, `next` or `todo`; files are comma-separated
and may be empty. `tools\handoff_tool.py` reads these lines to build its menu and the file bundle for each task, so keep the format exact.
Exactly one task should be `next`. Add new tasks as `todo` lines; never renumber ids.

- [done] s0 | Setup: folders, venv, packages, git, PyInstaller test | | Built and ran clean on the user's PC.
- [done] p1 | Phase 1: database, storage, services, seeded types, tests | services.py, db.py, storage.py, test_phase1.py | User ran test_phase1.py on Windows: 18 of 18 pass.
- [done] p2 | Phase 2: main window, Add/Edit dialog, Recycle Bin | ui/main_window.py, ui/add_dialog.py | Tested headless on Linux only.
- [done] p3 | Phase 3: managers, settings, backup/restore, archive check, activity log | services.py, backup.py, restore.py | Tested headless on Linux only.
- [done] h1 | Handoff package: graphify graph, HANDOFF.md, helper tools | HANDOFF.md | Built 2026-11-06; automated 2026-11-09.
- [done] w1 | Verify Phases 2 and 3 on Windows and fix what breaks | | Windows run of the app and both test files. Report problems; fix with the smallest change. Use the bug option for each error.
- [done] 4a1 | Phase 4a: bulk import, logic and tests | services.py, storage.py, test_phase1.py | Add a service that imports a folder of existing scans with a default type and tags, reusing the duplicate checks. Public methods commit. Add tests first.
- [done] 4a2 | Phase 4a: bulk import window | ui/add_dialog.py, ui/main_window.py | Add an Import Folder window with a preview list, default type and tags, and a progress bar, using the import service.
- [next] 4b | Phase 4b: watch folder for the scanner | services.py, ui/main_window.py | Files dropped by the scanner appear in a Pending list that the user files one by one.
- [todo] 4c | Phase 4c: OCR text search | services.py, db.py, storage.py | Background OCR with Tesseract so text inside scans becomes searchable. Needs a schema migration. Tesseract is not installed yet.
- [todo] 4d | Phase 4d: thumbnails and export | services.py, ui/main_window.py | Thumbnails for faster browsing; export search results to CSV or Excel (low priority).
- [todo] 5 | Phase 5: read-only browser view | services.py, app.py, db.py | Flask + waitress in a background thread, 0.0.0.0, reusing services.py, one Archive per thread, write routes refused. Never exposed to the internet.
- [todo] 6 | Phase 6: roles, confidential filtering, final build | services.py, app.py, ui/main_window.py | View-only access if wanted, hide confidential documents from browser users, final build with python -m PyInstaller (prefer --onedir), auto-start, README update.
- [todo] x1 | Type setup export/import with preview | services.py, ui/type_manager.py, ui/common.py | Share document types between offices; the import only adds, never overwrites.
- [todo] x2 | Data Privacy Act review, BitLocker, offsite backup | | Non-code checklist for the office (RA 10173).

Before 4a: collect the remaining ~14 document types from the user (format `Type: detail (data type), ...`) and ask what "Source" holds for Resolutions and Executive Orders.

## 9. Working with this user
Direct and concise; minimal scaffolding; clean, ready-to-use files. Test before sending and say plainly what is untested.
Give runnable commands with `.venv\Scripts\python`. Do not claim something works on Windows unless the user confirmed it.
Ask at most one question at a time.

## 10. The code graph (graphify)
`graphify-out/` was built with `graphify update .` (code only, no LLM): 484 nodes, 17 clusters.
- Start with `graphify-out/GRAPH_REPORT.md` (core abstractions: `Archive`, `MainWindow`, `DocumentDialog`).
- Query: `graphify query "how is a backup recorded" --graph graphify-out/graph.json`, `graphify explain "Archive"`, `graphify path "A" "B"`.
- It maps **structure only**. For decisions and intent use this file. After code changes run `graphify update .`;
  for the docs (this file, README) run `/graphify . --update` in your assistant so they join the graph.
- Install: `uv tool install graphifyy` (or `pipx install graphifyy`), then `graphify install`.


## 11. Keeping this handoff current (do this at every milestone)
A milestone is a finished task whose tests pass. Record it the moment it is done, not at the end of the day.
```
.venv\Scripts\python tools\handoff_tool.py --milestone <id> --note "what was done, what is untested"
```
This marks the task done, promotes the next `todo` to `next`, runs every `test_*.py` and records the result, appends a dated line to the
milestone log, regenerates the status table, updates "Last updated", keeps `HANDOFF.md.bak`, and refreshes the code graph if graphify is installed.
Also edit by hand, keeping the formats: new decisions and their reason (section 4), changed conventions (section 5), schema changes (section 6),
and new tasks (section 8). Other commands: `--list` (show the board and any format problems), `--sync`, `--tests`.
The user runs `compile_for_chat.bat`; its menu is generated from section 8 and its first message from section 12, so what is written here is what the next chat sees.

## 12. Chat rules
These lines become the "Rules" in the first message of every chat bundle.
- Windows with Device Guard: use .venv\Scripts\python -m pip and -m PyInstaller.
- Business rules go in services.py with tests. The UI never touches SQL.
- In Archive, public methods commit; methods starting with an underscore never commit.
- Do not name methods or attributes on Tk widgets like Tk internals: _options, _name, _w, master.
- Output: complete files for new modules; exact find and replace blocks for edits; tests first.
- Tell me exactly which commands to run, and say plainly what you could not test.
- When a task is finished, give me the exact handoff_tool.py --milestone command to run, with id and note filled in.
- Keep answers short. Ask at most one question at a time.

## 13. Milestone log
Newest last. Written by `tools\handoff_tool.py --milestone`.
- 2026-11-05: p1 done - Phase 1. User ran test_phase1.py on Windows: 18 of 18 pass.
- 2026-11-06: p2, p3 done - Phases 2 and 3 built and tested headless on Linux. Handoff package and graphify code graph created. Not yet run on Windows.
- 2026-11-09: h1 done - handoff automation: task board, chat bundles generated from HANDOFF.md, milestone command.
- 2026-11-10: w1 done - Verify Phases 2 and 3 on Windows and fix what breaks. Phases 2 and 3 verified on Windows: test_phase1 and test_phase3 pass, app starts clean, open file, show in folder, PDF preview, DPI/layout, Recycle Bin delete/restore, backup all work. No bugs found. Not tested: restore.py, Settings window, Scanner inbox. Tests: test_phase1.py PASS; test_phase3.py PASS; test_phase4.py PASS; test_phase4b.py PASS.
- 2026-11-10: 4a1 done - Phase 4a: bulk import, logic and tests. Bulk import logic already existed: scan_folder and import_files in services.py, test_phase4.py 6 of 6 pass on Windows. Board was stale. Not seen this session: services.py code. Tests: test_phase1.py PASS; test_phase3.py PASS; test_phase4.py PASS; test_phase4b.py PASS.
- 2026-11-10: 4a1 done - Phase 4a: bulk import, logic and tests. Bulk import logic already existed: scan_folder and import_files in services.py, test_phase4.py 6 of 6 pass on Windows. Board was stale. Not seen this session: services.py code. Tests: test_phase1.py PASS; test_phase3.py PASS; test_phase4.py PASS; test_phase4b.py PASS.
- 2026-11-10: 4a2 done - Phase 4a: bulk import window. Import Folder window already existed: preview list, default type, tags and progress bar confirmed working on Windows by the user. Board was stale. Not seen this session: UI code. Tests: test_phase1.py PASS; test_phase3.py PASS; test_phase4.py PASS; test_phase4b.py PASS.
