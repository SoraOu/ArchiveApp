# Office Document Archive

A finding aid for the office's scanned documents. File a scan with a document type, details and tags,
then search and open it later. It does not process documents or connect to other systems.

## Run
```
cd ArchiveApp
.venv\Scripts\python app.py
```
First run creates `data\` and loads the starter types from `profile.json`.

## Where things are
| Item | Location |
|---|---|
| Database | `data\archive.db` |
| Scanned files | `data\archive\YYYY\MM\` (copied in, named `<id>_<name>.ext`) |
| Error log | `data\app.log` |
| Settings | inside the database (File > Settings) |
| Move the data folder | add `data_dir = D:\OfficeArchiveData` under `[paths]` in `config.ini` |

Never put `data\` on a network share or a cloud-synced folder. Only the main PC opens the database.

## Day to day
- **File a document:** + Add Document, pick the scan(s), choose or type the document type, fill in details and tags, Save.
- **New type:** type a name that does not exist; the app asks, then you list the details it carries.
- **Fix mistakes:** Manage > Document Types (rename, merge, edit fields) and Manage > Tags (rename, merge, delete).
- **Deleted by accident:** File > Recycle Bin.
- **Who did what:** Tools > Activity Log.

## Backup (do this weekly)
1. File > Settings, choose the backup folder on an **external drive that is not always plugged in**.
2. File > Back up now. The first run copies everything; later runs copy only new files.
3. The app reminds you when a backup is overdue (default 7 days, once a day at most).

A backup is the folder `OfficeArchiveBackup\` containing `db_snapshots\` (newest 10 database copies)
and `archive\` (every scanned file).

## Restore
Close the app, then restore into a **new, empty** folder:
```
.venv\Scripts\python restore.py  E:\  D:\ArchiveRestored
```
(`E:\` is the folder you chose for backups.) Then add this to `config.ini`:
```
[paths]
data_dir = D:\ArchiveRestored
```
Test a restore once, before you need it.

## Check the archive
Tools > Check archive finds database errors, files that are listed but missing, and stray files.
"Verify file contents" also detects files that were changed after filing (slow on large archives).

## Updating the program
Replace the program files (`app.py`, `services.py`, `ui\`, ...) with the new version. Do not touch `data\`
or `config.ini`. The database upgrades itself on the next start. Make a backup first.

## Tests
```
.venv\Scripts\python test_phase1.py
.venv\Scripts\python test_phase3.py
```
They run in a temporary folder and never touch real data.

## If something goes wrong
- Look at `data\app.log`.
- "database is locked": make sure only one copy of the app is running.
- Missing files: restore them from the latest backup, then run Tools > Check archive.

## Files
`app.py` start-up | `services.py` all rules | `db.py` schema and upgrades | `storage.py` file handling |
`backup.py` / `restore.py` backup and restore | `profile.json` starter types | `ui\` screens
