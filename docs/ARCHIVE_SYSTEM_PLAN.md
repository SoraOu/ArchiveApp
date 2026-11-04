# Office Document Archive System: Project Plan

## 1. Overview

**Purpose:** A document archive for office use. Received documents are scanned, filed in the system with details and tags, and found again quickly.

**Deployment:**
- **Now:** a desktop application on the main PC (full access).
- **Later:** a locally hosted server on the main PC so other office PCs can view and search the archive through a web browser (view/download only).

**Scope:** office LAN only. No internet exposure.

---

## 2. Core Workflow

1. A document is received.
2. It is scanned.
3. The scanned file is added to the system.
4. A details window opens where the user enters:
   - Document name
   - Tags (free-form, any number)
   - Other details (type, date, sender, reference no., notes)
5. While typing a tag, the system suggests matching existing tags.
6. On save, the document is immediately searchable and accessible.

**Tag behavior**
- No pre-defined tags; users create them as needed.
- Typing suggests existing tags (prefix matches first, then "contains").
- Tags are normalized (trimmed, case-insensitive) to prevent duplicates such as "Budget" / "budget".
- Enter or click adds a tag as a chip.

---

## 3. Architecture

| Layer | Role | File |
|---|---|---|
| Database | Schema, queries, migrations | `db.py` |
| Storage | File copying, hashing, thumbnails, paths | `storage.py` |
| Services | Business rules (add document, merge tags, search) | `services.py` |
| UI | Tkinter windows | `ui/` |
| Server (later) | Flask routes calling `services.py` | `server.py` |

**Rule:** the UI never touches SQL directly. All logic goes through `services.py`, so the future web server reuses it unchanged.

**Stack**
- Python
- Tkinter (ttk) for the desktop UI
- SQLite for the database
- Flask or FastAPI with `waitress` for the later server
- PyInstaller for packaging

> **Environment note (Device Guard):** use `python -m pip` and `python -m PyInstaller` instead of calling `pip` or `pyinstaller` directly.

**Why SQLite is safe here:** only one process (the main PC app and its server) writes to the database. Never place the `.db` file on a shared network folder for multiple PCs to open.

---

## 4. Data Model

**documents**
- `id`, `name`, `file_path`, `original_filename`, `file_hash`, `page_count`
- `doc_type_id`, `doc_date`, `sender`, `reference_no`, `notes`
- `is_confidential`, `date_added`, `last_edited`, `is_deleted`

**tags**
- `id`, `name` (unique, case-insensitive)

**document_tags**
- `document_id`, `tag_id`

**doc_types**
- `id`, `name` (Memo, Letter, Report, Voucher, ...)

**document_files** *(for multi-file documents)*
- `id`, `document_id`, `file_path`, `file_hash`, `sort_order`

**audit_log**
- `id`, `timestamp`, `action`, `document_id`, `details`

**settings**
- `key`, `value` (archive path, backup path, last backup date)

**schema_version**
- Tracks migrations so new fields can be added later without rebuilding the database.

---

## 5. Features

### 5.1 Core (Phases 1 to 3)
- Add document (single file or multiple files)
- Copy files into the archive folder (not linked to the original location)
- Details form with preview
- Tag input with autosuggest and chips
- Search across name, tags, sender, reference no.
- Tag filters (multi-tag) and date range
- Sort and preview pane
- Open file in default viewer
- Edit details and re-tag
- Soft delete with Recycle Bin (restore or permanent delete)
- Duplicate detection by file hash
- Tag Manager (rename, merge, delete, usage counts)
- Document types list
- Settings (paths, backup)
- One-click backup and 7-day backup reminder
- Audit log

### 5.2 Enhancements (Phase 4)
- **OCR (Tesseract):** full-text search inside scanned documents, run in the background after saving
- **Watch folder:** scanner saves to a folder; files appear as "Pending" for filing
- **Bulk import:** import an existing folder of scans with default tags, then edit details later
- **Thumbnails** for faster browsing
- **Saved searches / Recent** list
- **Export** results to Excel/CSV

### 5.3 Server integration (Phases 5 and 6)
- Read-only browser UI with the same search and tag filters
- Roles: main PC = full access; browser users = view/download only
- Write routes restricted to `127.0.0.1`
- Login for browser users (optional if network is trusted)
- Confidential documents hidden from browser users
- Download logging

