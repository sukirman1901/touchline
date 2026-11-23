import argparse
import hashlib
import json
import mimetypes
import re
import signal
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

from .data import load_observations, probe
from .events import number, summary
from .export import render_export
from .store import Store
from .projects import Projects, MAX_UPLOAD

ROOT = Path(__file__).resolve().parent.parent


def make_server(context, port=8876):
    lock = threading.Lock()
    analysis_cache = {}
    projects = Projects(context["root"])

    def analysis(selected):
        path = selected["root"] / "data/automatic.json"
        status_path = path.with_suffix(".status.json")
        job = json.loads(status_path.read_text()) if status_path.exists() else {}
        if job.get("identity") not in {None, selected.get("identity")}:
            job = {}
        if not path.exists():
            return dict(status="pending", events=[], owners=[], balls=[], job=job)
        stamp = path.stat().st_mtime_ns
        cached = analysis_cache.setdefault(str(path), {"stamp": None, "value": None})
        if cached["stamp"] != stamp:
            value = json.loads(path.read_text())
            if value.get("identity") != selected.get("identity"):
                return dict(status="source-mismatch", events=[], owners=[], balls=[])
            cached.update(stamp=stamp, value=value)
        return dict(cached["value"], job=job)

    def events(selected):
        return selected["store"].merged(analysis(selected)["events"])

    class Handler(BaseHTTPRequestHandler):
        @property
        def project_id(self):
            return parse_qs(urlparse(self.path).query).get("project", ["legacy"])[0]

        def selected(self):
            if self.project_id == "legacy":
                if "media" not in context:
                    raise ValueError("Belum ada proyek. Tambahkan video dari beranda.")
                return context
            return projects.context(self.project_id)

        def json(self, payload, status=200):
            data = json.dumps(payload, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def file(self, path):
            if not path.is_file():
                self.send_error(404)
                return
            size = path.stat().st_size
            start, end, status = 0, size - 1, 200
            if "Range" in self.headers:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers["Range"])
                try:
                    if not match or not any(match.groups()):
                        raise ValueError()
                    a, b = match.groups()
                    if a:
                        start, end = int(a), min(int(b), size - 1) if b else size - 1
                    else:
                        start = max(0, size - int(b))
                    if not 0 <= start <= end < size:
                        raise ValueError()
                    status = 206
                except ValueError:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            self.send_response(status)
            self.send_header("Content-Type", mimetypes.guess_type(path)[0] or "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if self.command == "HEAD":
                return
            try:
                with path.open("rb") as handle:
                    handle.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        block = handle.read(min(262144, remaining))
                        if not block:
                            break
                        self.wfile.write(block)
                        remaining -= len(block)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            try:
                self.get_route()
            except (ValueError, KeyError) as error:
                self.json({"error": str(error)}, 400)

        def get_route(self):
            path = urlparse(self.path).path
            if path == "/api/projects":
                items = projects.list()
                if "media" in context:
                    items.append(dict(id="legacy", name="Persibo vs Gresik United",
                                      source="local", state="ready", meta=context["meta"]))
                self.json({"projects": items})
            elif re.fullmatch(r"/api/projects/[a-f0-9]{32}", path):
                self.json(projects.get(path.rsplit("/", 1)[1]))
            elif re.fullmatch(r"/preview/[a-f0-9]{32}", path):
                self.file(projects.directory(path.rsplit("/", 1)[1]) / "preview.mp4")
            elif path == "/api/project":
                selected = self.selected()
                current = events(selected)
                self.json(dict(name=selected.get("name", "Persibo vs Gresik United"),
                               clip=selected.get("clip", "Gol 1 · Sehabudin"),
                               sourceOffset=selected.get("sourceOffset", 5910), **selected["meta"],
                               observations=selected["observations"],
                               automatic=analysis(selected), events=current, stats=summary(current)))
            elif path == "/api/events":
                current = events(self.selected())
                self.json(dict(events=current, stats=summary(current)))
            elif path == "/api/analysis":
                self.json(analysis(self.selected()))
            elif path.startswith("/api/jobs/"):
                with lock:
                    job = dict(self.selected()["jobs"].get(path.rsplit("/", 1)[-1], {}))
                self.json(job or {"error": "Ekspor tidak ditemukan."}, 200 if job else 404)
            elif path == "/media":
                self.file(self.selected()["media"])
            elif re.fullmatch(r"/exports/[a-f0-9-]{36}\.mp4", path):
                self.file(self.selected()["root"] / path.lstrip("/"))
            elif path in {"/", "/workspace", "/app.js", "/dropdown.js", "/styles.css", "/icons.svg",
                          "/filmstrip.jpg", "/home.js", "/home.css"}:
                name = {"/": "home.html", "/workspace": "index.html"}.get(path, path[1:])
                self.file(context["root"] / "web" / name)
            else:
                self.send_error(404)

        def validate_origin(self):
            origin = self.headers.get("Origin")
            host = self.headers.get("Host")
            if host not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
                raise ValueError("Host tidak diizinkan.")
            if origin and origin not in {f"http://{host}"}:
                raise ValueError("Origin tidak diizinkan.")

        def body(self):
            self.validate_origin()
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16384:
                raise ValueError("Ukuran permintaan tidak valid.")
            item = json.loads(self.rfile.read(size))
            if not isinstance(item, dict):
                raise ValueError("Permintaan harus berupa objek.")
            return item

        def do_POST(self):
            try:
                path = urlparse(self.path).path
                if path == "/api/projects/upload":
                    self.validate_origin()
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= MAX_UPLOAD:
                        self.close_connection = True
                        raise ValueError("Ukuran video harus antara 1 byte dan 2 GB.")
                    name = unquote(self.headers.get("X-Filename", "Video.mp4"))
                    self.json(projects.upload(self.rfile, size, name), 202)
                    return
                item = self.body()
                if path == "/api/projects/youtube":
                    self.json(projects.youtube(item.get("url", "")), 202)
                    return
                if re.fullmatch(r"/api/projects/[a-f0-9]{32}/(analyze|retry)", path):
                    identifier, action = path.split("/")[-2:]
                    result = (projects.retry(identifier) if action == "retry" else
                              projects.start_analysis(identifier, item.get("start"), item.get("end")))
                    self.json(result, 202)
                    return
                selected = self.selected()
                project_id = self.project_id
                if path == "/api/events":
                    original = next((event for event in events(selected) if event["id"] == item.get("id")), None)
                    self.json(selected["store"].save(item, original), 201)
                elif path == "/api/events/delete":
                    selected["store"].delete(str(item.get("id", "")))
                    self.json({"ok": True})
                elif path == "/api/export":
                    start, end = number(item.get("start")), number(item.get("end"))
                    if not 0 <= start < end <= selected["meta"]["duration"]:
                        raise ValueError("Rentang ekspor tidak valid.")
                    export_events = events(selected)
                    with lock:
                        if any(job["state"] == "running" for job in selected["jobs"].values()):
                            self.json({"error": "Ekspor sebelumnya masih berjalan."}, 409)
                            return
                        identifier = str(uuid.uuid4())
                        selected["jobs"][identifier] = dict(id=identifier, state="running", progress=0)
                    def update(value):
                        with lock:
                            selected["jobs"][identifier]["progress"] = value
                    def worker():
                        try:
                            dest = selected["root"] / "exports" / f"{identifier}.mp4"
                            render_export(selected["media"], dest, export_events, start, end, update)
                            with lock:
                                selected["jobs"][identifier].update(state="done",
                                    url=f"/exports/{identifier}.mp4?project={project_id}")
                        except Exception as error:
                            with lock:
                                selected["jobs"][identifier].update(state="error", error=str(error))
                    threading.Thread(target=worker, daemon=True).start()
                    self.json({"id": identifier}, 202)
                else:
                    self.send_error(404)
            except (ValueError, TypeError, KeyError) as error:
                self.json({"error": str(error)}, 400)

    class ProjectServer(ThreadingHTTPServer):
        def server_close(self):
            projects.close()
            super().server_close()
    return ProjectServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8876)
    args = parser.parse_args()
    media = Path.home() / "Downloads/Gol_1_Persibo_Sehabudin.mp4"
    csv = Path.home() / "Downloads/tracking_Gol_1_Persibo_Sehabudin.csv"
    context = dict(root=ROOT)
    if media.exists():
        meta = probe(media)
        context.update(media=media, meta=meta, jobs={},
                       identity=hashlib.sha256(media.read_bytes()).hexdigest(),
                       observations=load_observations(csv, meta["width"], meta["height"], meta["fps"]) if csv.exists() else [],
                       store=Store(ROOT / "data/project.sqlite", meta["duration"]))
    server = make_server(context, args.port)
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    print(f"Touchline siap: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
