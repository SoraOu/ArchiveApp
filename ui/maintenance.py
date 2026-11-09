"""ui/maintenance.py - backup progress window and archive check window."""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import backup
from ui.common import ModalWindow


def _mb(n):
    return f"{n / (1024 * 1024):.1f} MB"


class BackupDialog(ModalWindow):
    """Runs the backup in the background and shows progress."""

    def __init__(self, parent, archive, dest_dir):
        super().__init__(parent, "Backing up", "520x190")
        self.archive, self.dest = archive, dest_dir
        self.ok = False
        self._q = queue.Queue()
        self._cancel = threading.Event()
        self._finished = False
        self.resizable(False, False)
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        self.status = ttk.Label(body, text=f"Copying to {dest_dir} ...", wraplength=480, justify="left")
        self.status.pack(anchor="w")
        self.bar = ttk.Progressbar(body, mode="indeterminate", length=480)
        self.bar.pack(fill="x", pady=10)
        self.bar.start(12)
        self.detail = ttk.Label(body, text="", foreground="#666", wraplength=480, justify="left")
        self.detail.pack(anchor="w")
        row = ttk.Frame(body)
        row.pack(fill="x", side="bottom", pady=(10, 0))
        self.btn = ttk.Button(row, text="Cancel", command=self._on_button)
        self.btn.pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self._on_button)
        self.bind("<Escape>", lambda e: self._on_button())
        threading.Thread(target=self._work, daemon=True).start()
        self.after(100, self._poll)

    def _work(self):
        try:
            info = backup.run_backup(
                self.archive.data_dir, self.dest, cancel=self._cancel.is_set,
                progress=lambda i, n, name: self._q.put(("progress", i, n, name)))
            self._q.put(("done", info))
        except Exception as e:
            self._q.put(("error", str(e)))

    def _poll(self):
        last = None
        try:
            while True:
                msg = self._q.get_nowait()
                if msg[0] == "progress":
                    last = msg
                else:
                    return self._finish(msg)
        except queue.Empty:
            pass
        if last:
            _, i, n, name = last
            if self.bar.cget("mode") != "determinate":
                self.bar.stop()
                self.bar.configure(mode="determinate", maximum=max(n, 1))
            self.bar["value"] = i
            self.detail.configure(text=f"{i} of {n} files checked   {name}")
        if not self._finished:
            self.after(100, self._poll)

    def _finish(self, msg):
        self._finished = True
        self.bar.stop()
        self.btn.configure(text="Close")
        if msg[0] == "done":
            info = msg[1]
            self.ok = True
            self.archive.record_backup(info)
            self.bar.configure(mode="determinate", maximum=1)
            self.bar["value"] = 1
            self.title("Backup complete")
            self.status.configure(text=(
                f"Backup complete.\n{info['files_copied']} new file(s) copied ({_mb(info['bytes_copied'])}), "
                f"{info['files_total']} file(s) in total.\nSaved in: {info['destination']}"))
            self.detail.configure(text="")
        else:
            self.title("Backup failed")
            self.status.configure(text=f"The backup did not finish:\n{msg[1]}")
            self.detail.configure(text="")

    def _on_button(self):
        if self._finished:
            self.destroy()
        else:
            self._cancel.set()
            self.btn.configure(state="disabled")
            self.status.configure(text="Cancelling...")


def start_backup(parent, archive):
    """Ask for a backup folder if none is set, then run the backup. Returns True if it completed."""
    dest = archive.get_setting("backup_dir")
    if not dest or not Path(dest).is_dir():
        dest = filedialog.askdirectory(parent=parent, title="Choose the backup folder (an external drive is best)")
        if not dest:
            return False
        archive.set_setting("backup_dir", dest)
    try:
        warning = backup.check_destination(archive.data_dir, dest)
    except backup.BackupError as e:
        messagebox.showerror("Backup folder", str(e), parent=parent)
        return False
    if warning and archive.get_setting("backup_same_drive_ok") != dest:
        if not messagebox.askyesno("Same drive", warning + "\n\nBack up here anyway?", parent=parent, icon="warning"):
            return False
        archive.set_setting("backup_same_drive_ok", dest)
    dlg = BackupDialog(parent, archive, dest)
    dlg.run()
    return dlg.ok


