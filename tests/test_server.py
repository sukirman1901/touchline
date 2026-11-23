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


if __name__ == "__main__":
    unittest.main()
