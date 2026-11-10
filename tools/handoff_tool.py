"""handoff_tool.py - keeps HANDOFF.md and the AI-chat bundles in sync. Standard library only.

HANDOFF.md is the single source of truth:
  * its "Task board" section decides which tasks appear in the menu and which files each task needs
  * its "Chat rules" section becomes the rules in the first message
  * recording a milestone updates the board, the status table, the log and the "Last updated" date

Run from the ArchiveApp folder (compile_for_chat.bat does this for you):
    python tools\\handoff_tool.py                      interactive menu
    python tools\\handoff_tool.py --list               show the parsed task board and any format problems
    python tools\\handoff_tool.py --task ID            build the chat bundle for a task (no menu)
    python tools\\handoff_tool.py --bug --files "a.py" bundle for a bug (add --error-file err.txt)
    python tools\\handoff_tool.py --custom --files "a.py b.py" --text "what to do"
    python tools\\handoff_tool.py --milestone ID --note "what was done" [--no-tests]
    python tools\\handoff_tool.py --tests              run every test_*.py
    python tools\\handoff_tool.py --sync               regenerate the status table
Add --no-open --no-clip to skip opening the folder and copying to the clipboard.

Task board line format (one task per line, in the "Task board" section):
    - [status] id | title | files, separated, by, commas | what the chat should do
    status is done, next or todo. files may be empty.
"""
import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE.parent / "HANDOFF.md").exists() else Path.cwd()
HANDOFF = ROOT / "HANDOFF.md"
OUT = ROOT / "_for_chat"

TASK_RE = re.compile(r"^- \[(done|next|todo)\]\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*(.*?)\s*$")
STATUS_START, STATUS_END = "<!-- STATUS:START -->", "<!-- STATUS:END -->"
WORD = {"done": "Done", "next": "Next", "todo": "To do"}
DEFAULT_RULES = [
    "Windows with Device Guard: use .venv\\Scripts\\python -m pip and -m PyInstaller.",
    "Business rules go in services.py with tests. The UI never touches SQL.",
    "Output: complete files for new modules; exact find and replace blocks for edits; tests first.",
    "Tell me exactly which commands to run, and say plainly what you could not test.",
    "Keep answers short. Ask at most one question at a time.",
]
BLOCKED_PREFIX = ("data/", "backups/", "scans/", "samples/", ".venv/", "_for_chat/", ".git/", "graphify-out/cache/")
BLOCKED_EXT = {".db", ".sqlite", ".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif",
               ".webp", ".zip", ".exe", ".log", ".bak"}
BLOCKED_NAME = {"config.ini"}
WARN_KB = 120


# ------------------------------------------------------------------ reading HANDOFF.md
class Task:
    def __init__(self, status, tid, title, files, text, line_no):
        self.status, self.id, self.title, self.text, self.line_no = status, tid, title, text, line_no
        self.files = [f.strip().replace("\\", "/") for f in re.split(r"[,;]", files) if f.strip()]


def read_text():
    if not HANDOFF.exists():
        sys.exit(f"HANDOFF.md not found in {ROOT}. Run this from the ArchiveApp folder.")
    return HANDOFF.read_text(encoding="utf-8").replace("\r\n", "\n")


def section_span(lines, heading_pattern):
    """(first body line, line after the last body line) of the '## ...' section matching the pattern."""
    start = None
    for i, line in enumerate(lines):
        if start is None and re.match(r"^## .*" + heading_pattern, line, re.I):
            start = i + 1
        elif start is not None and line.startswith("## "):
            return start, i
    return (start, len(lines)) if start is not None else (None, None)


