import http.client
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
                       store=Store(root / "test.sqlite", 75), jobs={})
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


if __name__ == "__main__":
    unittest.main()
