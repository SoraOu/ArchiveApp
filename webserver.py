"""webserver.py - read-only browser view of the archive (Phase 5).

Anyone on the office network can search the archive and open documents that are NOT marked
confidential. Nothing can be changed from the browser: every request except GET/HEAD is refused,
the database connection is read-only, and every page goes through the Archive.public_* methods,
which never return confidential or deleted documents. Never expose this to the internet.

Use:  webserver.autostart(data_dir, archive)      (called by app.py)
      webserver.manager.start(data_dir, port)     (called by the Browser view dialog)
"""
import base64
import logging
import math
import mimetypes
import socket
import threading
from urllib.parse import urlencode

from flask import Flask, Response, abort, render_template_string, request, send_file, url_for
from markupsafe import Markup

import services

log = logging.getLogger("archive")

PAGE_SIZE = 50
SORTS = {"added_desc": "Newest added", "added_asc": "Oldest added", "name": "Name", "date_desc": "Document date"}
# Shown inside the browser; everything else is offered as a download so a stored .html/.svg file can never run.
INLINE_TYPES = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
# 1x1 transparent PNG: sent for every document that has no thumbnail (and for hidden ones, so nothing is revealed)
PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
CSP = ("default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; form-action 'self'; "
       "base-uri 'none'; frame-ancestors 'none'")

