"""Local, isolated video projects and background intake/analysis jobs."""
import hashlib
import importlib.util
import json
import math
import os
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .data import probe
from .store import Store

MAX_UPLOAD = 2 * 1024**3
BUSY = {"importing", "downloading", "preparing", "analyzing"}


def youtube_url(value):
    url = urlparse(str(value).strip())
    if url.scheme != "https" or url.username or url.password or url.port not in (None, 443):
        raise ValueError("Gunakan link HTTPS YouTube untuk satu video.")
    if url.hostname == "youtu.be":
        identifier = url.path.strip("/")
    elif url.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        identifier = parse_qs(url.query).get("v", [""])[0] if url.path == "/watch" else (
            url.path.split("/")[-1] if url.path.startswith(("/shorts/", "/live/")) else "")
    else:
        identifier = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", identifier):
        raise ValueError("Link harus menunjuk ke satu video YouTube, bukan playlist.")
    return "https://www.youtube.com/watch?v=" + identifier


def clip_range(start, end, duration):
    start, end = float(start), float(end)
    if not all(math.isfinite(v) for v in (start, end, duration)) or not 0 <= start < end <= duration:
        raise ValueError("Rentang klip harus berada di dalam durasi video.")
    return start, end


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class Projects:
    def __init__(self, root):
        self.root = Path(root)
        self.base = self.root / "data/projects"
        self.lock = threading.RLock()
        self.contexts = {}
        self.processes = set()
        self.workers = set()
        self.closed = False
        # A new server cannot own jobs from its predecessor.
        for path in self.base.glob("*/project.json"):
            item = json.loads(path.read_text())
            if item["state"] in BUSY:
                self.update(item["id"], state="error", error="Proses terhenti saat server ditutup. Coba lagi.")

    def directory(self, identifier):
        if not re.fullmatch(r"[a-f0-9]{32}", str(identifier)):
            raise ValueError("ID proyek tidak valid.")
        return self.base / identifier

    def get(self, identifier):
        with self.lock:
            path = self.directory(identifier) / "project.json"
            if not path.exists():
                raise ValueError("Proyek tidak ditemukan.")
            item = json.loads(path.read_text())
        if item["state"] == "analyzing":
            progress = self.directory(identifier) / item.get("attempt", ".") / "data/automatic.status.json"
            if progress.exists():
                try:
                    status = json.loads(progress.read_text())
                    item["progress"] = status.get("progress", 0)
                except (ValueError, OSError):
                    pass
        return item

    def update(self, identifier, **values):
        with self.lock:
            path = self.directory(identifier) / "project.json"
            item = json.loads(path.read_text()) if path.exists() else {}
            item.update(values)
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(item, ensure_ascii=False, allow_nan=False))
            temp.replace(path)
            return item

    def list(self):
        return sorted((self.get(p.parent.name) for p in self.base.glob("*/project.json")),
                      key=lambda p: p["created"], reverse=True)

    def _create(self, name, source, **values):
        identifier = uuid.uuid4().hex
        self.directory(identifier).mkdir(parents=True)
        return self.update(identifier, id=identifier, name=str(name)[:160] or "Video baru",
                           source=source, state="importing", progress=0, created=time.time(), **values)

    def _launch(self, identifier, action):
        def run():
            try:
                action()
            except Exception as exc:
                self.update(identifier, state="error", error=str(exc)[:1000])
            finally:
                with self.lock:
                    self.workers.discard(threading.current_thread())
        with self.lock:
            if self.closed:
                raise ValueError("Server sedang berhenti.")
            worker = threading.Thread(target=run, daemon=True)
            self.workers.add(worker)
            worker.start()

    @staticmethod
    def _stop(process):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            except ProcessLookupError:
                pass

    def close(self):
        with self.lock:
            self.closed = True
            processes, workers = list(self.processes), list(self.workers)
        for process in processes:
            self._stop(process)
        for worker in workers:
            worker.join(timeout=35)

    def upload(self, stream, size, name):
        if not 0 < size <= MAX_UPLOAD:
            raise ValueError("Pilih video berukuran maksimal 2 GB.")
        item = self._create(Path(name).stem, "upload")
        directory = self.directory(item["id"])
        temp = directory / "upload.part"
        try:
            with temp.open("wb") as target:
                remaining = size
                while remaining:
                    block = stream.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError("Upload terputus. Pilih file dan unggah ulang.")
                    target.write(block)
                    remaining -= len(block)
            temp.replace(directory / "source.bin")
        except Exception:
            shutil.rmtree(directory)
            raise
        self._launch(item["id"], lambda: self._prepare(item["id"], directory / "source.bin"))
        return item

    def youtube(self, value):
        url = youtube_url(value)
        item = self._create("Video YouTube", "youtube", url=url)
        self.update(item["id"], state="downloading")
        self._launch(item["id"], lambda: self._download(item["id"]))
        return self.get(item["id"])

    def _command(self, identifier, args, timeout=7200):
        log = self.directory(identifier) / f"process-{uuid.uuid4().hex}.log"
        with log.open("w") as out:
            try:
                with self.lock:
                    if self.closed:
                        raise ValueError("Proses terhenti karena server ditutup. Coba lagi.")
                    process = subprocess.Popen(args, stdout=out, stderr=out,
                                               cwd=self.root, start_new_session=True)
                    self.processes.add(process)
                try:
                    returncode = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    self._stop(process)
                    raise
                finally:
                    with self.lock:
                        self.processes.discard(process)
            except FileNotFoundError as exc:
                raise ValueError(f"Dependensi {args[0]} belum tersedia.") from exc
            except subprocess.TimeoutExpired as exc:
                raise ValueError("Proses melewati batas waktu. Coba klip yang lebih pendek.") from exc
        if returncode:
            tail = log.read_text(errors="replace")[-700:]
            raise ValueError("Pemrosesan gagal. " + tail)

    def _download(self, identifier):
        if importlib.util.find_spec("yt_dlp"):
            downloader = [sys.executable, "-m", "yt_dlp"]
        elif shutil.which("yt-dlp"):
            downloader = ["yt-dlp"]
        else:
            raise ValueError("yt-dlp belum terpasang. Instal yt-dlp, lalu klik Coba lagi; atau upload file video.")
        directory = self.directory(identifier) / f"download-{uuid.uuid4().hex}"
        directory.mkdir()
        self._command(identifier, downloader + [
            "--ignore-config", "--no-playlist", "--no-progress",
            "--socket-timeout", "30", "--retries", "2", "--max-filesize", str(MAX_UPLOAD),
            "--write-info-json", "-f", "bv*[height<=1080]+ba/b[height<=1080]",
            "--merge-output-format", "mp4", "-o", str(directory / "source.%(ext)s"),
            "--", self.get(identifier)["url"]], timeout=3600)
        sources = [p for p in directory.glob("source.*") if p.suffix in {".mp4", ".mkv", ".webm"}]
        if len(sources) != 1:
            raise ValueError("Video YouTube tidak berhasil diunduh. Coba upload file video.")
        info = directory / "source.info.json"
        if info.exists():
            self.update(identifier, name=str(json.loads(info.read_text()).get("title", "Video YouTube"))[:160])
        self._prepare(identifier, sources[0])

    def _prepare(self, identifier, source):
        try:
            meta = probe(source)
        except FileNotFoundError as exc:
            raise ValueError("ffprobe belum tersedia. Pasang FFmpeg, lalu coba lagi.") from exc
        except (subprocess.CalledProcessError, StopIteration, KeyError, ValueError) as exc:
            raise ValueError("File tidak dapat dibaca sebagai video. Pilih file MP4, MOV, MKV, atau WebM yang valid.") from exc
        if not math.isfinite(meta["duration"]) or meta["duration"] <= 0 or meta["fps"] <= 0:
            raise ValueError("File tidak memiliki video dengan durasi yang valid.")
        self.update(identifier, state="preparing", stage="Menyiapkan preview", meta=meta,
                    source_file=source.name)
        directory = self.directory(identifier)
        temporary = directory / f"preview-{uuid.uuid4().hex}.part.mp4"
        self._command(identifier, ["ffmpeg", "-v", "error", "-y", "-i", str(source),
            "-map", "0:v:0", "-map", "0:a:0?", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23", "-threads", "2",
            "-c:a", "aac", "-movflags", "+faststart", str(temporary)])
        temporary.replace(directory / "preview.mp4")
        meta = probe(directory / "preview.mp4")
        self.update(identifier, state="preview", stage="Pilih rentang klip", meta=meta, error=None, progress=100)

    def start_analysis(self, identifier, start, end):
        with self.lock:
            item = self.get(identifier)
            if item["state"] not in {"preview", "error"} or not item.get("meta"):
                raise ValueError("Video belum siap atau analisis sudah berjalan.")
            start, end = clip_range(start, end, item["meta"]["duration"])
            if any(p["state"] == "analyzing" or (p["state"] == "preparing" and p.get("stage") == "Memotong klip")
                   for p in self.list()):
                raise ValueError("Satu analisis masih berjalan. Tunggu sampai selesai.")
            models = self.root / "data/models"
            if not all((models / name).exists() for name in ("players.pt", "ball.pt")):
                raise ValueError("Model belum tersedia. Letakkan players.pt dan ball.pt di data/models, lalu coba lagi.")
            self.update(identifier, state="preparing", stage="Memotong klip", start=start, end=end,
                        progress=0, error=None)
        self._launch(identifier, lambda: self._analyze(identifier))
        return self.get(identifier)

    def _analyze(self, identifier):
        item = self.get(identifier)
        directory = self.directory(identifier)
        attempt = directory / f"attempt-{uuid.uuid4().hex}"
        attempt.mkdir()
        temporary = attempt / "clip.mp4"
        self._command(identifier, ["ffmpeg", "-v", "error", "-y", "-ss", str(item["start"]),
            "-i", str(directory / "preview.mp4"), "-t", str(item["end"] - item["start"]),
            "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-threads", "2", "-c:a", "aac", "-movflags", "+faststart", str(temporary)])
        clip_meta = probe(temporary)
        identity = file_hash(temporary)
        (directory / "data").mkdir(exist_ok=True)
        (attempt / "data").mkdir()
        self.update(identifier, state="analyzing", stage="Deteksi dan tracking", progress=0,
                    attempt=attempt.name)
        self._command(identifier, [sys.executable, "-m", "app.analyze",
            "--media", str(temporary),
            "--model", str(self.root / "data/models/players.pt"),
            "--ball-model", str(self.root / "data/models/ball.pt"),
            "--output", str(attempt / "data/automatic.json")])
        result = json.loads((attempt / "data/automatic.json").read_text())
        if result.get("identity") != identity:
            raise ValueError("Hasil analisis tidak cocok dengan video.")
        temporary.replace(directory / "clip.mp4")
        for output in (attempt / "data").iterdir():
            output.replace(directory / "data" / output.name)
        self.update(identifier, state="ready", stage="Analisis selesai", progress=100, error=None,
                    clip_meta=clip_meta, identity=identity)
        with self.lock:
            self.contexts.pop(identifier, None)

    def retry(self, identifier):
        with self.lock:
            item = self.get(identifier)
            if item["state"] != "error":
                raise ValueError("Hanya proses gagal yang bisa dicoba lagi.")
            directory = self.directory(identifier)
            if (directory / "preview.mp4").exists() and "start" in item:
                return self.start_analysis(identifier, item["start"], item["end"])
            self.update(identifier, state="importing", error=None)
            if item["source"] == "youtube":
                self.update(identifier, state="downloading")
                self._launch(identifier, lambda: self._download(identifier))
            else:
                self._launch(identifier, lambda: self._prepare(identifier, directory / "source.bin"))
            return self.get(identifier)

    def context(self, identifier):
        with self.lock:
            item = self.get(identifier)
            if item["state"] != "ready":
                raise ValueError("Analisis proyek belum selesai.")
            if identifier not in self.contexts:
                directory = self.directory(identifier)
                self.contexts[identifier] = dict(root=directory, media=directory / "clip.mp4",
                    name=item["name"], clip="Klip analisis", sourceOffset=item["start"],
                    meta=item["clip_meta"], identity=item["identity"], observations=[], jobs={},
                    store=Store(directory / "data/project.sqlite", item["clip_meta"]["duration"]))
            return self.contexts[identifier]
