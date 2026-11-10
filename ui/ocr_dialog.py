"""ui/ocr_dialog.py - read the text inside scans in the background so searches can find it."""
import queue
import threading
import tkinter as tk
from tkinter import ttk

from services import Archive
from ui.common import ModalWindow


class OcrDialog(ModalWindow):
    """Shows how many scans still need reading and runs the reading with a progress bar.
    The work runs on its own Archive object (its own database connection) in a background thread."""

    def __init__(self, parent, archive):
        super().__init__(parent, "Index scans", "580x340")
        self.archive = archive
        self.changed = False
        self.finished = True            # True while nothing is running
        self._q = queue.Queue()
        self._cancel = threading.Event()
        self._failed_before = 0
        self.resizable(False, False)
        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        self.status = ttk.Label(body, text="", wraplength=540, justify="left")
        self.status.pack(anchor="w")
        self.retry_var = tk.BooleanVar(value=False)
        self.retry_chk = ttk.Checkbutton(body, text="Also try again the files that failed before",
                                         variable=self.retry_var, command=self._update_start)
        self.retry_chk.pack(anchor="w", pady=(8, 0))
        self.bar = ttk.Progressbar(body, mode="determinate", length=540)
        self.bar.pack(fill="x", pady=(12, 4))
        self.detail = ttk.Label(body, text="", foreground="#666", wraplength=540, justify="left")
        self.detail.pack(anchor="w")
        self.result = ttk.Label(body, text="", wraplength=540, justify="left")
        self.result.pack(anchor="w", pady=(8, 0))
        row = ttk.Frame(body)
        row.pack(fill="x", side="bottom", pady=(10, 0))
        self.close_btn = ttk.Button(row, text="Close", command=self._on_close)
        self.close_btn.pack(side="right")
        self.start_btn = ttk.Button(row, text="Start", command=self.start)
        self.start_btn.pack(side="right", padx=6)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda e: self._on_close())
        self._show_info()

    # ------------------------------------------------------------ state
    def _show_info(self):
        st = self.archive.ocr_status()
        self._failed_before = st["failed"]
        self._available = st["available"]
        self._pending = st["pending"]
        if not st["available"]:
            self.status.configure(text=st["message"] + "\n\nSet the Tesseract path in File > Settings.")
        elif st["pending"] == 0:
            self.status.configure(text=f"All scans are up to date. {st['done']} file(s) have readable text, "
                                       f"{st['empty']} had no text, {st['failed']} failed earlier.")
        else:
            self.status.configure(text=(
                f"{st['pending']} scan file(s) are waiting to be read. This can take a few seconds per page.\n"
                f"You can stop at any time; files already read stay searchable.\n"
                f"Already read: {st['done']}. Without text: {st['empty']}. Failed earlier: {st['failed']}."))
        self.retry_chk.configure(state="normal" if st["failed"] else "disabled")
        self._update_start()

    def _update_start(self):
        ready = self._available and (self._pending > 0 or (self.retry_var.get() and self._failed_before > 0))
        self.start_btn.configure(state="normal" if ready and self.finished else "disabled")

    # ------------------------------------------------------------ running
    def start(self):
        if not self.finished:
            return
        self.finished = False
        self._cancel.clear()
        self.result.configure(text="")
        self.start_btn.configure(state="disabled")
        self.retry_chk.configure(state="disabled")
        self.close_btn.configure(text="Stop")
        self.bar.configure(value=0, maximum=1)
        self.detail.configure(text="Starting...")
        retry = self.retry_var.get()
        data_dir = self.archive.data_dir

        def work():
            arc = None
            try:
                arc = Archive(data_dir)
                rep = arc.ocr_run(cancel=self._cancel.is_set, retry_failed=retry,
                                  progress=lambda i, n, name: self._q.put(("progress", i, n, name)))
                self._q.put(("done", rep))
            except Exception as e:
                self._q.put(("error", str(e)))
            finally:
                if arc is not None:
                    try:
                        arc.close()
                    except Exception:
                        pass
        threading.Thread(target=work, daemon=True).start()
        self.after(150, self._poll)

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
            self.bar.configure(maximum=max(n, 1))
            self.bar["value"] = i
            self.detail.configure(text=f"{i} of {n} files   {name}")
        if not self.finished:
            self.after(150, self._poll)

    def _finish(self, msg):
        self.finished = True
        self.close_btn.configure(text="Close", state="normal")
        if msg[0] == "error":
            self.title("Indexing failed")
            self.result.configure(text=f"It could not finish:\n{msg[1]}", foreground="#b00020")
            self.detail.configure(text="")
        else:
            rep = msg[1]
            if not rep["cancelled"]:
                self.bar["value"] = self.bar["maximum"]
            if rep["done"]:
                self.changed = True
            self.title("Indexing stopped" if rep["cancelled"] else "Indexing finished")
            lines = [f"{rep['done']} file(s) read, {rep['empty']} had no text, {len(rep['failed'])} failed."]
            for f in rep["failed"][:3]:
                lines.append(f" - {f['name']}: {f['error']}")
            if len(rep["failed"]) > 3:
                lines.append(f" ...and {len(rep['failed']) - 3} more.")
            self.result.configure(text="\n".join(lines),
                                  foreground="#b00020" if rep["failed"] else "#1b7f2a")
            self.detail.configure(text="")
        self.retry_var.set(False)
        self._show_info()

    def _on_close(self):
        if self.finished:
            self.destroy()
        else:
            self._cancel.set()
            self.close_btn.configure(state="disabled")
            self.detail.configure(text="Stopping after the current file...")