LAYOUT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<style>
 body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f5f6f8;color:#222}
 header{background:#1f4e79;color:#fff;padding:10px 16px}
 header a{color:#fff;text-decoration:none;font-weight:600;font-size:1.1em}
 main{max-width:1100px;margin:0 auto;padding:14px}
 a{color:#1f4e79}
 form.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}
 form.bar input[type=search]{flex:1 1 260px;padding:8px;font-size:1em}
 form.bar select,form.bar button{padding:8px;font-size:1em}
 .chip{display:inline-block;padding:2px 8px;margin:2px 4px 2px 0;border:1px solid #b7c4d3;border-radius:12px;
       background:#fff;text-decoration:none;font-size:.9em}
 .chip.on{background:#1f4e79;color:#fff;border-color:#1f4e79}
 details{margin:6px 0 12px}
 table.list{width:100%;border-collapse:collapse;background:#fff}
 table.list th,table.list td{padding:6px 8px;border-bottom:1px solid #e3e6ea;text-align:left;vertical-align:middle}
 table.list th{background:#eef1f5;font-size:.9em}
 .thumb{width:64px;height:64px;object-fit:contain;background:#eee;display:block}
 .muted{color:#666;font-size:.9em}
 .pager{margin:12px 0;display:flex;gap:16px;align-items:center}
 dl.facts{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;background:#fff;padding:12px;margin:0 0 12px}
 dl.facts dt{font-weight:600} dl.facts dd{margin:0}
 .notes{white-space:pre-wrap}
 ul.files{background:#fff;padding:10px 10px 10px 28px;margin:0}
 @media (max-width:700px){.hide-small{display:none}}
</style></head><body>
<header><a href="/">Office Document Archive</a> <span class="muted" style="color:#cfe0f1">read-only view</span></header>
<main>{{ body }}</main></body></html>"""

INDEX = """
<form class="bar" method="get" action="/">
 <input type="search" name="q" value="{{ q }}" placeholder="Search names, tags, or text inside scans" autofocus>
 <select name="type"><option value="">All types</option>
  {% for t in types %}<option value="{{ t.id }}"{% if t.id == type_id %} selected{% endif %}>{{ t.name }} ({{ t.doc_count }})</option>{% endfor %}
 </select>
 <select name="sort">{% for k, label in sorts %}<option value="{{ k }}"{% if k == sort %} selected{% endif %}>{{ label }}</option>{% endfor %}</select>
 {% for tg in tags %}<input type="hidden" name="tag" value="{{ tg }}">{% endfor %}
 <button type="submit">Search</button>
 {% if q or type_id or tags %}<a href="{{ url_for('index') }}">Clear</a>{% endif %}
</form>
{% if tag_links %}<details {% if tags %}open{% endif %}><summary>Filter by tag</summary>
 {% for t in tag_links %}<a class="chip{% if t.on %} on{% endif %}" href="{{ t.href }}">{{ t.name }} ({{ t.count }})</a>{% endfor %}
</details>{% endif %}
<p class="muted">Showing {{ first }}-{{ last }} of {{ total }}</p>
{% if results %}
<table class="list"><tr><th></th><th>Name</th><th class="hide-small">Type</th><th class="hide-small">Reference</th>
 <th class="hide-small">Doc date</th><th class="hide-small">Tags</th></tr>
{% for r in results %}<tr>
 <td><a href="{{ url_for('document', doc_id=r.id) }}"><img class="thumb" alt="" loading="lazy" src="{{ url_for('thumb', doc_id=r.id) }}"></a></td>
 <td><a href="{{ url_for('document', doc_id=r.id) }}">{{ r.name }}</a>{% if r.file_count > 1 %} <span class="muted">({{ r.file_count }} files)</span>{% endif %}</td>
 <td class="hide-small">{{ r.type_name or '' }}</td><td class="hide-small">{{ r.ref }}</td>
 <td class="hide-small">{{ r.doc_date or '' }}</td><td class="hide-small">{{ r.tags|join(', ') }}</td></tr>{% endfor %}
</table>
<div class="pager">
 {% if prev_href %}<a href="{{ prev_href }}">&larr; Previous</a>{% endif %}
 <span class="muted">Page {{ page }} of {{ pages }}</span>
 {% if next_href %}<a href="{{ next_href }}">Next &rarr;</a>{% endif %}
</div>
{% else %}<p>No documents found.</p>{% endif %}
"""

DOCUMENT = """
<p><a href="{{ url_for('index') }}">&larr; Back to search</a></p>
<h2>{{ d.name }}</h2>
<dl class="facts">
 <dt>Type</dt><dd>{{ d.type_name or '-' }}</dd>
 {% if d.doc_date %}<dt>Document date</dt><dd>{{ d.doc_date }}</dd>{% endif %}
 {% for f in d.fields %}<dt>{{ f.label }}</dt><dd>{{ f.value }}</dd>{% endfor %}
 <dt>Tags</dt><dd>{% for t in d.tags %}<a class="chip" href="{{ url_for('index', tag=t) }}">{{ t }}</a>{% else %}-{% endfor %}</dd>
 <dt>Added</dt><dd>{{ d.date_added }}</dd>
 {% if d.notes %}<dt>Notes</dt><dd class="notes">{{ d.notes }}</dd>{% endif %}
</dl>
<h3>Files</h3>
<ul class="files">
{% for f in d.files %}<li>{{ f.name }} <span class="muted">({{ f.size_bytes|filesize }})</span>
 {% if f.exists %}
  {% if f.can_view %}<a href="{{ url_for('document_file', doc_id=d.id, file_id=f.id) }}">View</a> | {% endif %}
  <a href="{{ url_for('document_file', doc_id=d.id, file_id=f.id, download=1) }}">Download</a>
 {% else %}<span class="muted">file not found on the archive PC</span>{% endif %}</li>
{% endfor %}
</ul>
"""


def _filesize(n):
    n = float(n or 0)
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{int(n)} bytes" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024


def create_app(data_dir):
    app = Flask(__name__)
    app.jinja_env.filters["filesize"] = _filesize
    local = threading.local()

    def archive():
        """One read-only Archive (own database connection) per server thread."""
        arc = getattr(local, "arc", None)
        if arc is None:
            arc = local.arc = services.Archive(data_dir, read_only=True)
        return arc

    def page(title, template, **ctx):
        body = Markup(render_template_string(template, **ctx))
        return render_template_string(LAYOUT, title=title, body=body)

    @app.before_request
    def read_only_guard():
        if request.method not in ("GET", "HEAD"):
            abort(405)

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if resp.mimetype == "text/html":
            resp.headers["Content-Security-Policy"] = CSP
        return resp

    @app.get("/")
    def index():
        arc = archive()
        q = request.args.get("q", "").strip()[:200]
        tags = [t.strip() for t in request.args.getlist("tag") if t.strip()][:10]
        sort = request.args.get("sort")
        sort = sort if sort in SORTS else "added_desc"
        type_id = request.args.get("type", type=int)
        pg = max(request.args.get("page", 1, type=int), 1)
        res = arc.public_search(query=q, type_id=type_id, tags=tags, sort=sort,
                                limit=PAGE_SIZE, offset=(pg - 1) * PAGE_SIZE)
        total = res["total"]
        pages = max(math.ceil(total / PAGE_SIZE), 1)

        def link(**over):
            params = {"q": q, "type": type_id, "sort": sort, "tag": tags, "page": None}
            params.update(over)
            return url_for("index", **{k: v for k, v in params.items() if v not in (None, "", [])})

        chosen = {t.casefold() for t in tags}
        tag_links = []
        for t in arc.public_tags():
            on = t["name"].casefold() in chosen
            new = [x for x in tags if x.casefold() != t["name"].casefold()] if on else tags + [t["name"]]
            tag_links.append({"name": t["name"], "count": t["count"], "on": on, "href": link(tag=new)})
        first = (pg - 1) * PAGE_SIZE + 1 if res["results"] else 0
        return page("Office Document Archive", INDEX, q=q, tags=tags, sort=sort, sorts=list(SORTS.items()),
                    type_id=type_id, types=arc.public_types(), tag_links=tag_links, results=res["results"],
                    total=total, first=first, last=first + len(res["results"]) - 1 if first else 0,
                    page=pg, pages=pages,
                    prev_href=link(page=pg - 1) if pg > 1 else None,
                    next_href=link(page=pg + 1) if pg < pages else None)

    @app.get("/doc/<int:doc_id>")
    def document(doc_id):
        d = archive().public_document(doc_id)
        if d is None:
            abort(404)
        for f in d["files"]:
            f["can_view"] = _ext(f["name"]) in INLINE_TYPES
        return page(d["name"], DOCUMENT, d=d)

    @app.get("/doc/<int:doc_id>/file/<int:file_id>")
    def document_file(doc_id, file_id):
        info = archive().public_file(doc_id, file_id)
        if info is None:
            abort(404)
        path = info["path"]
        ext = path.suffix.lower()
        inline = ext in INLINE_TYPES and not request.args.get("download")
        mime = INLINE_TYPES.get(ext) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return send_file(str(path), mimetype=mime, as_attachment=not inline,
                         download_name=info["name"] or path.name, conditional=True)

    @app.get("/thumb/<int:doc_id>")
    def thumb(doc_id):
        path = archive().public_thumbnail(doc_id)
        if path is None:
            return Response(PLACEHOLDER_PNG, mimetype="image/png", headers={"Cache-Control": "no-cache"})
        return send_file(str(path), mimetype="image/png", max_age=3600)

    return app


def _ext(name):
    name = str(name or "")
    return name[name.rfind("."):].lower() if "." in name else ""


# ---------------------------------------------------------------- running the server
def _check_port_free(host, port):
    """Plain bind test. (waitress sets SO_REUSEADDR, which on Windows would let a second server
    share a port that is already in use, so a busy port must be caught here.)"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))


def lan_addresses():
    """This PC's IPv4 addresses on the office network (for 'open this address on another PC')."""
    found = []
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith(("127.", "169.254.")) and ip not in found:
                found.append(ip)
    except OSError:
        pass
    return found


class WebServer:
    def __init__(self):
        self.server = None
        self.thread = None
        self.port = None

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, data_dir, port, host="0.0.0.0"):
        """Start serving in a background thread. Raises OSError if the port is already in use."""
        if self.running:
            return
        from waitress import create_server
        port = int(port)
        _check_port_free(host, port)
        server = create_server(create_app(data_dir), host=host, port=port, threads=4, ident="archive")
        thread = threading.Thread(target=server.run, name="archive-web", daemon=True)
        thread.start()
        self.server, self.thread, self.port = server, thread, port
        log.info("Browser view started on %s:%s", host, port)

    def stop(self):
        if self.server is not None:
            try:
                self.server.close()
            except Exception:
                log.exception("closing the browser view failed")
        if self.thread is not None:
            self.thread.join(timeout=3)
        if not self.running:
            self.server = self.thread = self.port = None

    def urls(self):
        if not self.running:
            return []
        return [f"http://{ip}:{self.port}/" for ip in lan_addresses()] or [f"http://localhost:{self.port}/"]


manager = WebServer()


def autostart(data_dir, archive, host="0.0.0.0"):
    """Start the browser view at app start-up when it is switched on. Never raises.
    Returns (running, message)."""
    cfg = archive.web_settings()
    if not cfg["enabled"]:
        return False, "Browser view is off."
    try:
        manager.start(data_dir, cfg["port"], host=host)
    except OSError as e:
        log.warning("Browser view could not start: %s", e)
        return False, f"Browser view could not start: port {cfg['port']} may already be in use. ({e})"
    except Exception as e:
        log.exception("Browser view could not start")
        return False, f"Browser view could not start: {e}"
    return True, "Browser view running at " + " or ".join(manager.urls())
