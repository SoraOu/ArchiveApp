"""app.py - starts the Office Document Archive.   Run:  python app.py"""
import logging
import sys
import tkinter as tk
import traceback
from tkinter import messagebox, ttk

import services
import storage
from ui.main_window import MainWindow


def main():
    data_dir = storage.default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(data_dir / "app.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("archive")
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)       # sharp text on high-DPI screens
        except Exception:
            pass

    root = tk.Tk()
    try:
        ttk.Style(root).theme_use("vista" if sys.platform.startswith("win") else "clam")
    except tk.TclError:
        pass

    def on_error(exc, val, tb):
        log.error("Unhandled error\n%s", "".join(traceback.format_exception(exc, val, tb)))
        messagebox.showerror("Something went wrong", f"{val}\n\nDetails were saved to app.log in the data folder.")
    root.report_callback_exception = on_error

    try:
        archive = services.Archive(data_dir)
        summary = archive.ensure_seeded()
        if summary:
            log.info("Loaded starter document types: %s", summary)
    except Exception as e:
        log.exception("startup failed")
        messagebox.showerror("Cannot open the archive",
                             f"The archive database could not be opened.\n\n{e}\n\nData folder: {data_dir}")
        return

    MainWindow(root, archive)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    archive.close()


if __name__ == "__main__":
    main()
