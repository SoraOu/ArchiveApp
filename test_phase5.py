r"""test_phase5.py - checks the read-only browser view (Phase 5).
Uses a temporary folder, so it never touches your real data. Needs: flask, waitress.

Run:  .venv\Scripts\python test_phase5.py
"""
import socket
import sqlite3
import sys
import tempfile
import traceback
import urllib.request
from pathlib import Path

from PIL import Image

import webserver
from services import Archive, ArchiveError

TMP = tempfile.TemporaryDirectory()
ROOT = Path(TMP.name)
SRC = ROOT / "src"
SRC.mkdir()
DATA = ROOT / "data"
arc = Archive(DATA)
S = {}


def mkfile(name, content=None):
    p = SRC / name
    p.write_bytes(content or name.encode())
    return p


def mkpng(name, color, size=(300, 200)):
    p = SRC / name
    Image.new("RGB", size, color).save(p)
    return p


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


def setup_docs():
    t = arc.create_type("Resolution", [{"label": "Ref No.", "data_type": "id", "is_key": True},
                                       {"label": "Amount", "data_type": "number"}])
    S["t"] = t
    S["open"] = arc.add_document(mkpng("open.png", "red"), name="Open budget", type_id=t,
                                 details={"Ref No.": "R-1", "Amount": 1500}, tags=["Budget", "Public"],
                                 notes="Approved <b>2025</b>", doc_date="2025-03-01")
    S["pdf"] = arc.add_document(mkfile("memo.docx"), name="Plain memo", tags=["Public"])
    S["secret"] = arc.add_document(mkpng("secret.png", "blue"), name="Secret salaries", type_id=t,
                                   tags=["Payroll"], confidential=True)
    S["gone"] = arc.add_document(mkfile("gone.docx"), name="Deleted memo", tags=["Trash"])
    arc.delete_document(S["gone"])


# ---------------------------------------------------------------- services: public views
def t_read_only_archive():
    setup_docs()
    ro = Archive(DATA, read_only=True)
    try:
        assert ro.search("open")["total"] == 1                               # reading works
        assert raises(sqlite3.OperationalError, ro.set_setting, "x", "y")    # writing is refused by SQLite itself
        assert raises(sqlite3.OperationalError, ro.delete_document, S["open"])
    finally:
        ro.close()
    assert arc.get_document(S["open"]) is not None and not arc.get_document(S["open"])["is_deleted"]


def t_public_search():
    assert [r["name"] for r in arc.public_search()["results"]] == ["Plain memo", "Open budget"]
    assert arc.public_search()["total"] == 2
    assert arc.public_search("secret")["total"] == 0 and arc.public_search("salaries")["total"] == 0
    assert arc.public_search("deleted")["total"] == 0
    assert arc.public_search(tags=["Payroll"])["total"] == 0
    assert arc.public_search(type_id=S["t"])["total"] == 1                   # the confidential one is hidden
    assert arc.public_search(tags=["Budget"])["total"] == 1
    assert all("is_confidential" not in r for r in arc.public_search()["results"])
    assert len(arc.public_search(limit=1, offset=1)["results"]) == 1
    assert raises(TypeError, arc.public_search, include_confidential=True)   # cannot be switched off


def t_public_lists():
    assert [(t["name"], t["doc_count"]) for t in arc.public_types()] == [("Resolution", 1)]
    names = [t["name"] for t in arc.public_tags()]
    assert names == ["Budget", "Public"] and "Payroll" not in names and "Trash" not in names, names
    assert {t["name"]: t["count"] for t in arc.public_tags()} == {"Budget": 1, "Public": 2}


def t_public_document():
    d = arc.public_document(S["open"])
    assert d["name"] == "Open budget" and d["type_name"] == "Resolution" and d["doc_date"] == "2025-03-01", d
    assert d["tags"] == ["Budget", "Public"] and "<b>2025</b>" in d["notes"]
    assert {"label": "Ref No.", "value": "R-1"} in d["fields"], d["fields"]
    assert len(d["files"]) == 1 and d["files"][0]["name"] == "open.png" and d["files"][0]["exists"]
    text = repr(d)
    assert str(DATA) not in text and "abs_path" not in text, text           # no server paths leave the server
    assert arc.public_document(S["secret"]) is None
    assert arc.public_document(S["gone"]) is None
    assert arc.public_document(999999) is None


