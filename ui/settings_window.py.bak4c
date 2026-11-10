"""ui/settings_window.py - office name, backup folder and reminders, maintenance."""
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ui.common import ModalWindow
from ui.maintenance import CheckDialog, start_backup


class SettingsWindow(ModalWindow):
    def __init__(self, parent, archive, on_change=None):
        super().__init__(parent, "Settings", "640x470")
        self.archive, self.on_change = archive, on_change
        self.resizable(False, False)
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        r = 0
        ttk.Label(body, text="Office name").grid(row=r, column=0, sticky="w", pady=5)
        self.office_var = tk.StringVar(value=archive.get_setting("office_name", ""))
        ttk.Entry(body, textvariable=self.office_var).grid(row=r, column=1, columnspan=2, sticky="ew", padx=(10, 0))

        r += 1
        ttk.Label(body, text="Data folder").grid(row=r, column=0, sticky="w", pady=5)
        ttk.Label(body, text=str(archive.data_dir), wraplength=360, justify="left").grid(
            row=r, column=1, sticky="w", padx=(10, 0))
        ttk.Button(body, text="Open", width=8, command=self._open_data).grid(row=r, column=2, padx=(6, 0))

        r += 1
        ttk.Separator(body).grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
        r += 1
        ttk.Label(body, text="Backup", font=("TkDefaultFont", 10, "bold")).grid(row=r, column=0, sticky="w")
        r += 1
        ttk.Label(body, text="Backup folder").grid(row=r, column=0, sticky="w", pady=5)
        self.backup_var = tk.StringVar(value=archive.get_setting("backup_dir", ""))
        ttk.Entry(body, textvariable=self.backup_var).grid(row=r, column=1, sticky="ew", padx=(10, 0))
        ttk.Button(body, text="Browse...", width=8, command=self._browse).grid(row=r, column=2, padx=(6, 0))
        r += 1
        ttk.Label(body, foreground="#666", wraplength=470, justify="left", text=(
            "Use an external drive that is not always plugged in. A copy on the same drive "
            "does not protect against drive failure or ransomware.")).grid(row=r, column=1, columnspan=2, sticky="w", padx=(10, 0))
        r += 1
        ttk.Label(body, text="Remind me every").grid(row=r, column=0, sticky="w", pady=5)
        rem = ttk.Frame(body)
        rem.grid(row=r, column=1, sticky="w", padx=(10, 0))
        self.days_var = tk.StringVar(value=str(archive.backup_status()["reminder_days"]))
        ttk.Spinbox(rem, from_=1, to=90, width=5, textvariable=self.days_var).pack(side="left")
        ttk.Label(rem, text=" days").pack(side="left")
        r += 1
        ttk.Label(body, text="Last backup").grid(row=r, column=0, sticky="w", pady=5)
        self.last_lbl = ttk.Label(body, text="")
        self.last_lbl.grid(row=r, column=1, sticky="w", padx=(10, 0))
        ttk.Button(body, text="Back up now", command=self._backup_now).grid(row=r, column=2, padx=(6, 0))
        self._show_last()

        r += 1
        ttk.Separator(body).grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
        r += 1
        ttk.Label(body, text="Maintenance", font=("TkDefaultFont", 10, "bold")).grid(row=r, column=0, sticky="w")
        r += 1
        ttk.Button(body, text="Check archive...", command=self._check).grid(row=r, column=1, sticky="w", padx=(10, 0), pady=5)
        r += 1
        ttk.Label(body, foreground="#666", wraplength=470, justify="left", text=(
            "To restore from a backup, close this program and run restore.py (see the README). "
            "It rebuilds the archive in a new, empty folder.")).grid(row=r, column=1, columnspan=2, sticky="w", padx=(10, 0))

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=14, pady=(0, 12), side="bottom")
        ttk.Button(bottom, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bottom, text="Save", command=self._save).pack(side="right", padx=6)

    def _show_last(self):
        st = self.archive.backup_status()
        if st["last_backup"] is None:
            self.last_lbl.configure(text="Never")
        else:
            when = st["last_backup"].replace("T", " ")
            d = st["days_ago"]
            self.last_lbl.configure(text=f"{when}  ({'today' if d == 0 else f'{d} day(s) ago'})")

    def _open_data(self):
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(self.archive.data_dir))
            else:
                subprocess.Popen(["xdg-open", str(self.archive.data_dir)])
        except Exception as e:
            messagebox.showerror("Cannot open folder", str(e), parent=self)
            self.regrab()

    def _browse(self):
        d = filedialog.askdirectory(parent=self, title="Choose the backup folder")
        self.regrab()
        if d:
            self.backup_var.set(d)

    def _store(self):
        try:
            days = max(1, min(90, int(self.days_var.get())))
        except ValueError:
            days = 7
        self.archive.set_setting("office_name", self.office_var.get().strip())
        self.archive.set_setting("backup_dir", self.backup_var.get().strip())
        self.archive.set_setting("backup_reminder_days", days)

    def _backup_now(self):
        self._store()
        start_backup(self, self.archive)
        self.regrab()
        self.backup_var.set(self.archive.get_setting("backup_dir", ""))
        self._show_last()

    def _check(self):
        CheckDialog(self, self.archive).run()
        self.regrab()

    def _save(self):
        self._store()
        if self.on_change:
            self.on_change()
        self.destroy()
