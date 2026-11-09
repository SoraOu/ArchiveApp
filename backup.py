"""backup.py - copy the database and archived files to another folder (e.g. an external drive).

Layout created inside the chosen folder:
    OfficeArchiveBackup/
        db_snapshots/archive_YYYYMMDD_HHMMSS.db   (the newest ones are kept)
        archive/...                               (every scanned file, copied only once)
        backup_info.json

Archived files never change after they are stored, so a repeat backup only copies new files.
To restore, use restore.py (or restore_backup below) into a new, empty folder.
"""
import json
import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

ROOT_NAME = "OfficeArchiveBackup"


class BackupError(Exception):
    pass


def backup_root(dest_dir):
    return Path(dest_dir) / ROOT_NAME


def check_destination(data_dir, dest_dir):
    """Raise BackupError if the destination is unusable. Returns a warning string when the
    destination is on the same drive as the data (not a real backup), else None."""
    data, dest = Path(data_dir).resolve(), Path(dest_dir).resolve()
    if dest == data or data in dest.parents:
        raise BackupError("The backup folder cannot be inside the archive's data folder.")
    if not dest.exists():
        raise BackupError(f"The backup folder does not exist:\n{dest}")
    d1, d2 = os.path.splitdrive(str(data))[0].lower(), os.path.splitdrive(str(dest))[0].lower()
    if d1 and d1 == d2:
        return (f"The backup folder is on the same drive ({d1.upper()}) as the archive. "
                "If that drive fails, both copies are lost. Use an external drive for a real backup.")
    return None


def run_backup(data_dir, dest_dir, progress=None, cancel=None, keep_snapshots=10):
    """Snapshot the database, then copy any archived files not yet in the backup.
    progress(done, total, name) is called per file; cancel() -> True stops the backup."""
    data = Path(data_dir)
    db_path, archive = data / "archive.db", data / "archive"
    if not db_path.is_file():
        raise BackupError("No archive database found to back up.")
    check_destination(data, dest_dir)
    started = time.time()
    root = backup_root(dest_dir)
    snaps, files_dir = root / "db_snapshots", root / "archive"
    snaps.mkdir(parents=True, exist_ok=True)
    files_dir.mkdir(parents=True, exist_ok=True)

    # 1. consistent database snapshot (safe even while the app is open)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap = snaps / f"archive_{stamp}.db"
    n = 2
    while snap.exists():                       # two backups in the same second keep separate snapshots
        snap = snaps / f"archive_{stamp}_{n}.db"
        n += 1
    tmp = snap.with_name(snap.name + ".tmp")
    src, dst = sqlite3.connect(str(db_path)), sqlite3.connect(str(tmp))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    check = sqlite3.connect(str(tmp))
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if result != "ok":
        tmp.unlink(missing_ok=True)
        raise BackupError("The database copy failed its integrity check. Nothing was backed up.")
    os.replace(tmp, snap)
    for old in sorted(snaps.glob("archive_*.db"))[:-keep_snapshots]:
        old.unlink(missing_ok=True)

    # 2. files (only the ones the backup does not have yet)
    files = sorted(p for p in archive.rglob("*") if p.is_file() and not p.name.endswith(".tmp"))
    copied = copied_bytes = 0
    for i, p in enumerate(files, start=1):
        if cancel and cancel():
            raise BackupError("Backup cancelled. The database snapshot was saved; some files were not copied.")
        rel = p.relative_to(archive)
        dest = files_dir / rel
        size = p.stat().st_size
        if not dest.exists() or dest.stat().st_size != size:
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_name(dest.name + ".tmp")
            shutil.copy2(p, part)
            os.replace(part, dest)
            copied += 1
            copied_bytes += size
        if progress:
            progress(i, len(files), rel.as_posix())

    info = {"completed": datetime.now().isoformat(timespec="seconds"), "snapshot": snap.name,
            "files_total": len(files), "files_copied": copied, "bytes_copied": copied_bytes,
            "seconds": round(time.time() - started, 1), "destination": str(root)}
    (root / "backup_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


def list_snapshots(backup_dir):
    root = Path(backup_dir)
    if (root / ROOT_NAME).is_dir():
        root = root / ROOT_NAME
    return sorted((root / "db_snapshots").glob("archive_*.db"), reverse=True)


def restore_backup(backup_dir, target_data_dir, snapshot=None, progress=None):
    """Rebuild a data folder from a backup. The target must not already contain an archive."""
    root = Path(backup_dir)
    if (root / ROOT_NAME).is_dir():
        root = root / ROOT_NAME
    snaps = list_snapshots(root)
    if not snaps:
        raise BackupError(f"No database snapshots found in {root}")
    chosen = next((s for s in snaps if s.name == snapshot), None) if snapshot else snaps[0]
    if chosen is None:
        raise BackupError(f"Snapshot {snapshot} not found.")
    target = Path(target_data_dir)
    if (target / "archive.db").exists():
        raise BackupError("The target folder already contains an archive. Restore into a new, empty folder.")
    target.mkdir(parents=True, exist_ok=True)
    part = target / "archive.db.tmp"
    shutil.copy2(chosen, part)
    os.replace(part, target / "archive.db")

    src_files = root / "archive"
    files = sorted(p for p in src_files.rglob("*") if p.is_file() and not p.name.endswith(".tmp"))
    for i, p in enumerate(files, start=1):
        dest = target / "archive" / p.relative_to(src_files)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(p, dest)
        if progress:
            progress(i, len(files), p.name)

    conn = sqlite3.connect(str(target / "archive.db"))
    try:
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        missing = [r[0] for r in conn.execute("SELECT file_path FROM document_files")
                   if not (target / "archive" / r[0]).is_file()]
    finally:
        conn.close()
    return {"snapshot": chosen.name, "documents": docs, "files_restored": len(files), "missing_files": missing,
            "target": str(target)}
