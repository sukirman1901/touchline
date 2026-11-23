import tempfile
import subprocess
import unittest
from pathlib import Path

import cv2
import numpy as np

from app.export import draw_events, render_export
from app.data import probe


EVENT = dict(kind="pass", start=.2, end=.7, source=[.2, .5], target=[.8, .5],
             reviewed=True, outcome="completed", player="", note="")


class ExportTests(unittest.TestCase):
    def test_only_reviewed_events_inside_interval(self):
        black = np.zeros((180, 320, 3), dtype=np.uint8)
        self.assertEqual(draw_events(black.copy(), 0, [EVENT]).sum(), 0)
        self.assertGreater(draw_events(black.copy(), .5, [EVENT]).sum(), 0)
        self.assertEqual(draw_events(black.copy(), .8, [EVENT]).sum(), 0)
        self.assertEqual(draw_events(black.copy(), .5, [{**EVENT, "reviewed": False}]).sum(), 0)

    def test_export_preserves_timing_and_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, dest = root / "source.mp4", root / "out.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "color=c=black:s=320x180:r=30:d=1",
                            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                            "-shortest", str(source)], check=True)
            render_export(source, dest, [EVENT], 0, 1, lambda _: None)
            info = probe(dest)
            self.assertTrue(info["audio"])
            self.assertAlmostEqual(info["duration"], 1, delta=.06)
            self.assertEqual(info["fps"], 30)
            cap = cv2.VideoCapture(str(dest))
            cap.set(cv2.CAP_PROP_POS_MSEC, 500)
            ok, frame = cap.read()
            cap.release()
            self.assertTrue(ok)
            self.assertGreater(frame.sum(), 0)
