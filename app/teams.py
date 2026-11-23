"""Jersey observations and track-consistent team clusters (not club identities)."""
from collections import defaultdict

import cv2
import numpy as np


def jersey_feature(image, position, height, width):
    """Return median RGB of the central torso, excluding pitch-colored pixels."""
    h, w = image.shape[:2]
    x, bottom = position[0] * w, position[1] * h
    crop = image[max(0, round(bottom - height * h * .78)):
                 min(h, round(bottom - height * h * .38)),
                 max(0, round(x - width * w * .28)):
                 min(w, round(x + width * w * .28))]
    if crop.size == 0:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    grass = ((hsv[:, :, 0] >= 30) & (hsv[:, :, 0] <= 90) &
             (hsv[:, :, 1] > 65) & (hsv[:, :, 2] > 80))
    valid = ~grass & (hsv[:, :, 2] > 12)
    if valid.sum() < max(6, valid.size * .2):
        return None
    return np.median(crop[valid], axis=0)[::-1].round().astype(int).tolist()


def assign_teams(frames):
    observations = defaultdict(list)
    for frame in frames:
        for player in frame["players"]:
            player.update(team=None, team_confidence=0., team_color=None)
            if player.get("role", "player") == "player" and player.get("jersey") is not None:
                observations[(frame["segment"], player["track"])].append(player["jersey"])
    keys = [key for key, rows in observations.items() if len(rows) >= 3]
    if len(keys) < 2:
        return []
    rgb = np.array([np.median(observations[key], axis=0) for key in keys], dtype=np.uint8)
    # Chromaticity reduces splitting one jersey into sun/shadow teams.
    values = rgb.astype(float)
    lab = np.column_stack((values / np.maximum(values.sum(axis=1, keepdims=True), 1) * 255,
                           values.mean(axis=1) * .3))
    first = int(np.argmin(lab[:, 0]))
    centers = np.array([lab[first], lab[np.argmax(np.linalg.norm(lab - lab[first], axis=1))]])
    for _ in range(20):
        labels = np.linalg.norm(lab[:, None] - centers, axis=2).argmin(axis=1)
        if len(set(labels)) != 2:
            return []
        updated = np.array([np.median(lab[labels == c], axis=0) for c in range(2)])
        if np.allclose(updated, centers):
            break
        centers = updated
    if np.linalg.norm(centers[0] - centers[1]) < 25:
        return []
    colors = [np.median(rgb[labels == c], axis=0).astype(int) for c in range(2)]
    palette = [dict(id=c, name=f"Tim {chr(65+c)}", color="#" + "".join(f"{v:02x}" for v in color))
               for c, color in enumerate(colors)]
    assignments = {}
    for key, point in zip(keys, lab):
        distances = np.linalg.norm(centers - point, axis=1)
        label = int(distances.argmin())
        confidence = float(1 - distances[label] / max(distances[1-label], 1))
        samples = np.asarray(observations[key], dtype=float)
        features = np.column_stack((samples / np.maximum(samples.sum(axis=1, keepdims=True), 1) * 255,
                                    samples.mean(axis=1) * .3))
        votes = np.linalg.norm(features[:, None] - centers, axis=2).argmin(axis=1)
        agreement = float(np.mean(votes == label))
        if confidence >= .35 and agreement >= .75:
            assignments[key] = (label, min(confidence, agreement))
    for frame in frames:
        for player in frame["players"]:
            assignment = assignments.get((frame["segment"], player["track"]))
            if assignment and player.get("role", "player") == "player":
                label, confidence = assignment
                player.update(team=label, team_confidence=round(confidence, 3),
                              team_color=palette[label]["color"])
    return palette


def enrich_from_video(frames, media):
    """Backfill jersey samples from cached boxes without rerunning the detector."""
    capture = cv2.VideoCapture(str(media))
    fps = capture.get(cv2.CAP_PROP_FPS)
    index = -1
    try:
        for frame in frames:
            target = round(frame["time"] * fps)
            ok, image = False, None
            while index < target:
                ok, image = capture.read()
                index += 1
                if not ok:
                    break
            if not ok:
                raise RuntimeError(f"Frame unavailable at {frame['time']}")
            for player in frame["players"]:
                player.setdefault("role", "player")
                player["jersey"] = jersey_feature(image, player["position"], player["height"], player["width"])
    finally:
        capture.release()