def parse(text=None):
    """Returns (tasks, rules, last_updated, problems)."""
    text = read_text() if text is None else text
    lines = text.split("\n")
    tasks, problems = [], []
    a, b = section_span(lines, "Task board")
    if a is None:
        problems.append('No "Task board" section found in HANDOFF.md.')
    else:
        seen = set()
        for n in range(a, b):
            line = lines[n].rstrip("\r")
            if not line.startswith("- ["):
                continue
            m = TASK_RE.match(line)
            if not m:
                problems.append(f"Line {n + 1} is not a valid task line: {line[:70]}")
                continue
            t = Task(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), n)
            if t.id in seen:
                problems.append(f"Line {n + 1}: duplicate task id {t.id}")
            seen.add(t.id)
            tasks.append(t)
    rules = []
    a, b = section_span(lines, "Chat rules")
    if a is not None:
        rules = [l[2:].strip() for l in lines[a:b] if l.startswith("- ") and l[2:].strip()]
    m = re.search(r"Last updated:?\s*(\d{4}-\d{2}-\d{2})", text)
    return tasks, rules or DEFAULT_RULES, (m.group(1) if m else "unknown"), problems


def open_tasks(tasks):
    return sorted((t for t in tasks if t.status != "done"), key=lambda t: (t.status != "next", t.line_no))


# ------------------------------------------------------------------ bundle
def check_file(rel):
    """Return (ok, reason). Never lets confidential data, binaries or paths outside the project through."""
    norm = rel.replace("\\", "/").strip()
    while norm.startswith("./"):
        norm = norm[2:]
    low = norm.lower()
    if norm.startswith("/") or re.match(r"^[a-z]:", low) or ".." in low.split("/"):
        return False, "outside the project"
    p = (ROOT / norm).resolve()
    try:
        p.relative_to(ROOT.resolve())
    except ValueError:
        return False, "outside the project"
    if low.startswith(BLOCKED_PREFIX) or Path(low).name in BLOCKED_NAME or Path(low).suffix in BLOCKED_EXT:
        return False, "confidential or not text"
    if not p.is_file():
        return False, "not found"
    return True, ""


def copy_to_clipboard(text):
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return True
    except Exception:
        pass
    if sys.platform.startswith("win"):
        try:
            subprocess.run(["clip"], input=text.encode("mbcs", "replace"), check=True)
            return True
        except Exception:
            pass
    return False


