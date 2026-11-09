"""ui/type_dialogs.py - dialogs shown when a new document type is entered."""
import tkinter as tk
from tkinter import messagebox, ttk

from services import key, norm
from ui.widgets import AutoSuggestEntry

DATA_TYPE_NAMES = {
    "text": "Text",
    "longtext": "Long text",
    "number": "Number",
    "id": "ID / Reference no.",
    "year": "Year",
    "date": "Date",
    "name": "Name",
    "yesno": "Yes / No",
    "dropdown": "Dropdown (choices)",
}
_NAME_TO_TYPE = {v: k for k, v in DATA_TYPE_NAMES.items()}


def _center(win, parent):
    win.update_idletasks()
    try:
        x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 3
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    except tk.TclError:
        pass


def _make_modal(win):
    win.wait_visibility()
    try:
        win.grab_set()
    except tk.TclError:
        pass


class NewTypeDialog(tk.Toplevel):
    """'This type does not exist. Create it?' with 'did you mean' suggestions."""

    def __init__(self, parent, text, similar):
        super().__init__(parent)
        self.result = None
        self.title("New document type?")
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"\u201c{text}\u201d is not an existing document type.",
                  wraplength=380, font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self.listbox = None
        if similar:
            ttk.Label(body, text="Did you mean one of these?").pack(anchor="w", pady=(10, 3))
            self.listbox = tk.Listbox(body, height=min(len(similar), 5), exportselection=False)
            for s in similar:
                self.listbox.insert("end", s)
            self.listbox.pack(fill="x")
            self.listbox.selection_set(0)
            self.listbox.bind("<Double-1>", lambda e: self._use_selected())
            ttk.Button(body, text="Use selected type", command=self._use_selected).pack(anchor="w", pady=(4, 0))
        ttk.Label(body, text="Otherwise, create it as a new type and tell the system what\n"
                             "details this kind of document carries.", justify="left").pack(anchor="w", pady=(12, 8))
        row = ttk.Frame(body)
        row.pack(fill="x")
        ttk.Button(row, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(row, text="Create new type", command=self._create).pack(side="right", padx=6)
        self.bind("<Escape>", lambda e: self.destroy())
        _center(self, parent.winfo_toplevel())
        _make_modal(self)

    def _use_selected(self):
        if self.listbox is not None and self.listbox.curselection():
            self.result = ("existing", self.listbox.get(self.listbox.curselection()[0]))
            self.destroy()

    def _create(self):
        self.result = ("new", None)
        self.destroy()


def ask_new_type(parent, text, similar):
    dlg = NewTypeDialog(parent, text, similar)
    parent.wait_window(dlg)
    return dlg.result


class FieldBuilderDialog(tk.Toplevel):
    """Define the details (fields) of a new document type."""

    def __init__(self, parent, archive, type_name):
        super().__init__(parent)
        self.archive = archive
        self.result = None
        self.rows = []
        self.title("New document type")
        self.transient(parent.winfo_toplevel())
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"Details for \u201c{type_name}\u201d",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        ttk.Label(body, justify="left", text=(
            "Add only the details people search by, such as the number, a date or a name.\n"
            "1 to 3 is enough. Everything is optional when filing, and you can add more later.")
        ).pack(anchor="w", pady=(2, 10))

        self.grid_frame = ttk.Frame(body)
        self.grid_frame.pack(fill="x")
        for col, text in enumerate(("Field name", "Data type", "Choices (comma separated)", "Duplicate check", "")):
            ttk.Label(self.grid_frame, text=text, font=("TkDefaultFont", 9, "bold")).grid(
                row=0, column=col, sticky="w", padx=3, pady=(0, 3))
        self.grid_frame.columnconfigure(0, weight=1)
        self._add_row()

        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="+ Add field", command=self._add_row).pack(side="left")
        ttk.Label(body, foreground="#666", text=(
            "Duplicate check: tick the field(s) that identify a document, e.g. Year + Version.\n"
            "The system will warn if the same values are filed twice.")).pack(anchor="w", pady=(8, 0))
        bottom = ttk.Frame(body)
        bottom.pack(fill="x", pady=(12, 0))
        ttk.Button(bottom, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bottom, text="Save type", command=self._save).pack(side="right", padx=6)
        self.bind("<Escape>", lambda e: self.destroy())
        _center(self, parent.winfo_toplevel())
        _make_modal(self)

    def _add_row(self):
        row = {}
        label = AutoSuggestEntry(
            self.grid_frame,
            lambda text: [s["label"] for s in self.archive.suggest_field_labels(text)],
            on_select=lambda text, r=row: self._label_picked(r, text), width=26)
        type_var = tk.StringVar(value=DATA_TYPE_NAMES["text"])
        type_cb = ttk.Combobox(self.grid_frame, textvariable=type_var, state="readonly", width=20,
                               values=list(DATA_TYPE_NAMES.values()))
        choices_var = tk.StringVar()
        choices = ttk.Entry(self.grid_frame, textvariable=choices_var, width=30, state="disabled")
        key_var = tk.BooleanVar(value=False)
        key_cb = ttk.Checkbutton(self.grid_frame, variable=key_var)
        remove = ttk.Button(self.grid_frame, text="\u2715", width=3, command=lambda r=row: self._remove_row(r))
        type_cb.bind("<<ComboboxSelected>>", lambda e, r=row: self._type_changed(r))
        row.update(label=label, type_var=type_var, type_cb=type_cb, choices_var=choices_var,
                   choices=choices, key_var=key_var, key_cb=key_cb, remove=remove)
        self.rows.append(row)
        self._regrid()
        label.focus_entry()

    def _regrid(self):
        for i, r in enumerate(self.rows, start=1):
            r["label"].grid(row=i, column=0, sticky="ew", padx=3, pady=2)
            r["type_cb"].grid(row=i, column=1, padx=3, pady=2)
            r["choices"].grid(row=i, column=2, padx=3, pady=2)
            r["key_cb"].grid(row=i, column=3, padx=3, pady=2)
            r["remove"].grid(row=i, column=4, padx=3, pady=2)

    def _remove_row(self, row):
        if len(self.rows) == 1:
            row["label"].set("")
            return
        self.rows.remove(row)
        for k in ("label", "type_cb", "choices", "key_cb", "remove"):
            row[k].destroy()
        self._regrid()

    def _type_changed(self, row):
        is_dd = _NAME_TO_TYPE.get(row["type_var"].get()) == "dropdown"
        row["choices"].configure(state="normal" if is_dd else "disabled")

    def _label_picked(self, row, text):
        for s in self.archive.suggest_field_labels(text):
            if key(s["label"]) == key(text):
                row["type_var"].set(DATA_TYPE_NAMES.get(s["data_type"], "Text"))
                self._type_changed(row)
                break

    def _save(self):
        specs, seen = [], set()
        for r in self.rows:
            label = norm(r["label"].get())
            if not label:
                continue
            if key(label) in seen:
                messagebox.showerror("Duplicate field", f"\u201c{label}\u201d appears more than once.", parent=self)
                return
            seen.add(key(label))
            data_type = _NAME_TO_TYPE.get(r["type_var"].get(), "text")
            spec = {"label": label, "data_type": data_type, "is_key": bool(r["key_var"].get())}
            if data_type == "dropdown":
                spec["options"] = [o for o in r["choices_var"].get().split(",") if o.strip()]
            specs.append(spec)
        self.result = specs
        self.destroy()

    def show(self):
        self.master.wait_window(self)
        return self.result
