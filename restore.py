r"""restore.py - rebuild the archive from a backup into a NEW, EMPTY folder.

Usage (close the archive app first):
    .venv\Scripts\python restore.py  <backup folder>  <new data folder>  [snapshot file name]

Example:
    .venv\Scripts\python restore.py  E:\  D:\ArchiveRestored

<backup folder> is the folder you chose for backups (the one that contains OfficeArchiveBackup).
Afterwards, point the app to the restored data by adding this to config.ini:
    [paths]
    data_dir = D:\ArchiveRestored
"""
import sys

import backup


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    try:
        result = backup.restore_backup(argv[1], argv[2], snapshot=argv[3] if len(argv) > 3 else None,
                                       progress=lambda i, n, name: print(f"\r  copying files {i}/{n}", end=""))
    except backup.BackupError as e:
        print(f"\nRestore failed: {e}")
        return 1
    print(f"\nRestored from snapshot {result['snapshot']}")
    print(f"  Documents : {result['documents']}")
    print(f"  Files     : {result['files_restored']}")
    if result["missing_files"]:
        print(f"  WARNING: {len(result['missing_files'])} file(s) listed in the database were not in the backup:")
        for p in result["missing_files"][:20]:
            print("   -", p)
    print(f"\nNext: add to config.ini\n  [paths]\n  data_dir = {result['target']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