def edit_error_text(path):
    path.write_text("Paste the full error text below this line, then save and close Notepad.\n" + "-" * 60 + "\n",
                    encoding="utf-8")
    if sys.platform.startswith("win"):
        subprocess.run(["notepad", str(path)])
    else:
        print("Paste the error text, then finish with an empty line:")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if not line:
                break
            lines.append(line)
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def build_bundle(files, task_text, bug=False, error_file=None, open_folder=True, clip=True):
    tasks, rules, updated, _ = parse()
    nxt = next((t for t in open_tasks(tasks) if t.status == "next"), None)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    included, skipped, total = [], [], 0
    all_text = []
    err_text = ""
    if bug:
        err_path = OUT / "error.txt"
        if error_file:
            err_path.write_text(Path(error_file).read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        else:
            edit_error_text(err_path)
        err_text = err_path.read_text(encoding="utf-8", errors="replace")
        all_text.append(f"===== FILE: error.txt =====\n{err_text}\n")
    wanted = ["HANDOFF.md"]
    for f in files:
        f = f.replace("\\", "/").strip()
        while f.startswith("./"):
            f = f[2:]
        if f and f.lower() not in [w.lower() for w in wanted]:
            wanted.append(f)
    for rel in wanted:
        ok, why = check_file(rel)
        if not ok:
            skipped.append(f"{rel} ({why})")
            continue
        src = ROOT / rel
        data = src.read_text(encoding="utf-8", errors="replace")
        total += src.stat().st_size
        all_text.append(f"===== FILE: {rel} =====\n{data}\n")
        shutil.copy2(src, OUT / rel.replace("/", "_"))
        included.append(rel)
    (OUT / "ALL_IN_ONE.txt").write_text("\n".join(all_text), encoding="utf-8")
    msg = [
        "I'm continuing a project mid-way. HANDOFF.md is in the attached file ALL_IN_ONE.txt: read it fully first.",
        "The attached file holds these files, each starting with a line like ===== FILE: name =====",
        "Files: " + " ".join(included),
        f"HANDOFF.md was last updated {updated}." + (f" Current milestone: {nxt.title}." if nxt else ""),
    ]
    if bug:
        msg.append("The error text is in the section named error.txt.")
    msg += ["", f"Task: {task_text}", "", "Ask me for any other file you need instead of guessing its contents.", "Rules:"]
    msg += [f"- {r}" for r in rules]
    message = "\n".join(msg) + "\n"
    (OUT / "FIRST_MESSAGE.txt").write_text(message, encoding="utf-8")
    copied = copy_to_clipboard(message) if clip else False
    gi = ROOT / ".gitignore"
    if gi.exists() and "_for_chat/" not in gi.read_text(encoding="utf-8", errors="replace"):
        with open(gi, "a", encoding="utf-8") as g:
            g.write("\n_for_chat/\n")
    kb = round(total / 1024)
    print("\n" + "=" * 44 + "\n  Bundle ready\n" + "=" * 44)
    print("  Included: " + (" ".join(included) or "(nothing)"))
    if skipped:
        print("  SKIPPED : " + "; ".join(skipped))
    print(f"  Size    : about {kb} KB" + ("   <- large; consider fewer files" if kb > WARN_KB else ""))
    print("\n  1. Open a new chat and paste (Ctrl+V). " +
          ("The first message is on your clipboard." if copied else "Clipboard failed: open FIRST_MESSAGE.txt and copy it."))
    print(f"  2. Attach ONE file: {OUT / 'ALL_IN_ONE.txt'}")
    print(f"  3. Also saved: {OUT / 'FIRST_MESSAGE.txt'}")
    if open_folder and sys.platform.startswith("win"):
        os.startfile(str(OUT))
    return {"included": included, "skipped": skipped, "kb": kb, "copied": copied}


# ------------------------------------------------------------------ tests / graph
def run_tests(verbose=True):
    results = []
    for path in sorted(ROOT.glob("test_*.py")):
        if verbose:
            print(f"  running {path.name} ...", flush=True)
        try:
            p = subprocess.run([sys.executable, str(path)], cwd=str(ROOT), capture_output=True,
                               text=True, timeout=900)
            lines = [l for l in (p.stdout + p.stderr).splitlines() if l.strip()]
            results.append((path.name, p.returncode == 0, lines[-1] if lines else "(no output)"))
        except subprocess.TimeoutExpired:
            results.append((path.name, False, "timed out"))
    return results


def tests_summary(results):
    if not results:
        return "no test files found"
    return "; ".join(f"{n} {'PASS' if ok else 'FAIL'}" for n, ok, _ in results)


def refresh_graph():
    try:
        p = subprocess.run([sys.executable, "-m", "graphify", "update", "."], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=300)
        return p.returncode == 0
    except Exception:
        return False


# ------------------------------------------------------------------ writing HANDOFF.md
def render_status(tasks):
    done = sum(t.status == "done" for t in tasks)
    rows = ["| Id | Task | Status |", "|---|---|---|"]
    rows += [f"| {t.id} | {t.title} | {WORD[t.status]} |" for t in tasks]
    return "\n".join(rows) + f"\n\n{done} of {len(tasks)} tasks done."


def with_status_block(text, tasks):
    block = f"{STATUS_START}\n{render_status(tasks)}\n{STATUS_END}"
    if STATUS_START in text and STATUS_END in text:
        a, b = text.index(STATUS_START), text.index(STATUS_END) + len(STATUS_END)
        return text[:a] + block + text[b:]
    return text


def save(text):
    if HANDOFF.exists():
        shutil.copy2(HANDOFF, ROOT / "HANDOFF.md.bak")
    gi = ROOT / ".gitignore"
    if gi.exists() and "HANDOFF.md.bak" not in gi.read_text(encoding="utf-8", errors="replace"):
        with open(gi, "a", encoding="utf-8") as g:
            g.write("\nHANDOFF.md.bak\n")
    tmp = ROOT / "HANDOFF.md.tmp"
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, HANDOFF)


