"""Conservative image-space inference; confidence is a heuristic, not probability."""
from bisect import bisect_left
import math
import uuid

MAX_GAP = .21


def sample_path(path, timestamp):
    index = bisect_left(path, timestamp, key=lambda p: p["time"])
    if index < len(path) and abs(path[index]["time"] - timestamp) < 1e-6:
        return path[index]
    if not 0 < index < len(path):
        return None
    a, b = path[index - 1], path[index]
    if (b["time"] - a["time"] > MAX_GAP or a["segment"] != b["segment"] or
            a.get("track") != b.get("track")):
        return None
    weight = (timestamp - a["time"]) / (b["time"] - a["time"])
    return dict(a, position=[x + (y - x) * weight for x, y in zip(a["position"], b["position"])])


def infer(frames, identity):
    owners, runs, run = [], [], []
    balls = [dict(time=f["time"], segment=f["segment"], position=f["ball"], track=f.get("ball_track"))
             for f in frames if f["ball"] is not None]

    def finish():
        if sum(p["ownership_evidence"] == "observed" for p in run) >= 3 and run[-1]["time"] - run[0]["time"] >= .19:
            runs.append(list(run))
            owners.extend(run)
        run.clear()

    decisions = []
    for frame in frames:
        candidates = []
        if frame["ball"] is not None:
            for player in frame["players"]:
                if player.get("role") == "referee":
                    continue
                dx = (frame["ball"][0] - player["position"][0]) * 1280
                dy = (frame["ball"][1] - player["position"][1]) * 720
                radius = max(12, min(38, player["height"] * 720 * .45))
                distance = math.hypot(dx, dy)
                if distance < radius:
                    candidates.append((distance / radius, player))
        candidates.sort(key=lambda item: item[0])
        # Do not assign a contested ball to whichever bbox is a pixel nearer.
        player = candidates[0][1] if candidates and (
            len(candidates) == 1 or candidates[1][0] - candidates[0][0] > .3) else None
        decisions.append(dict(player=player, evidence="observed" if not frame.get("interpolated") else "ball-interpolated",
                              reason="missing" if frame["ball"] is None else "contested" if candidates and not player else "free"))

    # Offline reacquisition: bridge only a single short unknown interval when
    # the same player is observed on both sides. Never hold past the last sighting.
    for i, decision in enumerate(decisions):
        if decision["player"] is None or decision["evidence"] != "observed":
            continue
        j = i + 1
        while j < len(frames) and decisions[j]["player"] is None and decisions[j]["reason"] == "missing":
            j += 1
        if j == i + 1 or j >= len(frames):
            continue
        after = decisions[j]
        if (after["player"] is None or after["evidence"] != "observed" or
                after["player"]["track"] != decision["player"]["track"] or
                frames[j]["segment"] != frames[i]["segment"] or
                frames[j]["time"] - frames[i]["time"] > MAX_GAP):
            continue
        replacements = []
        for k in range(i+1, j):
            player = next((p for p in frames[k]["players"]
                           if p["track"] == decision["player"]["track"]), None)
            if player is None or frames[k]["segment"] != frames[i]["segment"]:
                break
            replacements.append((k, player))
        if len(replacements) == j-i-1:
            for k, player in replacements:
                decisions[k].update(player=player, evidence="bridged")

    for frame, decision in zip(frames, decisions):
        player = decision["player"]
        if not player:
            finish()
            continue
        if run and (run[-1]["track"] != player["track"] or
                    run[-1]["segment"] != frame["segment"] or
                    frame["time"] - run[-1]["time"] > MAX_GAP):
            finish()
        run.append(dict(player, time=frame["time"], segment=frame["segment"],
                        ownership_evidence=decision["evidence"]))
    finish()

    events = []
    def event(kind, path, track):
        first, last = path[0], path[-1]
        identifier = str(uuid.uuid5(uuid.NAMESPACE_URL,
                                   f"{identity}:{kind}:{first['time']:.3f}:{last['time']:.3f}:{track}"))
        return dict(id=identifier, kind=kind, start=first["time"], end=last["time"],
                    source=first["position"], target=last["position"], outcome="unknown",
                    reviewed=False, player=f"Track {track}", provenance="automatic",
                    confidence="candidate", trajectory=path,
                    note="Estimasi otomatis dari kedekatan bola dan pelacakan. Periksa di video.")
    for run in runs:
        events.append(event("possession", run, run[0]["track"]))
    for before, after in zip(runs, runs[1:]):
        a, b = before[-1], after[0]
        gap = b["time"] - a["time"]
        if a["track"] == b["track"] or a["segment"] != b["segment"] or not .19 <= gap <= 2:
            continue
        path = [p for p in balls if a["time"] <= p["time"] <= b["time"]]
        if len(path) < 3 or any(y["time"] - x["time"] > MAX_GAP or x["segment"] != y["segment"] or
                                x.get("track") != y.get("track")
                                for x, y in zip(path, path[1:])):
            continue
        if math.hypot((a["position"][0] - b["position"][0]) * 1280,
                      (a["position"][1] - b["position"][1]) * 720) < 40:
            continue
        events.append(event("pass", path, f"{a['track']} → {b['track']}"))
    return dict(owners=owners, balls=balls, events=sorted(events, key=lambda e: e["start"]),
                ownership_coverage={kind: sum(p["ownership_evidence"] == kind for p in owners)
                                    for kind in ("observed", "ball-interpolated", "bridged")})
