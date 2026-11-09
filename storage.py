"""storage.py - file handling: hashing, safe copying into the archive, paths."""
import configparser
import hashlib
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def app_dir():
    """Folder of the .exe when frozen, otherwise the folder of this file."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def default_data_dir():
    """Data folder: [paths] data_dir in config.ini if set, else <app folder>\\data."""
    cfg = app_dir() / "config.ini"
    if cfg.exists():
        parser = configparser.ConfigParser()
        try:
            parser.read(cfg, encoding="utf-8")
            value = parser.get("paths", "data_dir", fallback="").strip()
            if value:
                return Path(value)
        except configparser.Error:
            pass
    return app_dir() / "data"


def sanitize_filename(name, max_len=80):
    """Make text safe to use as part of a Windows file name."""
    s = _INVALID.sub("_", str(name))
    s = re.sub(r"\s+", " ", s).strip(" .")
    if s.split(".")[0].upper() in _RESERVED:
        s = "_" + s
    return s[:max_len].rstrip(" .") or "document"


def sha256_file(path, chunk=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


class Storage:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.archive_dir = self.data_dir / "archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def store_file(self, src, doc_id, display_name, seq=0, expected_hash=None):
        """Copy src into archive/YYYY/MM/. Returns the path relative to archive/ (forward slashes)."""
        src = Path(src)
        now = datetime.now()
        folder = self.archive_dir / f"{now:%Y}" / f"{now:%m}"
        folder.mkdir(parents=True, exist_ok=True)

        base = f"{doc_id}_{sanitize_filename(display_name, 60)}"
        suffix = f"_{seq + 1}" if seq else ""
        ext = src.suffix.lower()
        dest = folder / f"{base}{suffix}{ext}"
        n = 2
        while dest.exists():
            dest = folder / f"{base}{suffix}_{n}{ext}"
            n += 1

        tmp = dest.with_name(dest.name + ".tmp")
        try:
            shutil.copy2(src, tmp)
            if expected_hash and sha256_file(tmp) != expected_hash:
                raise IOError(f"Copy of '{src.name}' did not match the original. Try again.")
            os.replace(tmp, dest)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        return dest.relative_to(self.archive_dir).as_posix()

    def abs_path(self, rel):
        """Absolute path for a stored relative path (refuses to leave the archive folder)."""
        root = self.archive_dir.resolve()
        p = (root / rel).resolve()
        if root not in p.parents:
            raise ValueError("Invalid archive path")
        return p

    def all_files(self):
        """Every file under archive/ as a relative path (forward slashes)."""
        root = self.archive_dir
        return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())

    def exists(self, rel):
        try:
            return self.abs_path(rel).is_file()
        except ValueError:
            return False

    def delete_file(self, rel):
        """Delete a stored file and any empty month/year folders left behind."""
        try:
            p = self.abs_path(rel)
        except ValueError:
            return
        p.unlink(missing_ok=True)
        root = self.archive_dir.resolve()
        parent = p.parent
        while parent != root and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