---

## 6. Screens

- **Main window:** search bar, tag sidebar, results table, preview pane
- **Add / Edit Document** window
- **Tag Manager**
- **Recycle Bin**
- **Pending (watch folder)** *(Phase 4)*
- **Settings**
- **Activity Log**

---

## 7. Folder Layout

```
ArchiveApp/
  app.py
  db.py
  storage.py
  services.py
  server.py              (later)
  ui/
    main_window.py
    add_dialog.py
    tag_manager.py
    recycle_bin.py
    settings_window.py
  data/
    archive.db
    archive/2026/11/<id>_<name>.pdf
    thumbs/
  backups/
  README.md
```

---

## 8. Build Phases

### Phase 1: Foundation
- Database schema, migrations
- Storage module (copy, hash, folder structure)
- Services: add document, search, tag handling

### Phase 2: Main Interface
- Main window (search, tag sidebar, results, preview)
- Add Document dialog with tag autosuggest and chips
- Edit document, open file

### Phase 3: Management
- Tag Manager, Recycle Bin, Settings
- Backup and reminder
- Audit log
- **Milestone:** a complete, usable desktop archive

### Phase 4: Enhancements
- OCR, watch folder, bulk import, thumbnails, export

### Phase 5: Server
- Flask server in a background thread (waitress, `0.0.0.0`)
- Read-only browser UI reusing `services.py`
- Network setup (see section 9)

### Phase 6: Security and Packaging
- Roles, logins, confidential filtering, download logging
- Package with `python -m PyInstaller --onefile --windowed app.py`
- Auto-start on boot, README/handover

---

## 9. Server and Network Setup (Phase 5)

- **Static IP:** reserve one for the main PC via DHCP reservation in the router.
- **Firewall:** inbound rule for the chosen port (e.g. 8000), Private profile only.
- **Network profile:** set to Private.
- **Power:** disable sleep on the main PC; use a UPS if possible.
- **Auto-start:** Task Scheduler ("at logon/startup") or NSSM.
- **Access:** other PCs open `http://MAIN-PC-IP:8000` in a browser.
- **Optional:** local hostname (e.g. `http://archive-pc:8000`) via router DNS.
- **Do not** port-forward to the internet.

---

## 10. Security and Compliance

- **BitLocker** on the main PC's drive.
- **Passwords** hashed (bcrypt/argon2) for browser logins.
- **HTTPS** optional on a closed LAN; add if data is sensitive (self-signed cert or Caddy).
- **Data Privacy Act (RA 10173):** documents containing personal information (beneficiary lists, health/nutrition records) have handling requirements. Use the confidential flag, logins, and encryption.
- **Records rules:** confirm the agency's retention and disposal schedule, and whether scans may replace paper originals.
- **Retention field:** optional keep-until/dispose date per document.

---

## 11. Backup and Continuity

- Nightly (or at least weekly) copy of `archive.db` and the `archive/` folder.
- Keep one copy on an external drive that is **not always connected** (ransomware and drive-failure protection).
- A backup stored only on the same PC does not count.
- Test a restore at least once.
- Set Windows active hours so automatic restarts don't take the server down.
- Write a README covering: data location, restore steps, how to rebuild the `.exe`.

---

## 12. Office Readiness

- **Scan standard:** agree on one format and quality (e.g. PDF, 200-300 dpi).
- **Tag guide:** one-page list of common tags and naming conventions.
- **Backlog:** plan the bulk import of any existing scans.
- **Numbering:** confirm whether the office has an incoming-document reference number format.
- **Pilot:** run with real documents for 2 weeks before full reliance.

---

## 13. Open Decisions

- [ ] Final "other details" fields (type, date, sender, reference no., notes, confidential flag)
- [ ] Which Phase 4 extras are in scope (OCR, watch folder, bulk import, multi-file, export)
- [ ] Reference number format
- [ ] Retention/disposal requirements
- [ ] Login required for browser users, or open on the LAN

---

## 14. Next Step

Build **Phases 1 to 3**: database, storage, services, main window, Add Document dialog with tag suggestions, Tag Manager, Recycle Bin, Settings, and backup.