class CheckDialog(ModalWindow):
    """Look for missing files, stray files and (optionally) changed files."""

    def __init__(self, parent, archive):
        super().__init__(parent, "Check archive", "720x520", (600, 400))
        self.archive = archive
        self._q = queue.Queue()
        self._cancel = threading.Event()
        self._orphans = []
        self._running = False
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, wraplength=660, justify="left", text=(
            "Checks the database for errors, finds files that are listed but missing from the archive folder, "
            "and finds files in the archive folder that no document uses.")).pack(anchor="w")
        opts = ttk.Frame(body)
        opts.pack(fill="x", pady=8)
        self.verify_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Also verify that file contents are unchanged (slow for large archives)",
                        variable=self.verify_var).pack(side="left")
        self.run_btn = ttk.Button(opts, text="Run check", command=self.start)
        self.run_btn.pack(side="right")
        self.bar = ttk.Progressbar(body, mode="determinate")
        self.bar.pack(fill="x")
        frame = ttk.Frame(body)
        frame.pack(fill="both", expand=True, pady=8)
        self.text = tk.Text(frame, wrap="word", state="disabled", relief="solid", borderwidth=1, height=14)
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.text.tag_configure("bad", foreground="#b00020")
        self.text.tag_configure("good", foreground="#1b7f2a")
        self.text.tag_configure("head", font=("TkDefaultFont", 10, "bold"))
        row = ttk.Frame(body)
        row.pack(fill="x")
        ttk.Button(row, text="Close", command=self._close).pack(side="right")
        self.orphan_btn = ttk.Button(row, text="Delete stray files", command=self._delete_orphans, state="disabled")
        self.orphan_btn.pack(side="right", padx=6)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _write(self, text, tag=None):
        self.text.configure(state="normal")
        self.text.insert("end", text, tag)
        self.text.configure(state="disabled")

    def start(self):
        if self._running:
            return
        self._running = True
        self._cancel.clear()
        self.run_btn.configure(state="disabled")
        self.orphan_btn.configure(state="disabled")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.bar.configure(value=0, maximum=1)
        verify = self.verify_var.get()

        def work():
            try:
                rep = self.archive.check_integrity(
                    verify_hashes=verify, cancel=self._cancel.is_set,
                    progress=lambda i, n, p: self._q.put(("progress", i, n)))
                self._q.put(("done", rep))
            except Exception as e:
                self._q.put(("error", str(e)))
        threading.Thread(target=work, daemon=True).start()
        self.after(100, self._poll)

    def _poll(self):
        last = None
        try:
            while True:
                msg = self._q.get_nowait()
                if msg[0] == "progress":
                    last = msg
                else:
                    return self._report(msg)
        except queue.Empty:
            pass
        if last:
            self.bar.configure(maximum=max(last[2], 1))
            self.bar["value"] = last[1]
        self.after(100, self._poll)

    def _report(self, msg):
        self._running = False
        self.run_btn.configure(state="normal")
        if msg[0] == "error":
            self._write(f"The check could not finish:\n{msg[1]}\n", "bad")
            return
        rep = msg[1]
        self.bar["value"] = self.bar["maximum"]
        problems = 0
        self._write("Database\n", "head")
        if rep["database_ok"]:
            self._write("  No errors found.\n", "good")
        else:
            problems += 1
            self._write(f"  Problem: {rep['database_message']}\n", "bad")
        self._write(f"\nFiles listed by documents: {rep['files_checked']}\n", "head")
        if rep["missing_files"]:
            problems += len(rep["missing_files"])
            self._write(f"  {len(rep['missing_files'])} file(s) are missing from the archive folder:\n", "bad")
            for m in rep["missing_files"][:50]:
                self._write(f"   - {m['name']}  ({m['path']})\n")
            self._write("  Restore them from a backup if you have one.\n")
        else:
            self._write("  None missing.\n", "good")
        if self.verify_var.get():
            if rep["changed_files"]:
                problems += len(rep["changed_files"])
                self._write(f"  {len(rep['changed_files'])} file(s) differ from what was originally stored:\n", "bad")
                for m in rep["changed_files"][:50]:
                    self._write(f"   - {m['name']}  ({m['path']})\n")
            else:
                self._write("  All file contents match.\n", "good")
        self._write("\nStray files (in the archive folder but not used by any document)\n", "head")
        self._orphans = rep["orphan_files"]
        if self._orphans:
            problems += len(self._orphans)
            self._write(f"  {len(self._orphans)} found:\n", "bad")
            for p in self._orphans[:50]:
                self._write(f"   - {p}\n")
            self.orphan_btn.configure(state="normal")
        else:
            self._write("  None.\n", "good")
        self._write("\n" + ("Everything looks fine." if problems == 0 else f"{problems} issue(s) found."),
                    "good" if problems == 0 else "bad")

    def _delete_orphans(self):
        if not messagebox.askyesno("Delete stray files",
                                   f"Delete {len(self._orphans)} file(s) that no document uses?\nThis cannot be undone.",
                                   parent=self, icon="warning"):
            self.regrab()
            return
        self.regrab()
        n = self.archive.remove_orphan_files(self._orphans)
        messagebox.showinfo("Done", f"{n} file(s) deleted.", parent=self)
        self.regrab()
        self.start()

    def _close(self):
        self._cancel.set()
        self.destroy()
