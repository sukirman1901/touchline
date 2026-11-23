"""Metric analytics on validated pitch coordinates; no pixel-to-speed fallback."""
from collections import defaultdict
import math
import numpy as np
from .motion import MetricMotion


def analyze_metrics(frames, owners, length=105., width=68.):
    motion, tracks = MetricMotion(), {}
    heatmaps = defaultdict(lambda: np.zeros((12, 20)))
    possession = defaultdict(float)
    owner_map = {(p["time"], p["segment"]): p for p in owners}
    for i, frame in enumerate(frames):
        dt = frames[i+1]["time"] - frame["time"] if i+1 < len(frames) and frames[i+1]["segment"] == frame["segment"] else 0
        dt = dt if 0 < dt <= .21 else 0
        owner = owner_map.get((frame["time"], frame["segment"]))
        team = owner.get("team") if owner else None
        possession[str(team) if team is not None else "unknown"] += dt
        eligible = []
        for player in frame["players"]:
            player["speed_kmh"] = None
            point = player.get("pitch")
            key = f"{frame['segment']}:{player['track']}"
            measured = motion.update(key, frame["time"], point)
            if point is None:
                continue
            entry = tracks.setdefault(key, dict(distance_m=0., observed_seconds=0., team=player.get("team")))
            player["speed_kmh"] = measured["speed_kmh"]
            entry["distance_m"] += measured["distance_m"]
            entry["observed_seconds"] += measured["elapsed"]
            if player.get("role") == "referee":
                continue
            if player.get("team") is not None:
                heatmaps[str(player["team"])][min(11, max(0, int(point[1] / width * 12))),
                                               min(19, max(0, int(point[0] / length * 20)))] += dt
                eligible.append(player)
        frame["territory"] = None
        frame["passing_options"] = []
        if not eligible or len({p["team"] for p in eligible}) < 2:
            continue
        grid = np.array([[(x+.5)*length/20, (y+.5)*width/12] for y in range(12) for x in range(20)])
        points = np.array([p["pitch"] for p in eligible])
        nearest = np.linalg.norm(grid[:, None] - points, axis=2).argmin(axis=1)
        frame["territory"] = [[eligible[index]["team"] for index in nearest[row*20:(row+1)*20]]
                              for row in range(12)]
        carrier = next((p for p in eligible if owner and p["track"] == owner["track"]), None)
        if carrier:
            start = np.array(carrier["pitch"])
            for receiver in eligible:
                if receiver["team"] != carrier["team"] or receiver["track"] == carrier["track"]:
                    continue
                end = np.array(receiver["pitch"])
                vector = end - start
                norm = float(vector @ vector)
                if norm < 1:
                    continue
                blockers = []
                for opponent in eligible:
                    if opponent["team"] == carrier["team"]:
                        continue
                    point = np.array(opponent["pitch"])
                    fraction = float((point-start) @ vector / norm)
                    if 0 < fraction < 1 and np.linalg.norm(point - (start + fraction*vector)) < 2:
                        blockers.append(opponent["track"])
                frame["passing_options"].append(dict(receiver=receiver["track"], distance_m=math.sqrt(norm),
                                                      blockers=blockers, method="geometric-lane-only"))
    return dict(tracks=tracks, heatmaps={k: v.tolist() for k, v in heatmaps.items()},
                possession_seconds=dict(possession), heatmap_units="player-seconds",
                field=dict(length=length, width=width))
