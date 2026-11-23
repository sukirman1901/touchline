"""Small, repeatable model comparison; saves detections and visual review sheets."""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO


def benchmark(model_path, media, output, size=1280, tiled=False):
    torch.set_num_threads(4)
    model = YOLO(str(model_path))
    capture = cv2.VideoCapture(str(media))
    times = [2, 5, 8, 10, 12, 15, 18, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]
    records, tiles = [], []
    started = time.monotonic()
    for timestamp in times:
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f"Frame {timestamp} unavailable")
        h, w = frame.shape[:2]
        tw, th = round(w * .6), round(h * .65)
        origins = [(0, 0), (w-tw, 0), (0, h-th), (w-tw, h-th)] if tiled else [(0, 0)]
        images = [frame[y:y+th, x:x+tw] for x, y in origins] if tiled else [frame]
        results = model(images, imgsz=size, conf=.15, verbose=False)
        boxes = []
        for result, (ox, oy) in zip(results, origins):
            for box, confidence in zip(result.boxes.xyxy.cpu().numpy(), result.boxes.conf.cpu().numpy()):
                x1, y1, x2, y2 = map(float, box)
                x1, x2, y1, y2 = x1+ox, x2+ox, y1+oy, y2+oy
                position = [(x1+x2)/2/w, (y1+y2)/2/h]
                if any(np.linalg.norm((np.array(position)-b["position"])*[w,h]) < 8 for b in boxes):
                    continue
                boxes.append(dict(position=position, confidence=float(confidence), box=[x1,y1,x2,y2]))
        for candidate in boxes:
            x1,y1,x2,y2 = candidate["box"]
            confidence = candidate["confidence"]
            cv2.rectangle(frame, (round(x1) - 8, round(y1) - 8), (round(x2) + 8, round(y2) + 8),
                          (0, 255, 255), 2)
            cv2.putText(frame, f"{confidence:.2f}", (round(x1), round(y1) - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 255), 1)
        records.append(dict(time=timestamp, candidates=boxes))
        cv2.putText(frame, f"{timestamp}s | {len(boxes)} candidate(s)", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, .8, (255, 255, 255), 2)
        tiles.append(cv2.resize(frame, (640, 360)))
    capture.release()
    output.mkdir(parents=True, exist_ok=True)
    for offset in range(0, len(tiles), 6):
        rows = [np.concatenate(tiles[i:i + 2], axis=1) for i in range(offset, min(offset + 6, len(tiles)), 2)]
        cv2.imwrite(str(output / f"ball-review-{offset // 6 + 1}.jpg"), np.concatenate(rows, axis=0))
    report = dict(model=str(model_path), size=size, tiled=tiled, confidence=.15,
                  seconds=time.monotonic() - started, sampled=len(times),
                  detected=sum(bool(row["candidates"]) for row in records), frames=records)
    (output / "benchmark.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "frames"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--media", type=Path, default=Path.home() / "Downloads/Gol_1_Persibo_Sehabudin.mp4")
    parser.add_argument("--output", type=Path, default=Path("data/ball-benchmark"))
    parser.add_argument("--size", type=int, default=1280)
    parser.add_argument("--tiled", action="store_true")
    args = parser.parse_args()
    benchmark(args.model, args.media, args.output, args.size, args.tiled)
