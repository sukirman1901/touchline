"""Offline detector pass. Run with the existing football-analyzer Python environment."""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import supervision as sv
import torch
from ultralytics import YOLO

from .automatic import infer
from .tracking import associate_ball, smooth_players, stitch_tracks
from .teams import jersey_feature, assign_teams, enrich_from_video
from .pitch import map_frames, LandmarkDetector
from .metrics import analyze_metrics


def write_json(path, payload):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, allow_nan=False))
    temporary.replace(path)


def analyze(media, model_path, destination, ball_path=None, sample_fps=10, pitch_model=None, pitch_layout=None):
    torch.set_num_threads(4)
    model = YOLO(str(model_path))
    ball_model = YOLO(str(ball_path)) if ball_path else None
    if bool(pitch_model) != bool(pitch_layout):
        raise ValueError("Supply both --pitch-model and --pitch-layout")
    pitch = LandmarkDetector(pitch_model, json.loads(pitch_layout.read_text())) if pitch_model else None
    player_classes = [index for index, name in model.names.items() if name.lower() in {"person", "player", "goalkeeper", "referee"}]
    ball_classes = [index for index, name in model.names.items() if "ball" in name.lower()]
    if not player_classes:
        raise ValueError("Model tidak memiliki kelas pemain.")
    status_path = destination.with_suffix(".status.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(media))
    if not capture.isOpened():
        raise RuntimeError("Video tidak dapat dibuka")
    fps = capture.get(cv2.CAP_PROP_FPS)
    width, height = int(capture.get(3)), int(capture.get(4))
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    stride = max(1, round(fps / sample_fps))
    tracker = sv.ByteTrack(frame_rate=round(fps / stride), minimum_consecutive_frames=2)
    identity = hashlib.sha256(media.read_bytes()).hexdigest()
    frames, previous, previous_hist = [], None, None
    segment, index = 0, 0
    cache = destination.with_suffix(".detections.json")
    settings = dict(model=model_path.name, model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
                    ball_model=ball_path.name if ball_path else None,
                    ball_sha256=hashlib.sha256(ball_path.read_bytes()).hexdigest() if ball_path else None,
                    stride=stride, player_size=960, ball_size=640, ball_confidence=.15)
    if pitch:
        settings.update(pitch_model_sha256=hashlib.sha256(pitch_model.read_bytes()).hexdigest(),
                        pitch_layout_sha256=hashlib.sha256(pitch_layout.read_bytes()).hexdigest(),
                        field=dict(length=pitch.length, width=pitch.width))
    started = time.monotonic()
    write_json(status_path, dict(status="running", progress=0, identity=identity))
    try:
        while True:
            ok, image = capture.read()
            if not ok:
                break
            if index % stride:
                index += 1
                continue
            timestamp = index / fps
            small = cv2.resize(image, (96, 54))
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            if previous is not None and (np.mean(cv2.absdiff(small, previous)) > 38 and
                    cv2.compareHist(hist, previous_hist, cv2.HISTCMP_BHATTACHARYYA) > .38):
                segment += 1
                tracker = sv.ByteTrack(frame_rate=round(fps / stride), minimum_consecutive_frames=2)
            previous, previous_hist = small, hist
            result = model(image, imgsz=960, classes=player_classes + (ball_classes if ball_model else []),
                           conf=.15 if ball_model else .25, verbose=False)[0]
            all_detections = sv.Detections.from_ultralytics(result)
            detections = tracker.update_with_detections(
                all_detections[np.isin(all_detections.class_id, player_classes)])
            players = []
            for box, track, class_id in zip(detections.xyxy, detections.tracker_id, detections.class_id):
                x1, y1, x2, y2 = map(float, box)
                if y2 - y1 < 15 or y2 < height * .2:
                    continue
                role = model.names[int(class_id)].lower()
                players.append(dict(track=int(track) + segment * 100000,
                                    role="player" if role == "person" else role,
                                    position=[(x1 + x2) / 2 / width, y2 / height],
                                    height=(y2 - y1) / height, width=(x2 - x1) / width))
                players[-1]["jersey"] = jersey_feature(image, players[-1]["position"],
                                                       players[-1]["height"], players[-1]["width"])
            # Overlapping tiles increase small-ball pixels seen by the detector.
            if ball_model:
                origins = [(0, 0), (0, 0)]
                results = [ball_model(image, imgsz=640, conf=.15, verbose=False)[0],
                           result]
            else:
                tile_w, tile_h = round(width * .6), round(height * .65)
                origins = [(0, 0), (width - tile_w, 0),
                           (0, height - tile_h), (width - tile_w, height - tile_h)]
                crops = [image[y:y + tile_h, x:x + tile_w] for x, y in origins]
                results = model(crops, imgsz=640, classes=ball_classes, conf=.15, verbose=False)
            candidates = []
            for result, (ox, oy) in zip(results, origins):
                for box, confidence, class_id in zip(result.boxes.xyxy.cpu().numpy(),
                                                     result.boxes.conf.cpu().numpy(), result.boxes.cls.cpu().numpy()):
                    if "ball" not in result.names[int(class_id)].lower():
                        continue
                    x1, y1, x2, y2 = box
                    x, y = (x1 + x2) / 2 + ox, (y1 + y2) / 2 + oy
                    if not (.1 * height < y < .94 * height) or max(x2 - x1, y2 - y1) > 28:
                        continue
                    # A ball candidate needs a local pitch-colored surround.
                    patch = image[max(0, int(y) - 18):min(height, int(y) + 18),
                                  max(0, int(x) - 18):min(width, int(x) + 18)]
                    green = cv2.inRange(cv2.cvtColor(patch, cv2.COLOR_BGR2HSV),
                                       np.array([25, 35, 30]), np.array([95, 255, 255]))
                    if np.mean(green > 0) < .25:
                        continue
                    if any(math.hypot(x - c["position"][0] * width, y - c["position"][1] * height) < 8
                           for c in candidates):
                        continue
                    candidates.append(dict(position=[float(x / width), float(y / height)],
                                           confidence=float(confidence)))
            frames.append(dict(time=timestamp, segment=segment, players=players, candidates=candidates))
            if pitch:
                frames[-1]["landmarks"] = pitch.detect(image)
            if len(frames) % 50 == 0:
                print(f"Deteksi {index + 1}/{total} frame ({time.monotonic() - started:.0f}s)", flush=True)
                write_json(status_path, dict(status="running", progress=round(95 * (index + 1) / total),
                                            identity=identity))
            index += 1
    finally:
        capture.release()
    cache.write_text(json.dumps(dict(identity=identity, settings=settings, frames=frames)))
    finalize(cache, destination)
    write_json(status_path, dict(status="ready", progress=100, identity=identity))


def finalize(cache, destination, media=None, experimental_ball_reacquisition=False):
    raw = json.loads(cache.read_text())
    frames = raw["frames"]
    if media is not None:
        enrich_from_video(frames, media)
    teams = assign_teams(frames)
    links = stitch_tracks(frames)
    associate_ball(frames, experimental_reacquisition=experimental_ball_reacquisition)
    raw["settings"]["experimental_ball_reacquisition"] = experimental_ball_reacquisition
    smooth_players(frames)
    result = infer(frames, raw["identity"])
    field = raw["settings"].get("field", dict(length=105., width=68.))
    calibrated = map_frames(frames, **field)
    metrics = analyze_metrics(frames, result["owners"], **field)
    observed = sum(bool(frame["candidates"]) for frame in frames)
    accepted = sum(frame["ball"] is not None and not frame["interpolated"] for frame in frames)
    result.update(schema_version=2, teams=teams, track_links=links, metrics=metrics,
                  identity=raw["identity"], settings=raw["settings"],
                  modules=dict(tracking=dict(status="ready"),
                               teams=dict(status="ready" if teams else "unavailable",
                                          reason=None if teams else "Insufficient distinct jersey observations"),
                               calibration=dict(status="ready" if calibrated else "unavailable",
                                                valid_frames=calibrated,
                                                reason=None if calibrated else "Pitch landmarks not supplied or invalid")),
                  coverage=dict(sampled=len(frames), detected=observed, accepted=accepted,
                                interpolated=sum(f["interpolated"] for f in frames),
                                scenes=len({f["segment"] for f in frames})),
                  players=[dict(time=f["time"], segment=f["segment"], players=f["players"],
                                territory=f["territory"], passing_options=f["passing_options"]) for f in frames],
                  status="ready")
    write_json(destination, result)
    print(json.dumps(dict(coverage=result["coverage"], events=len(result["events"]),
                          passes=sum(e["kind"] == "pass" for e in result["events"])), indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--media", type=Path, default=Path.home() / "Downloads/Gol_1_Persibo_Sehabudin.mp4")
    parser.add_argument("--model", type=Path, default=Path.home() / "Downloads/yolo11n.pt")
    parser.add_argument("--output", type=Path, default=Path("data/automatic.json"))
    parser.add_argument("--ball-model", type=Path)
    parser.add_argument("--sample-fps", type=float, default=10)
    parser.add_argument("--pitch-model", type=Path)
    parser.add_argument("--pitch-layout", type=Path)
    parser.add_argument("--reuse", action="store_true")
    args = parser.parse_args()
    if args.reuse:
        finalize(args.output.with_suffix(".detections.json"), args.output, args.media)
    else:
        try:
            analyze(args.media, args.model, args.output, args.ball_model, args.sample_fps,
                    args.pitch_model, args.pitch_layout)
        except Exception as error:
            write_json(args.output.with_suffix(".status.json"), dict(status="error", error=str(error)))
            raise
