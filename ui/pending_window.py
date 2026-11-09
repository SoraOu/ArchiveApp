"""ui/pending_window.py - Scanner inbox: scans waiting in the watch folder, ready to be filed."""
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from services import ArchiveError
from ui.add_dialog import DocumentDialog, open_with_default_app
from ui.preview import Preview
from ui.type_dialogs import _center

REFRESH_MS = 4000


def _size_text(n):
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


class PendingWindow(tk.Toplevel):
    """Not modal: it can stay open while you work. on_change(doc_id) is called after a document is filed."""

    def __init__(self, parent, archive, on_change=None):
        super().__init__(parent)
        self.archive = archive
        self.on_change = on_change
        self._by_iid = {}
        self._after_id = None
        self._filing = False

        self.title("Scanner inbox")
        self.transient(parent.winfo_toplevel())
        self.minsize(900, 560)
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda e: self._close())
        _center(self, parent.winfo_toplevel())
        self.reload()
        self._schedule()
        if self.archive.get_watch_folder() is None:
            self.after(200, self._first_run)

    # ------------------------------------------------------------ layout
    def _build(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0)
        root.rowconfigure(2, weight=1)

        top = ttk.Frame(root)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="Scanner folder:").grid(row=0, column=0, sticky="w")
        self.folder_var = tk.StringVar()
        ttk.Label(top, textvariable=self.folder_var, foreground="#333").grid(
            row=0, column=1, sticky="w", padx=8)
        ttk.Button(top, text="Choose folder...", command=self.choose_folder).grid(row=0, column=2)

        self.info_var = tk.StringVar()
        ttk.Label(root, textvariable=self.info_var, foreground="#444").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(6, 4))

        lf = ttk.Frame(root)
        lf.grid(row=2, column=0, sticky="nsew")
        cols = ("name", "size", "scanned")
        self.tree = ttk.Treeview(lf, columns=cols, show="headings", selectmode="extended")
        for col, text, w, stretch in (("name", "File", 320, True), ("size", "Size", 80, False),
                                      ("scanned", "Scanned", 140, False)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, minwidth=60, stretch=stretch, anchor="w")
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.file_selected())
        self.tree.bind("<Return>", lambda e: self.file_selected())

        self.preview = Preview(root, width=340, height=420)
        self.preview.grid(row=2, column=1, sticky="ns", padx=(10, 0))

        bottom = ttk.Frame(root)
        bottom.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.file_btn = ttk.Button(bottom, text="File selected...", command=self.file_selected)
        self.file_btn.pack(side="left")
        self.open_btn = ttk.Button(bottom, text="Open", command=self.open_selected)
        self.open_btn.pack(side="left", padx=6)
        self.dismiss_btn = ttk.Button(bottom, text="Dismiss", command=self.dismiss_selected)
        self.dismiss_btn.pack(side="left")
        self.restore_btn = ttk.Button(bottom, text="Restore dismissed", command=self.restore_dismissed)
        self.restore_btn.pack(side="left", padx=6)
        ttk.Button(bottom, text="Close", command=self._close).pack(side="right")
        ttk.Label(root, text="Select several files to file them together as one document (extra pages). "
                  "Dismissed scans stay in the folder but are no longer listed.",
                  foreground="#666", wraplength=820).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.preview.clear("Select a scan")

    # ------------------------------------------------------------ refresh
    def _schedule(self):
        self._after_id = self.after(REFRESH_MS, self._tick)

    def _tick(self):
        self._after_id = None
        try:
            if not self._filing:
                self.reload()
            self._schedule()
        except tk.TclError:
            pass

    def reload(self):
        res = self.archive.pending_files()
        self.folder_var.set(res["folder"] or "(not chosen yet)")
        keep = {self._by_iid[i]["path"] for i in self.tree.selection() if i in self._by_iid}
        self.tree.delete(*self.tree.get_children())
        self._by_iid = {}
        for n, f in enumerate(res["files"]):
            iid = str(n)
            self._by_iid[iid] = f
            when = datetime.fromtimestamp(f["modified"]).strftime("%Y-%m-%d %H:%M")
            self.tree.insert("", "end", iid=iid, values=(f["name"], _size_text(f["size"]), when))
            if f["path"] in keep:
                self.tree.selection_add(iid)
        if res["error"]:
            self.info_var.set(res["error"])
        elif res["folder"] is None:
            self.info_var.set("Choose the folder your scanner saves to.")
        else:
            msg = f"{len(res['files'])} scan(s) waiting to be filed."
            if res["busy"]:
                msg += f"  ({res['busy']} still being saved by the scanner)"
            self.info_var.set(msg)
        ignored = self.archive.ignored_count()
        self.restore_btn.configure(text=f"Restore dismissed ({ignored})" if ignored else "Restore dismissed",
                                   state="normal" if ignored else "disabled")
        self._on_select()

    def _selected(self):
        return [self._by_iid[i] for i in self.tree.selection() if i in self._by_iid]

    def _on_select(self, ev=None):
        sel = self._selected()
        state = "normal" if sel else "disabled"
        for b in (self.file_btn, self.open_btn, self.dismiss_btn):
            b.configure(state=state)
        if sel:
            self.preview.show(Path(sel[0]["path"]))
        else:
            self.preview.clear("Select a scan")

    # ------------------------------------------------------------ actions
    def _first_run(self):
        if messagebox.askyesno("Scanner inbox", "Choose the folder your scanner saves to now?", parent=self):
            self.choose_folder()

    def choose_folder(self):
        start = self.archive.get_watch_folder()
        folder = filedialog.askdirectory(parent=self, title="Folder your scanner saves to",
                                         initialdir=str(start) if start else None)
        if not folder:
            return
        try:
            self.archive.set_watch_folder(folder)
        except ArchiveError as e:
            messagebox.showerror("Cannot use this folder", str(e), parent=self)
            return
        self.reload()
        if self.on_change:
            self.on_change(None)

    def open_selected(self):
        sel = self._selected()
        if not sel:
            return
        try:
            open_with_default_app(sel[0]["path"])
        except Exception as e:
            messagebox.showerror("Cannot open file", str(e), parent=self)

    def dismiss_selected(self):
        sel = self._selected()
        if not sel:
            return
        if not messagebox.askyesno("Dismiss", f"Dismiss {len(sel)} scan(s)?\n\nThey stay in the scanner folder "
                                   "but will no longer be listed here.", parent=self):
            return
        try:
            self.archive.ignore_files([f["path"] for f in sel])
        except OSError as e:
            messagebox.showerror("Could not dismiss", str(e), parent=self)
        self.reload()
        if self.on_change:
            self.on_change(None)

    def restore_dismissed(self):
        n = self.archive.clear_ignored()
        self.reload()
        if self.on_change:
            self.on_change(None)
        messagebox.showinfo("Restored", f"{n} dismissed scan(s) are listed again.", parent=self)

    def file_selected(self):
        """File the selected scans (all together as one document). 'Save and add another' moves on
        to the next scan waiting in the list."""
        sel = self._selected()
        if not sel:
            items = self.tree.get_children()
            if not items:
                return
            sel = [self._by_iid[items[0]]]
        self._filing = True
        try:
            prefill = None
            while True:
                dlg = DocumentDialog(self, self.archive, files=[f["path"] for f in sel], prefill=prefill)
                self.wait_window(dlg)
                if not dlg.result:
                    break
                if self.on_change:
                    self.on_change(dlg.result["doc_id"])
                self.reload()
                if not dlg.result["another"]:
                    break
                prefill = dlg.result["prefill"]
                items = self.tree.get_children()
                if not items:
                    break
                sel = [self._by_iid[items[0]]]
        finally:
            self._filing = False
            self.reload()

    def _close(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
        self.destroy()