def record_milestone(task_id, note, run_tests_now=True, graph=True):
    text = read_text()
    tasks, _, _, problems = parse(text)
    lines = text.split("\n")
    target = next((t for t in tasks if t.id.lower() == (task_id or "").lower()), None) if task_id and task_id != "-" else None
    if task_id and task_id != "-" and target is None:
        sys.exit(f"No task with id '{task_id}'. Use --list to see the ids.")
    summary = "not run"
    if run_tests_now:
        res = run_tests()
        summary = tests_summary(res)
        for name, ok, line in res:
            print(f"   {'PASS' if ok else 'FAIL'}  {name}: {line}")
    today = datetime.date.today().isoformat()
    if target and target.status != "done":
        lines[target.line_no] = lines[target.line_no].replace(f"[{target.status}]", "[done]", 1)
        target.status = "done"
    if not any(t.status == "next" for t in tasks):
        first = next((t for t in tasks if t.status == "todo"), None)
        if first:
            lines[first.line_no] = lines[first.line_no].replace("[todo]", "[next]", 1)
            first.status = "next"
    entry = f"- {today}: " + (f"{target.id} done - {target.title}. " if target else "") + (note.strip().rstrip(".") + ". " if note and note.strip() else "") + f"Tests: {summary}."
    a, b = section_span(lines, "Milestone log")
    if a is None:
        lines += ["", "## Milestone log", entry]
    else:
        end = b
        while end > a and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, entry)
    text = "\n".join(lines)
    text = re.sub(r"(Last updated:?\s*)\d{4}-\d{2}-\d{2}", r"\g<1>" + today, text, count=1)
    new_tasks, _, _, _ = parse(text)
    text = with_status_block(text, new_tasks)
    save(text)
    print(f"\n  HANDOFF.md updated ({today}). Backup: HANDOFF.md.bak")
    if target:
        nxt = next((t for t in new_tasks if t.status == "next"), None)
        print(f"  Done: {target.title}" + (f"\n  Next: {nxt.title}" if nxt else "\n  No tasks left on the board."))
    if graph:
        print("  Code graph refreshed." if refresh_graph() else "  Code graph not refreshed (graphify not installed - fine).")
    print("  Remember: git add -A and git commit.")


def sync():
    text = read_text()
    tasks, _, _, _ = parse(text)
    save(with_status_block(text, tasks))
    print("  Status table regenerated.")


# ------------------------------------------------------------------ menus
def show_board(tasks, problems):
    print("\nTask board (from HANDOFF.md):")
    for t in tasks:
        print(f"  [{t.status:>4}] {t.id:<6} {t.title}" + (f"   <{', '.join(t.files)}>" if t.files else ""))
    for p in problems:
        print("  PROBLEM:", p)


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return "0"


def split_files(s):
    return [f for f in re.split(r"[\s,;]+", s.replace('"', "")) if f]


