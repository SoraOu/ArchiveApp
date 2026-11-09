"""ui/import_dialog.py - Import a folder of existing scans (bulk import)."""
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from services import ArchiveError
from ui.type_dialogs import _center
from ui.widgets import TagInput

NO_TYPE = "(no type - decide later)"


class ImportDialog(tk.Toplevel):
    """Pick a folder, choose a default type and tags, import every scan in it.
    Check .result after it closes: None if nothing was imported, else the import report."""

    def __init__(self, parent, archive):
        super().__init__(parent)
        self.archive = archive
        self.result = None
        self._files = []
        self._running = False
        self._stop_flag = False
        self._type_ids = {}

        self.title("Import a folder of scans")
        self.transient(parent.winfo_toplevel())
        self.minsize(640, 560)
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda e: self._close())
        _center(self, parent.winfo_toplevel())
        self.wait_visibility()
        self._regrab()

    # ------------------------------------------------------------ layout
    def _build(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        r = 0
        ttk.Label(root, text="Folder").grid(row=r, column=0, sticky="w", pady=4)
        self.folder_var = tk.StringVar()
        ttk.Entry(root, textvariable=self.folder_var).grid(row=r, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(root, text="Browse...", command=self._pick_folder).grid(row=r, column=2, pady=4)

        r += 1
        self.sub_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(root, text="Include files in sub-folders", variable=self.sub_var,
                        command=self._scan).grid(row=r, column=1, sticky="w", padx=8)

        r += 1
        self.count_var = tk.StringVar(value="Choose a folder to see how many scans it holds.")
        ttk.Label(root, textvariable=self.count_var, foreground="#444").grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(8, 2))

        r += 1
        lf = ttk.Frame(root)
        lf.grid(row=r, column=0, columnspan=3, sticky="nsew")
        root.rowconfigure(r, weight=1)
        self.file_list = tk.Listbox(lf, height=8, exportselection=False, activestyle="none")
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=sb.set)
        self.file_list.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")

        r += 1
        opts = ttk.LabelFrame(root, text="Apply to every imported document", padding=8)
        opts.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        opts.columnconfigure(1, weight=1)
        ttk.Label(opts, text="Document type").grid(row=0, column=0, sticky="w", pady=3)
        self.type_var = tk.StringVar(value=NO_TYPE)
        self.type_cb = ttk.Combobox(opts, textvariable=self.type_var, state="readonly", width=34)
        self.type_cb.grid(row=0, column=1, sticky="w", padx=8, pady=3)
        names = [NO_TYPE]
        for t in self.archive.list_types():
            full = self.archive.get_type(t["id"])
            if any(f["is_required"] for f in full["fields"]):
                continue                    # bulk import cannot fill required details
            self._type_ids[t["name"]] = t["id"]
            names.append(t["name"])
        self.type_cb.configure(values=names)
        ttk.Label(opts, text="Tags").grid(row=1, column=0, sticky="nw", pady=3)
        self.tags = TagInput(opts, self.archive.suggest_tags)
        self.tags.grid(row=1, column=1, sticky="ew", padx=8, pady=3)
        self.review_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text=f"Add the tag “{self.archive.REVIEW_TAG}” so I can find these later "
                        "and fill in their details", variable=self.review_var).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=3)
        self.conf_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Mark all as confidential", variable=self.conf_var).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=3)

        r += 1
        ttk.Label(root, text="Each file becomes one document named after the file. Files already in the "
                  "archive are skipped.", foreground="#666", wraplength=600).grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(4, 6))

        r += 1
        self.bar = ttk.Progressbar(root, mode="determinate")
        self.bar.grid(row=r, column=0, columnspan=3, sticky="ew")
        r += 1
        self.status_var = tk.StringVar()
        ttk.Label(root, textvariable=self.status_var, foreground="#444").grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(2, 6))

        r += 1
        bottom = ttk.Frame(root)
        bottom.grid(row=r, column=0, columnspan=3, sticky="e")
        self.close_btn = ttk.Button(bottom, text="Close", command=self._close)
        self.close_btn.pack(side="right")
        self.start_btn = ttk.Button(bottom, text="Import", command=self._start, state="disabled")
        self.start_btn.pack(side="right", padx=6)

    # ------------------------------------------------------------ helpers
    def _regrab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _pick_folder(self):
        folder = filedialog.askdirectory(parent=self, title="Folder with scanned files")
        self._regrab()
        if folder:
            self.folder_var.set(folder)
            self._scan()

    def _scan(self):
        folder = self.folder_var.get().strip()
        self._files = []
        self.file_list.delete(0, "end")
        self.start_btn.configure(state="disabled")
        if not folder:
            return
        try:
            self._files = self.archive.scan_folder(folder, recursive=self.sub_var.get())
        except ArchiveError as e:
            self.count_var.set(str(e))
            return
        base = Path(folder)
        for p in self._files[:500]:
            try:
                shown = p.relative_to(base)
            except ValueError:
                shown = p
            self.file_list.insert("end", str(shown))
        n = len(self._files)
        more = "  (first 500 shown)" if n > 500 else ""
        self.count_var.set(f"{n} scan file(s) found (PDF, JPG, PNG, TIF, BMP).{more}" if n
                           else "No scan files found in this folder.")
        if n:
            self.start_btn.configure(state="normal")

    # ------------------------------------------------------------ import
    def _on_progress(self, i, n, name):
        self.bar.configure(maximum=n, value=i)
        self.status_var.set(f"Importing {i} of {n}: {name}")
        self.update()                                    # keep the window responsive

    def _start(self):
        if self._running or not self._files:
            return
        n = len(self._files)
        if not messagebox.askyesno("Import", f"Import {n} file(s) into the archive?\n\n"
                                   "Each file is copied into the archive and filed as its own document.",
                                   parent=self):
            self._regrab()
            return
        self._regrab()
        type_id = self._type_ids.get(self.type_var.get())
        tags = self.tags.get_tags()
        pending = self.tags.entry.get().strip()
        if pending:
            tags.append(pending)
        self._running, self._stop_flag = True, False
        self.start_btn.configure(state="disabled")
        self.close_btn.configure(text="Stop")
        try:
            report = self.archive.import_files(
                self._files, type_id=type_id, tags=tags, confidential=self.conf_var.get(),
                review_tag=self.archive.REVIEW_TAG if self.review_var.get() else None,
                progress=self._on_progress, cancel=lambda: self._stop_flag)
        except (ArchiveError, ValueError, OSError) as e:
            self._running = False
            self.close_btn.configure(text="Close")
            self.start_btn.configure(state="normal")
            messagebox.showerror("Import failed", str(e), parent=self)
            self._regrab()
            return
        self._running = False
        self.close_btn.configure(text="Close")
        self.result = report
        self._show_summary(report)
        self._scan()                                     # shows what is left, if anything

    def _show_summary(self, rep):
        lines = [f"Imported: {len(rep['imported'])}",
                 f"Skipped (already in the archive): {len(rep['skipped'])}",
                 f"Failed: {len(rep['failed'])}"]
        if rep["cancelled"]:
            lines.insert(0, "Stopped early. What was already imported is kept.")
        for f in rep["failed"][:5]:
            lines.append(f"  • {Path(f['path']).name}: {f['error']}")
        if len(rep["failed"]) > 5:
            lines.append(f"  ...and {len(rep['failed']) - 5} more (see Tools > Activity Log)")
        if rep["imported"] and self.review_var.get():
            lines.append(f"\nFind them later with the tag “{self.archive.REVIEW_TAG}”.")
        self.status_var.set(f"Done. {len(rep['imported'])} imported.")
        messagebox.showinfo("Import finished", "\n".join(lines), parent=self)
        self._regrab()

    def _close(self):
        if self._running:                                # Stop: finish the current file, then end
            self._stop_flag = True
            self.status_var.set("Stopping after the current file...")
            return
        self.destroy()
