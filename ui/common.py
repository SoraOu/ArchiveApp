"""ui/common.py - shared base window and small dialogs."""
import tkinter as tk
from tkinter import ttk


class ModalWindow(tk.Toplevel):
    """A window that blocks the one behind it. Call run() to show it and wait for it to close."""

    def __init__(self, parent, title, size=None, minsize=None):
        super().__init__(parent)
        self.title(title)
        self.transient(parent.winfo_toplevel())
        if size:
            self.geometry(size)
        if minsize:
            self.minsize(*minsize)
        self.bind("<Escape>", lambda e: self.destroy())

    def center(self):
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except tk.TclError:
            pass

    def regrab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def make_modal(self):
        self.center()
        self.wait_visibility()
        self.regrab()

    def run(self):
        self.make_modal()
        self.master.wait_window(self)
        return self


class AskText(ModalWindow):
    def __init__(self, parent, title, prompt, initial=""):
        super().__init__(parent, title)
        self.result = None
        self.resizable(False, False)
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=prompt, wraplength=360, justify="left").pack(anchor="w")
        self.var = tk.StringVar(value=initial)
        entry = ttk.Entry(body, textvariable=self.var, width=44)
        entry.pack(fill="x", pady=(8, 10))
        row = ttk.Frame(body)
        row.pack(fill="x")
        ttk.Button(row, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(row, text="OK", command=self._ok).pack(side="right", padx=6)
        entry.bind("<Return>", lambda e: self._ok())
        entry.focus_set()
        entry.select_range(0, "end")

    def _ok(self):
        text = self.var.get().strip()
        if text:
            self.result = text
            self.destroy()


def ask_text(parent, title, prompt, initial=""):
    return AskText(parent, title, prompt, initial).run().result


class ChoiceDialog(ModalWindow):
    """Pick one item from a list. result is the chosen text, or None."""

    def __init__(self, parent, title, message, choices, default=None, button="OK"):
        super().__init__(parent, title)
        self.result = None
        self.resizable(False, False)
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=message, wraplength=420, justify="left").pack(anchor="w")
        self.var = tk.StringVar(value=default if default in choices else (choices[0] if choices else ""))
        ttk.Combobox(body, textvariable=self.var, values=list(choices), state="readonly", width=46).pack(
            fill="x", pady=(10, 12))
        row = ttk.Frame(body)
        row.pack(fill="x")
        ttk.Button(row, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(row, text=button, command=self._ok).pack(side="right", padx=6)

    def _ok(self):
        self.result = self.var.get() or None
        self.destroy()


def ask_choice(parent, title, message, choices, default=None, button="OK"):
    return ChoiceDialog(parent, title, message, choices, default, button).run().result
