import argparse
import json
import mimetypes
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .data import load_observations, probe
from .events import number, summary
from .export import render_export
from .store import Store

ROOT = Path(__file__).resolve().parent.parent


def make_server(context, port=8876):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
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
            path = urlparse(self.path).path
            if path == "/api/project":
                self.json(dict(name="Persibo vs Gresik United", clip="Gol 1 · Sehabudin",
                               sourceOffset=5910, **context["meta"],
                               observations=context["observations"],
                               events=context["store"].list(),
                               stats=summary(context["store"].list())))
            elif path == "/api/events":
                events = context["store"].list()
                self.json(dict(events=events, stats=summary(events)))
            elif path.startswith("/api/jobs/"):
                with lock:
                    job = dict(context["jobs"].get(path.rsplit("/", 1)[-1], {}))
                self.json(job or {"error": "Ekspor tidak ditemukan."}, 200 if job else 404)
            elif path == "/media":
                self.file(context["media"])
            elif re.fullmatch(r"/exports/[a-f0-9-]{36}\.mp4", path):
                self.file(context["root"] / path.lstrip("/"))
            elif path in {"/", "/app.js", "/styles.css"}:
                self.file(context["root"] / "web" / ("index.html" if path == "/" else path[1:]))
            else:
                self.send_error(404)

        def body(self):
            origin = self.headers.get("Origin")
            host = self.headers.get("Host")
            if host not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
                raise ValueError("Host tidak diizinkan.")
            if origin and origin not in {f"http://{host}"}:
                raise ValueError("Origin tidak diizinkan.")
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16384:
                raise ValueError("Ukuran permintaan tidak valid.")
            item = json.loads(self.rfile.read(size))
            if not isinstance(item, dict):
                raise ValueError("Permintaan harus berupa objek.")
            return item

        def do_POST(self):
            try:
                item = self.body()
                path = urlparse(self.path).path
                if path == "/api/events":
                    self.json(context["store"].save(item), 201)
                elif path == "/api/events/delete":
                    context["store"].delete(str(item.get("id", "")))
                    self.json({"ok": True})
                elif path == "/api/export":
                    start, end = number(item.get("start")), number(item.get("end"))
                    if not 0 <= start < end <= context["meta"]["duration"]:
                        raise ValueError("Rentang ekspor tidak valid.")
                    events = context["store"].list()
                    with lock:
                        if any(job["state"] == "running" for job in context["jobs"].values()):
                            self.json({"error": "Ekspor sebelumnya masih berjalan."}, 409)
                            return
                        identifier = str(uuid.uuid4())
                        context["jobs"][identifier] = dict(id=identifier, state="running", progress=0)
                    def update(value):
                        with lock:
                            context["jobs"][identifier]["progress"] = value
                    def worker():
                        try:
                            dest = context["root"] / "exports" / f"{identifier}.mp4"
                            render_export(context["media"], dest, events, start, end, update)
                            with lock:
                                context["jobs"][identifier].update(state="done", url=f"/exports/{identifier}.mp4")
                        except Exception as error:
                            with lock:
                                context["jobs"][identifier].update(state="error", error=str(error))
                    threading.Thread(target=worker, daemon=True).start()
                    self.json({"id": identifier}, 202)
                else:
                    self.send_error(404)
            except (ValueError, TypeError, KeyError) as error:
                self.json({"error": str(error)}, 400)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8876)
    args = parser.parse_args()
    media = Path.home() / "Downloads/Gol_1_Persibo_Sehabudin.mp4"
    csv = Path.home() / "Downloads/tracking_Gol_1_Persibo_Sehabudin.csv"
    meta = probe(media)
    context = dict(root=ROOT, media=media, meta=meta, jobs={},
                   observations=load_observations(csv, meta["width"], meta["height"], meta["fps"]),
                   store=Store(ROOT / "data/project.sqlite", meta["duration"]))
    server = make_server(context, args.port)
    print(f"Touchline siap: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