def interactive():
    while True:
        tasks, _, updated, problems = parse()
        todo = open_tasks(tasks)
        os.system("cls" if os.name == "nt" else "clear")
        print("=" * 52 + "\n  Prepare files for an AI chat\n" + "=" * 52)
        print(f"  Read from HANDOFF.md (last updated {updated}). Pick a task:\n")
        for i, t in enumerate(todo, 1):
            print(f"  {i:>2}  [{t.status}] {t.title}")
        print("\n   B  Fix a bug or error\n   C  Custom - I choose the files\n"
              "   M  Record a milestone (updates HANDOFF.md)\n   T  Run all tests\n   L  Show the whole task board\n   0  Exit\n")
        for p in problems:
            print("  PROBLEM in HANDOFF.md:", p)
        c = ask("  Choose: ").lower()
        if c in ("0", "q", ""):
            return
        if c == "l":
            show_board(tasks, problems)
        elif c == "t":
            res = run_tests()
            print()
            for n, ok, line in res:
                print(f"   {'PASS' if ok else 'FAIL'}  {n}: {line}")
        elif c == "m":
            interactive_milestone(tasks)
        elif c == "b":
            files = split_files(ask("  File(s) named in the error, separated by spaces (Enter = none): "))
            default = "Fix the problem described in error.txt with the smallest change."
            text = ask(f"  Task [{default}]: ") or default
            build_bundle(files, text, bug=True)
        elif c == "c":
            files = split_files(ask("  Files, separated by spaces, relative to this folder: "))
            text = ask("  Task in one line: ") or "Describe the task here."
            build_bundle(files, text)
        elif c.isdigit() and 1 <= int(c) <= len(todo):
            t = todo[int(c) - 1]
            print(f"\n  Task: {t.text}")
            text = ask("  Type your own task in one line, or press Enter to use this one: ") or t.text
            build_bundle(t.files, text)
        else:
            continue
        ask("\n  Press Enter to go back to the menu... ")


def interactive_milestone(tasks):
    todo = open_tasks(tasks)
    print("\n  Which task did you finish?")
    for i, t in enumerate(todo, 1):
        print(f"  {i:>2}  {t.title}")
    print("   0  None of these (just add a note)")
    c = ask("  Choose: ")
    tid = todo[int(c) - 1].id if c.isdigit() and 1 <= int(c) <= len(todo) else "-"
    note = ask("  One-line note (what was done, what is still untested): ")
    tests = ask("  Run the tests now and record the result? [Y/n]: ").lower() != "n"
    record_milestone(tid, note, run_tests_now=tests)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(add_help=True, description="Read HANDOFF.md, build chat bundles, record milestones.")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--task")
    ap.add_argument("--bug", action="store_true")
    ap.add_argument("--custom", action="store_true")
    ap.add_argument("--files", default="")
    ap.add_argument("--text", default="")
    ap.add_argument("--error-file")
    ap.add_argument("--milestone")
    ap.add_argument("--note", default="")
    ap.add_argument("--no-tests", action="store_true")
    ap.add_argument("--no-graph", action="store_true")
    ap.add_argument("--tests", action="store_true")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--no-clip", action="store_true")
    a = ap.parse_args()
    opts = {"open_folder": not a.no_open, "clip": not a.no_clip}
    if a.list:
        tasks, rules, updated, problems = parse()
        show_board(tasks, problems)
        print(f"\n  Last updated: {updated}\n  Chat rules ({len(rules)}):")
        for r in rules:
            print("   -", r)
        return 1 if problems else 0
    if a.tests:
        res = run_tests()
        for n, ok, line in res:
            print(f"   {'PASS' if ok else 'FAIL'}  {n}: {line}")
        return 0 if all(ok for _, ok, _ in res) else 1
    if a.sync:
        sync()
        return 0
    if a.milestone is not None:
        record_milestone(a.milestone, a.note, run_tests_now=not a.no_tests, graph=not a.no_graph)
        return 0
    if a.task:
        tasks, _, _, _ = parse()
        t = next((x for x in tasks if x.id.lower() == a.task.lower()), None)
        if not t:
            sys.exit(f"No task with id '{a.task}'. Use --list.")
        build_bundle(t.files, a.text or t.text, **opts)
        return 0
    if a.bug or a.custom:
        build_bundle(split_files(a.files), a.text or ("Fix the problem described in error.txt with the smallest change."
                     if a.bug else "Describe the task here."), bug=a.bug, error_file=a.error_file, **opts)
        return 0
    interactive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