def t_public_file():
    fid = arc.public_document(S["open"])["files"][0]["id"]
    f = arc.public_file(S["open"], fid)
    assert f["name"] == "open.png" and Path(f["path"]).is_file()
    assert arc.public_file(S["pdf"], fid) is None                            # a file id from another document
    secret_fid = arc.get_document(S["secret"])["files"][0]["id"]
    assert arc.public_file(S["secret"], secret_fid) is None
    assert arc.public_file(S["gone"], arc.get_document(S["gone"])["files"][0]["id"]) is None
    assert arc.public_file(S["open"], 999999) is None


def t_public_thumbnail():
    p = arc.public_thumbnail(S["open"], 64)
    assert p is not None and p.is_file()
    assert arc.public_thumbnail(S["secret"], 64) is None                     # never made for confidential documents
    assert arc.public_thumbnail(S["pdf"], 64) is None                        # .docx: no picture
    secret_hash = arc.get_document(S["secret"])["files"][0]["hash"]
    assert not list((DATA / "thumbs").rglob(secret_hash + "*"))


def t_web_settings():
    assert arc.web_settings() == {"enabled": False, "port": 8080}
    arc.set_web_settings(True, "8123")
    assert arc.web_settings() == {"enabled": True, "port": 8123}
    assert raises(ArchiveError, arc.set_web_settings, True, "80")
    assert raises(ArchiveError, arc.set_web_settings, True, "70000")
    assert raises(ArchiveError, arc.set_web_settings, True, "abc")
    assert arc.web_settings()["port"] == 8123                                # bad input changed nothing
    arc.set_web_settings(False, 8080)
    assert any(r["action"] == "web_settings" for r in arc.get_audit_log(50))


# ---------------------------------------------------------------- web routes
def client():
    return webserver.create_app(DATA).test_client()


def t_route_index():
    c = client()
    r = c.get("/")
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "Open budget" in html and "Plain memo" in html
    assert "Secret salaries" not in html and "Deleted memo" not in html and "Payroll" not in html
    assert "/thumb/%d" % S["open"] in html and "/doc/%d" % S["open"] in html
    assert "Showing 1-2 of 2" in html, html
    html = c.get("/?q=budget").get_data(as_text=True)
    assert "Open budget" in html and "Plain memo" not in html
    assert "Secret salaries" not in c.get("/?q=salaries").get_data(as_text=True)
    html = c.get("/?tag=Budget&type=%d&sort=name" % S["t"]).get_data(as_text=True)
    assert "Open budget" in html and "Plain memo" not in html
    assert c.get("/?page=abc&type=x&sort=evil").status_code == 200           # junk input is ignored, not an error
    assert c.get("/?page=999").status_code == 200


def t_route_escaping():
    d = arc.add_document(mkfile("x.docx"), name="<script>alert(1)</script>", tags=["<i>t</i>"])
    c = client()
    for url in ("/", "/doc/%d" % d, "/?q=%3Cscript%3E"):
        html = c.get(url).get_data(as_text=True)
        assert "<script>alert(1)</script>" not in html and "<i>t</i>" not in html, url
    assert "&lt;script&gt;" in c.get("/doc/%d" % d).get_data(as_text=True)
    arc.delete_document(d)


def t_route_document():
    c = client()
    r = c.get("/doc/%d" % S["open"])
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "Open budget" in html and "Ref No." in html and "R-1" in html
    assert "&lt;b&gt;2025&lt;/b&gt;" in html and "<b>2025</b>" not in html   # notes are escaped
    assert "/doc/%d/file/" % S["open"] in html
    assert str(DATA) not in html
    assert c.get("/doc/%d" % S["secret"]).status_code == 404
    assert c.get("/doc/%d" % S["gone"]).status_code == 404
    assert c.get("/doc/999999").status_code == 404


