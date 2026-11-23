import subprocess
import tempfile
from pathlib import Path

import cv2

from .data import probe

# Shared visual geometry: browser viewBox is always 1280 x 720.
COLORS = {"completed": (148, 212, 100), "intercepted": (103, 107, 255),
          "out": (103, 107, 255), "unknown": (78, 176, 255)}


def draw_events(frame, timestamp, events):
    height, width = frame.shape[:2]
    scale = width / 1280
    thickness = max(1, round(3 * scale))
    for event in events:
        if not event["reviewed"] or not event["start"] <= timestamp <= event["end"]:
            continue
        source = tuple(round(v * d) for v, d in zip(event["source"], (width, height)))
        target = tuple(round(v * d) for v, d in zip(event["target"], (width, height)))
        color = COLORS[event["outcome"]] if event["kind"] == "pass" else (78, 176, 255)
        if event["kind"] == "pass":
            cv2.arrowedLine(frame, source, target, color, thickness, cv2.LINE_AA, tipLength=.05)
            center = source
        else:
            # Explicit coach-authored two-anchor trajectory, not inferred possession.
            progress = (timestamp - event["start"]) / (event["end"] - event["start"])
            center = tuple(round(a + (b - a) * progress) for a, b in zip(source, target))
        cv2.ellipse(frame, center, (max(2, round(23 * scale)), max(1, round(8 * scale))),
                    0, 0, 360, color, thickness, cv2.LINE_AA)
    return frame


def render_export(source, destination, events, start, end, progress):
    meta = probe(source)
    fps = meta["fps"]
    # Align trim and audio to the same source-frame boundaries.
    first, last = round(start * fps), round(end * fps)
    if last <= first:
        raise ValueError("Rentang ekspor terlalu pendek.")
    duration = (last - first) / fps
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="render-", dir=destination.parent) as tmp:
        intermediate = Path(tmp) / "frames.mp4"
        capture = cv2.VideoCapture(str(source))
        capture.set(cv2.CAP_PROP_POS_FRAMES, first)
        writer = cv2.VideoWriter(str(intermediate), cv2.VideoWriter_fourcc(*"mp4v"),
                                 fps, (meta["width"], meta["height"]))
        try:
            if not capture.isOpened() or not writer.isOpened():
                raise RuntimeError("Video tidak dapat dibuka untuk ekspor.")
            for index in range(first, last):
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("Video terhenti sebelum rentang ekspor selesai.")
                writer.write(draw_events(frame, index / fps, events))
                if (index - first) % 30 == 0:
                    progress(round(85 * (index - first) / (last - first)))
        finally:
            capture.release()
            writer.release()
        progress(90)
        command = ["ffmpeg", "-v", "error", "-y", "-i", str(intermediate),
                   "-ss", str(first / fps), "-i", str(source),
                   "-map", "0:v:0", "-map", "1:a:0?", "-t", str(duration),
                   "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
                   str(destination)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            destination.unlink(missing_ok=True)
            raise RuntimeError("FFmpeg: " + result.stderr[-1000:])
        progress(100)
