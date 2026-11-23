import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from app.server import make_server
from app.store import Store


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        media = root / "clip.mp4"
        media.write_bytes(b"0123456789")
        context = dict(media=media, root=root, meta={"duration": 75}, observations=[],
                       store=Store(root / "test.sqlite", 75), jobs={}, identity="test-source")
        self.server = make_server(context, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("GET", path, headers=headers or {})
        response = connection.getresponse()
        status, headers, body = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return status, headers, body

    def test_video_ranges_and_invalid_range(self):
        status, headers, body = self.request("/media", {"Range": "bytes=2-5"})
        self.assertEqual(status, 206)
        self.assertEqual(body, b"2345")
        self.assertEqual(headers["Content-Range"], "bytes 2-5/10")
        self.assertEqual(self.request("/media", {"Range": "bytes=20-"})[0], 416)
        self.assertEqual(self.request("/media", {"Range": "bytes=-3"})[2], b"789")

    def test_arbitrary_file_access_denied(self):
        self.assertEqual(self.request("/../../etc/passwd")[0], 404)
        self.assertEqual(self.request("/exports/../../etc/passwd")[0], 404)

    def test_new_job_progress_preserves_previous_analysis(self):
        data = Path(self.tmp.name) / "data"
        data.mkdir()
        (data / "automatic.json").write_text(json.dumps(dict(identity="test-source",
            status="ready", owners=[], balls=[], events=[])))
        (data / "automatic.status.json").write_text(json.dumps(dict(identity="test-source",
            status="running", progress=42)))
        result = json.loads(self.request("/api/analysis")[2])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["job"]["progress"], 42)

    def test_wrong_source_analysis_is_not_published(self):
        data = Path(self.tmp.name) / "data"
        data.mkdir()
        (data / "automatic.json").write_text(json.dumps(dict(identity="another-video",
            status="ready", owners=[], balls=[], events=[{"id": "wrong"}])))
        result = json.loads(self.request("/api/analysis")[2])
        self.assertEqual(result["events"], [])
        self.assertEqual(result["status"], "source-mismatch")

    def test_project_media_and_analysis_are_isolated(self):
        for char, name in [("a", "First"), ("b", "Second")]:
            identifier = char * 32
            root = Path(self.tmp.name) / "data/projects" / identifier
            (root / "data").mkdir(parents=True)
            (root / "clip.mp4").write_bytes(name.encode())
            (root / "project.json").write_text(json.dumps(dict(id=identifier, name=name,
                state="ready", source="upload", created=1, start=0, identity=name,
                clip_meta=dict(duration=5, fps=30, width=640, height=360))))
            (root / "data/automatic.json").write_text(json.dumps(dict(identity=name,
                status="ready", owners=[], balls=[], events=[])))
        for char, name in [("a", "First"), ("b", "Second"), ("a", "First")]:
            query = "?project=" + char * 32
            result = json.loads(self.request("/api/project" + query)[2])
            self.assertEqual(result["name"], name)
            self.assertEqual(result["automatic"]["identity"], name)
            self.assertEqual(self.request("/media" + query)[2], name.encode())
        self.assertEqual(self.request("/media?project=missing")[0], 400)

    def test_cross_origin_upload_is_rejected_before_reading_body(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        connection.request("POST", "/api/projects/upload", b"video",
                           {"Origin": "https://example.com", "Content-Type": "application/octet-stream"})
        response = connection.getresponse()
        self.assertEqual(response.status, 400)
        self.assertIn("Origin", response.read().decode())
        connection.close()


if __name__ == "__main__":
    unittest.main()