def t_route_file_and_thumb():
    c = client()
    fid = arc.public_document(S["open"])["files"][0]["id"]
    r = c.get("/doc/%d/file/%d" % (S["open"], fid))
    assert r.status_code == 200 and r.mimetype == "image/png" and r.data[:4] == b"\x89PNG", r.mimetype
    assert "attachment" not in r.headers.get("Content-Disposition", "")
    r = c.get("/doc/%d/file/%d?download=1" % (S["open"], fid))
    assert "attachment" in r.headers["Content-Disposition"]
    memo_fid = arc.public_document(S["pdf"])["files"][0]["id"]
    r = c.get("/doc/%d/file/%d" % (S["pdf"], memo_fid))                      # .docx is always a download
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"]
    assert c.get("/doc/%d/file/%d" % (S["pdf"], fid)).status_code == 404
    secret_fid = arc.get_document(S["secret"])["files"][0]["id"]
    assert c.get("/doc/%d/file/%d" % (S["secret"], secret_fid)).status_code == 404
    t = c.get("/thumb/%d" % S["open"])
    assert t.status_code == 200 and t.mimetype == "image/png" and len(t.data) > len(webserver.PLACEHOLDER_PNG)
    for doc in (S["secret"], S["pdf"], S["gone"], 999999):                   # same placeholder, nothing revealed
        t = c.get("/thumb/%d" % doc)
        assert t.status_code == 200 and t.data == webserver.PLACEHOLDER_PNG, doc


def t_route_read_only():
    c = client()
    before = arc.conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    for method in ("post", "put", "delete", "patch"):
        for url in ("/", "/doc/%d" % S["open"], "/doc/%d/delete" % S["open"], "/anything"):
            assert getattr(c, method)(url).status_code == 405, (method, url)
    assert arc.conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == before
    assert c.get("/nope").status_code == 404
    assert c.get("/doc/%d/file/1/../../../../app.py" % S["open"]).status_code == 404


def t_route_headers():
    c = client()
    r = c.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    r = c.get("/thumb/%d" % S["open"])
    assert r.headers["X-Content-Type-Options"] == "nosniff"


# ---------------------------------------------------------------- real server
def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def t_real_server():
    mgr = webserver.WebServer()
    port = free_port()
    assert not mgr.running
    mgr.start(DATA, port, host="127.0.0.1")
    try:
        assert mgr.running and mgr.port == port
        body = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).read().decode()
        assert "Open budget" in body and "Secret salaries" not in body
        req = urllib.request.Request(f"http://127.0.0.1:{port}/", data=b"x=1", method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "POST should be refused"
        except urllib.error.HTTPError as e:
            assert e.code == 405
        mgr.start(DATA, port, host="127.0.0.1")                              # starting twice is harmless
        busy = webserver.WebServer()
        assert raises(OSError, busy.start, DATA, port, host="127.0.0.1")     # port in use: clear error, no crash
        assert not busy.running
    finally:
        mgr.stop()
    assert not mgr.running


def t_autostart():
    msg_off = webserver.autostart(DATA, arc)
    assert msg_off[0] is False and not webserver.manager.running             # off by default
    port = free_port()
    arc.set_web_settings(True, port)
    try:
        running, msg = webserver.autostart(DATA, arc, host="127.0.0.1")
        assert running and webserver.manager.running and str(port) in msg, msg
    finally:
        webserver.manager.stop()
        arc.set_web_settings(False, 8080)
    # a busy port must not stop the app from starting
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        arc.set_web_settings(True, blocker.getsockname()[1])
        running, msg = webserver.autostart(DATA, arc, host="127.0.0.1")
        assert running is False and "port" in msg.lower(), msg
    arc.set_web_settings(False, 8080)


def t_lan_addresses():
    ips = webserver.lan_addresses()
    assert isinstance(ips, list) and all(not ip.startswith(("127.", "169.254.")) for ip in ips), ips


def t_integrity_after():
    rep = arc.check_integrity(verify_hashes=True)
    assert rep["database_ok"] and rep["orphan_files"] == [], rep


TESTS = [t_read_only_archive, t_public_search, t_public_lists, t_public_document, t_public_file,
         t_public_thumbnail, t_web_settings, t_route_index, t_route_escaping, t_route_document,
         t_route_file_and_thumb, t_route_read_only, t_route_headers, t_real_server, t_autostart,
         t_lan_addresses, t_integrity_after]

if __name__ == "__main__":
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS  {fn.__name__[2:]}")
        except Exception:
            failed += 1
            print(f"FAIL  {fn.__name__[2:]}")
            traceback.print_exc()
    print()
    print("ALL TESTS PASSED" if not failed else f"{failed} TEST(S) FAILED")
    try:
        arc.close()
        TMP.cleanup()
    except Exception:
        pass
    sys.exit(1 if failed else 0)
