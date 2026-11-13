r"""apply_4d_fix.py - thumbnail frame + wider thumbnail column.
Run from the ArchiveApp folder:  .venv\Scripts\python apply_4d_fix.py
Makes services.py.bak2 and ui\main_window.py.bak2 first. Changes nothing if an edit does not match."""
import shutil
from pathlib import Path

SV = [('f"{row[\'file_hash\']}_{size}.png"', 'f"{row[\'file_hash\']}_{size}_v2.png"')]
MW = [('''        self.tree.column("#0", width=self._thumb_px + 12, minwidth=self._thumb_px + 12,
                         stretch=False, anchor="center")''',
       '''        col_w = self._thumb_px + 20 + int(14 * self._thumb_px / 44)    # 20 px tree indent + picture + margin
        self.tree.column("#0", width=col_w, minwidth=col_w, stretch=False, anchor="center")''')]


def patch(path, edits, marker):
    raw = Path(path).read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    if marker in text:
        return None, f"{path}: already patched, skipped"
    for i, (a, b) in enumerate(edits, start=1):
        if text.count(a) != 1:
            raise SystemExit(f"STOPPED. {path}: edit {i} matched {text.count(a)} times (needs 1). "
                             "Run apply_4d.py first. Nothing was changed.")
        text = text.replace(a, b)
    return (text.replace("\n", "\r\n") if crlf else text), f"{path}: {len(edits)} edit applied"


if __name__ == "__main__":
    jobs = [("services.py", SV, "_v2.png"), (str(Path("ui") / "main_window.py"), MW, "col_w =")]
    for p, _, _ in jobs:
        if not Path(p).is_file():
            raise SystemExit(f"STOPPED. {p} not found. Run this from the ArchiveApp folder.")
    results = [(p,) + patch(p, e, m) for p, e, m in jobs]
    for p, new, msg in results:
        if new is not None:
            shutil.copy2(p, p + ".bak2")
            Path(p).write_bytes(new.encode("utf-8"))
        print(msg)
    print(r"Done. Next: replace thumbs.py and test_phase4d.py, then .venv\Scripts\python test_phase4d.py")
