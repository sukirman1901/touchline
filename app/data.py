import csv
import json
import subprocess
from fractions import Fraction


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format",
         "-of", "json", str(path)], check=True, capture_output=True, text=True, timeout=30)
    info = json.loads(result.stdout)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    return dict(width=video["width"], height=video["height"],
                fps=float(Fraction(video["avg_frame_rate"])),
                duration=float(info["format"]["duration"]),
                audio=any(s["codec_type"] == "audio" for s in info["streams"]))


def load_observations(path, width, height, fps):
    rows = []
    with open(path, newline="") as handle:
        for item in csv.DictReader(handle):
            # The prototype increments its frame counter before recording:
            # frame 1 is the source frame at t=0, not t=1/fps.
            rows.append(dict(
                time=(int(item["frame"]) - 1) / fps,
                frame=int(item["frame"]), kind=item["entity_type"],
                track=int(item["tracker_id"]),
                team={"Team_0": "Cluster A", "Team_1": "Cluster B"}.get(item["team_id"]),
                position=[float(item["x_px"]) / width, float(item["y_px"]) / height],
            ))
    return rows
