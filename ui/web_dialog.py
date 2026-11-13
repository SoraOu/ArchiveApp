"""ui/web_dialog.py - Tools > Browser view: switch the read-only browser view on or off."""
import tkinter as tk
from tkinter import messagebox, ttk

import webserver
from services import ArchiveError

INTRO = ("The browser view lets other PCs on the office network search the archive and open documents "
         "in a web browser. It is read-only, and documents marked confidential are never shown. "
         "Do not open this port to the internet.")
NOTE = ("The first time it runs, Windows may ask to allow access: choose Private networks. "
        "Turning it off or changing the port takes effect the next time the app starts.")


class WebDialog:
    """Plain object that owns a Toplevel (no subclassing, so no clashes with Tk internal names)."""

    def __init__(self, parent, archive):
        self.parent = parent
        self.archive = archive
        cfg = archive.web_settings()
        self.win = tk.Toplevel(parent)
        self.win.title("Browser view")
        self.win.resizable(False, False)
        self.win.transient(parent)
        frame = ttk.Frame(self.win, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=INTRO, wraplength=460, justify="left").pack(anchor="w")

        self.enabled_var = tk.BooleanVar(master=self.win, value=cfg["enabled"])
        self.port_var = tk.StringVar(master=self.win, value=str(cfg["port"]))
        self.status_var = tk.StringVar(master=self.win)
        self.address_var = tk.StringVar(master=self.win)

        ttk.Checkbutton(frame, text="Start the browser view when the app starts",
                        variable=self.enabled_var).pack(anchor="w", pady=(12, 4))
        row = ttk.Frame(frame)
        row.pack(anchor="w", pady=4)
        ttk.Label(row, text="Port:").pack(side="left")
        ttk.Entry(row, textvariable=self.port_var, width=8).pack(side="left", padx=6)
        ttk.Label(frame, textvariable=self.status_var, font=("", 10, "bold")).pack(anchor="w", pady=(10, 2))
        ttk.Entry(frame, textvariable=self.address_var, state="readonly", width=60).pack(anchor="w")
        ttk.Label(frame, text=NOTE, wraplength=460, justify="left").pack(anchor="w", pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Close", command=self.win.destroy).pack(side="right")
        ttk.Button(buttons, text="Save", command=self.save).pack(side="right", padx=6)
        ttk.Button(buttons, text="Save and start now", command=self.start_now).pack(side="right")
        self.refresh_status()

    def run(self):
        self.win.grab_set()
        self.win.focus_set()
        self.parent.wait_window(self.win)

    def refresh_status(self):
        if webserver.manager.running:
            self.status_var.set("Running. Open this address in a browser on any office PC:")
            self.address_var.set("   or   ".join(webserver.manager.urls()))
        else:
            self.status_var.set("Not running.")
            self.address_var.set("")

    def error(self, text):
        messagebox.showerror("Browser view", text, parent=self.win)
        self.win.grab_set()                     # a closed messagebox takes the grab with it

    def save(self):
        try:
            self.archive.set_web_settings(self.enabled_var.get(), self.port_var.get())
        except ArchiveError as e:
            self.error(str(e))
            return False
        return True

    def start_now(self):
        if not self.save():
            return
        if webserver.manager.running:
            messagebox.showinfo("Browser view", "The browser view is already running.", parent=self.win)
            self.win.grab_set()
            return
        try:
            webserver.manager.start(self.archive.data_dir, self.archive.web_settings()["port"])
        except OSError as e:
            self.error(f"Could not start: the port may already be in use.\n\n{e}")
        except Exception as e:
            self.error(f"Could not start the browser view.\n\n{e}")
        self.refresh_status()
