"""selftest.py - checks that the program and everything it needs work on this PC.

Run from the built program:  OfficeArchive.exe --selftest   (writes selftest_result.txt next to the .exe)
Run from source:             .venv\\Scripts\\python app.py --selftest
It works in a temporary folder and never touches your real data.
"""
import socket
import sys
import tempfile
import urllib.request
from pathlib import Path


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check_libraries():
    import flask, jinja2, markupsafe, openpyxl, PIL, pymupdf, waitress  # noqa: F401
    import services, storage, thumbs, webserver  # noqa: F401
    return "Flask, Pillow, PyMuPDF, openpyxl, waitress import fine"


def check_tk():
    import tkinter
    root = tkinter.Tk()
    root.withdraw()
    version = root.tk.call("info", "patchlevel")
    root.destroy()
    return "Tcl/Tk " + str(version)


def check_archive(workdir):
    import pymupdf
    import services
    from PIL import Image
    src = Path(workdir) / "src"
    src.mkdir(exist_ok=True)
    png = src / "selftest.png"
    Image.new("RGB", (200, 120), "white").save(png)
    pdf = src / "selftest.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "selftest")
    doc.save(str(pdf))
    doc.close()
    arc = services.Archive(Path(workdir) / "data")
    try:
        a = arc.add_document(png, name="Self test picture", tags=["selftest"])
        b = arc.add_document(pdf, name="Self test pdf")
        assert arc.search("self test")["total"] == 2, "search"
        assert arc.thumbnail_for_document(a, 48) is not None, "picture thumbnail"
        assert arc.thumbnail_for_document(b, 48) is not None, "PDF thumbnail"
        assert arc.export_file(Path(workdir) / "x.xlsx") == 2, "Excel export"
        assert arc.export_file(Path(workdir) / "x.csv") == 2, "CSV export"
        assert arc.public_search()["total"] == 2, "public search"
    finally:
        arc.close()
    return "add, search, thumbnails, export"


def check_browser_view(workdir):
    import webserver
    port = _free_port()
    mgr = webserver.WebServer()
    mgr.start(Path(workdir) / "data", port, host="127.0.0.1")
    try:
        body = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10).read().decode()
        assert "Self test picture" in body, "page did not list the test document"
    finally:
        mgr.stop()
    return "server started, page served, stopped"


def check_data_folder():
    import storage
    folder = storage.default_data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    probe = folder / ".selftest_write"
    probe.write_text("ok")
    probe.unlink()
    return f"writable: {folder}"


def check_profile():
    import storage
    path = storage.app_dir() / "profile.json"
    assert path.is_file(), f"not found next to the program: {path}"
    return str(path)


def check_tesseract():
    import ocr
    found = ocr.find_tesseract()
    assert found, "Tesseract not found (scans cannot be read for text; set the path in Settings)"
    return str(found)


def run_checks(extra_checks=()):
    """Returns a list of (status, name, detail). status: PASS, WARN (optional item) or FAIL."""
    results = []

    def check(name, fn, optional=False):
        try:
            results.append(("PASS", name, str(fn() or "")))
        except Exception as e:
            results.append(("WARN" if optional else "FAIL", name, f"{type(e).__name__}: {e}"))

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        check("libraries", check_libraries)
        check("window toolkit", check_tk)
        check("archive", lambda: check_archive(tmp))
        check("browser view", lambda: check_browser_view(tmp))
        check("data folder", check_data_folder)
        check("profile.json", check_profile, optional=True)
        check("Tesseract", check_tesseract, optional=True)
        for name, fn in extra_checks:
            check(name, fn)
    return results


def run(out_path=None, extra_checks=()):
    """Runs the checks, writes a report, returns 0 when nothing failed."""
    import storage
    results = run_checks(extra_checks)
    lines = [f"{status}  {name}: {detail}" for status, name, detail in results]
    failed = [r for r in results if r[0] == "FAIL"]
    lines += ["", "SELF-TEST PASSED" if not failed else f"SELF-TEST FAILED ({len(failed)} problem(s))"]
    text = "\n".join(lines) + "\n"
    out = Path(out_path) if out_path else storage.app_dir() / "selftest_result.txt"
    try:
        out.write_text(text, encoding="utf-8")
    except OSError:
        pass
    if sys.stdout:
        print(text)
    return 1 if failed else 0
