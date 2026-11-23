import io
import tempfile
import unittest
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import patch

from app.projects import Projects, youtube_url, clip_range


class ProjectTests(unittest.TestCase):
    def test_youtube_only_and_canonical_single_video(self):
        self.assertEqual(youtube_url("https://youtu.be/abcdefghijk?t=4"),
                         "https://www.youtube.com/watch?v=abcdefghijk")
        for url in ["http://127.0.0.1/video", "https://youtube.com.evil.test/watch?v=abcdefghijk",
                    "https://youtube.com/playlist?list=foo", "file:///etc/passwd"]:
            with self.assertRaises(ValueError):
                youtube_url(url)

    def test_range_must_be_finite_and_inside_source(self):
        self.assertEqual(clip_range(2, 8, 10), (2., 8.))
        for start, end in [(0, 11), (-1, 3), (5, 5), (0, float("nan"))]:
            with self.assertRaises(ValueError):
                clip_range(start, end, 10)

    def test_upload_rejects_truncated_stream_and_does_not_publish_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = Projects(Path(tmp))
            with self.assertRaises(ValueError):
                manager.upload(io.BytesIO(b"short"), 100, "match.mp4")
            self.assertFalse(list((Path(tmp) / "data/projects").glob("*/source.bin")))

    def test_upload_is_persisted_and_projects_are_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = Projects(Path(tmp))
            meta = dict(duration=10, fps=30, width=640, height=360, audio=False)
            with patch("app.projects.probe", return_value=meta), patch.object(manager, "_launch"):
                a = manager.upload(io.BytesIO(b"video"), 5, "First.mp4")
                b = manager.upload(io.BytesIO(b"video"), 5, "Second.mp4")
            self.assertNotEqual(a["id"], b["id"])
            self.assertNotEqual(manager.directory(a["id"]), manager.directory(b["id"]))
            restarted = Projects(Path(tmp))
            self.assertEqual(len(restarted.list()), 2)
            self.assertEqual(restarted.get(a["id"])["state"], "error")
            self.assertTrue((manager.directory(a["id"]) / "source.bin").exists())
            with self.assertRaises(ValueError):
                manager.directory("../../etc")

    def test_analysis_missing_models_reports_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = Projects(Path(tmp))
            with patch.object(manager, "_launch"):
                item = manager.upload(io.BytesIO(b"video"), 5, "First.mp4")
            manager.update(item["id"], state="preview", meta=dict(duration=10))
            with self.assertRaisesRegex(ValueError, "players.pt"):
                manager.start_analysis(item["id"], 0, 5)
            self.assertEqual(manager.get(item["id"])["state"], "preview")

    def test_invalid_video_has_readable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = Projects(Path(tmp))
            with patch.object(manager, "_launch"):
                item = manager.upload(io.BytesIO(b"not-video"), 9, "broken.mp4")
            with patch("app.projects.probe", side_effect=StopIteration):
                with self.assertRaisesRegex(ValueError, "video"):
                    manager._prepare(item["id"], manager.directory(item["id"]) / "source.bin")

    def test_duplicate_analysis_rejected_and_retry_keeps_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data/models").mkdir(parents=True)
            for name in ("players.pt", "ball.pt"):
                (root / "data/models" / name).touch()
            manager = Projects(root)
            with patch.object(manager, "_launch"):
                item = manager.upload(io.BytesIO(b"video"), 5, "First.mp4")
                manager.update(item["id"], state="preview", meta=dict(duration=10))
                (manager.directory(item["id"]) / "preview.mp4").write_bytes(b"preview")
                manager.start_analysis(item["id"], 1, 5)
                with self.assertRaises(ValueError):
                    manager.start_analysis(item["id"], 1, 5)
                manager.update(item["id"], state="error", error="model failed")
                result = manager.retry(item["id"])
                self.assertEqual(result["state"], "preparing")
                self.assertEqual(result["start"], 1)
                self.assertEqual((manager.directory(item["id"]) / "source.bin").read_bytes(), b"video")

    def test_shutdown_reaps_owned_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = Projects(Path(tmp))
            item = manager._create("shutdown", "upload")
            started = threading.Event()
            owned = []
            real_popen = subprocess.Popen
            def spawn(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                owned.append(process)
                started.set()
                return process
            with patch("app.projects.subprocess.Popen", side_effect=spawn):
                manager._launch(item["id"], lambda: manager._command(item["id"],
                    [sys.executable, "-c", "import time; time.sleep(60)"]))
                self.assertTrue(started.wait(5))
                try:
                    manager.close()
                    self.assertIsNotNone(owned[0].poll())
                finally:
                    if owned[0].poll() is None:
                        owned[0].terminate()
                        owned[0].wait()
