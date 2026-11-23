"""Independent tracking policies: image-space limits, not calibrated physics."""
import math
from collections import defaultdict


def stitch_tracks(frames):
    """Join only short, unambiguous same-team fragments; not cross-shot Re-ID."""
    tracklets = defaultdict(list)
    for frame in frames:
        for player in frame["players"]:
            player.setdefault("raw_track", player["track"])
            tracklets[(frame["segment"], player["track"])].append((frame["time"], player))
    ordered = sorted(tracklets, key=lambda key: tracklets[key][0][0])
    canonical, consumed, links = {}, set(), []
    for key in ordered:
        samples = tracklets[key]
        start, head = samples[0]
        choices = []
        for old in ordered:
            if old == key or old[0] != key[0] or old in consumed:
                continue
            previous = tracklets[old]
            end, tail = previous[-1]
            gap = start - end
            if not .001 < gap <= .4:
                continue
            if (head.get("team") is None or head.get("team") != tail.get("team") or
                    min(head.get("team_confidence", 0), tail.get("team_confidence", 0)) < .75 or
                    head.get("role") != tail.get("role")):
                continue
            ratio = head["height"] / max(tail["height"], .001)
            if not .75 <= ratio <= 1.33:
                continue
            prediction = tail["position"]
            if len(previous) >= 2:
                before_time, before = previous[-2]
                dt = end - before_time
                if dt > 0 and distance(before["position"], tail["position"]) / dt < 250:
                    prediction = [v + (v - u) / dt * gap
                                  for u, v in zip(before["position"], tail["position"])]
            error = distance(head["position"], prediction)
            if error <= 12 + 80 * gap:
                choices.append((error, old))
        choices.sort()
        # Nearest alone is insufficient when two teammates overlap.
        if choices and (len(choices) == 1 or choices[1][0] - choices[0][0] >= 12):
            error, old = choices[0]
            # Prevent two new fragments competing for one predecessor.
            competitors = [other for other in ordered if other != key and other != old and
                           other[0] == key[0] and
                           abs(tracklets[other][0][0] - start) <= .1 and
                           tracklets[other][0][1].get("team") == head.get("team") and
                           distance(tracklets[other][0][1]["position"], head["position"]) < 24]
            if competitors:
                canonical[key] = key[1]
                continue
            canonical[key] = canonical.get(old, old[1])
            consumed.add(old)
            links.append(dict(segment=key[0], from_track=key[1], to_track=canonical[key],
                              gap=round(start-tracklets[old][-1][0], 3),
                              prediction_error_px=round(error, 2), method="short-gap-motion-team"))
        else:
            canonical[key] = key[1]
    for frame in frames:
        for player in frame["players"]:
            player["track"] = canonical[(frame["segment"], player["track"])]
    return links


def distance(a, b):
    return math.hypot((a[0] - b[0]) * 1280, (a[1] - b[1]) * 720)


def associate_ball(frames, experimental_reacquisition=False):
    candidates = []
    for frame in frames:
        valid = []
        for candidate in frame["candidates"]:
            x, y = candidate["position"]
            # Faces, hands and jersey badges are common model false positives.
            inside_body = any(
                abs(x - p["position"][0]) < p["width"] * .55 and
                p["position"][1] - p["height"] * 1.1 < y < p["position"][1] - p["height"] * .18
                for p in frame["players"])
            if not inside_body:
                valid.append(candidate)
        candidates.append(valid)
    def forward_supported(index, candidate):
        # Offline confirmation, not a link back to the lost trajectory.
        if candidate["confidence"] < .4 or index + 2 >= len(frames):
            return False
        point, timestamp = candidate["position"], frames[index]["time"]
        for j in range(index + 1, index + 3):
            dt = frames[j]["time"] - timestamp
            if frames[j]["segment"] != frames[index]["segment"] or not 0 < dt <= .21:
                return False
            matches = [c for c in candidates[j] if c["confidence"] >= .15 and
                       distance(point, c["position"]) <= 20 + 350 * dt]
            if len(matches) != 1:
                return False
        return True

    previous = None
    ball_track = 0
    for i, frame in enumerate(frames):
        ranked = []
        recovered = []
        for candidate in candidates[i]:
            support = sum(any(distance(candidate["position"], c["position"]) <
                                  15 + 250 * abs(other["time"] - frame["time"])
                                  for c in candidates[j])
                          for j in range(max(0, i - 2), min(len(frames), i + 3))
                          if j != i and (other := frames[j])["segment"] == frame["segment"]
                          and abs(other["time"] - frame["time"]) <= .41)
            if support < 1 or candidate["confidence"] < .15:
                continue
            score = candidate["confidence"] + support * .2
            if previous and previous["segment"] == frame["segment"]:
                dt = frame["time"] - previous["time"]
                if dt <= .31:
                    delta = distance(candidate["position"], previous["position"])
                    if experimental_reacquisition and previous.get("velocity") is not None:
                        predicted = [p + v * dt for p, v in
                                     zip(previous["position"], previous["velocity"])]
                        delta = min(delta, distance(candidate["position"], predicted))
                    if delta > 20 + 350 * dt:
                        if experimental_reacquisition and dt >= .19 and forward_supported(i, candidate):
                            recovered.append((score, candidate))
                        continue
                    score += max(0, 1 - delta / (20 + 350 * dt))
            ranked.append((score, candidate))
        ranked.sort(key=lambda item: item[0], reverse=True)
        reacquired = not ranked and len(recovered) == 1
        if reacquired:
            ranked = recovered
        frame["ball"] = None
        frame["ball_track"] = None
        frame["interpolated"] = False
        if ranked and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] > .15):
            if (previous is None or reacquired or previous["segment"] != frame["segment"] or
                    frame["time"] - previous["time"] > .31):
                ball_track += 1
            frame["ball"] = ranked[0][1]["position"]
            frame["ball_track"] = ball_track
            velocity = None
            if previous and previous["track"] == ball_track:
                dt = frame["time"] - previous["time"]
                if 0 < dt <= .21:
                    velocity = [(b - a) / dt for a, b in zip(previous["position"], frame["ball"])]
            previous = dict(position=frame["ball"], time=frame["time"], segment=frame["segment"],
                            track=ball_track, velocity=velocity)
    observed = [i for i, frame in enumerate(frames) if frame["ball"] is not None]
    for left, right in zip(observed, observed[1:]):
        a, b = frames[left], frames[right]
        dt = b["time"] - a["time"]
        if (a["segment"] != b["segment"] or a["ball_track"] != b["ball_track"] or
                dt > .21 or distance(a["ball"], b["ball"]) > 20 + 350 * dt):
            continue
        for i in range(left + 1, right):
            if frames[i]["segment"] != a["segment"]:
                continue
            weight = (frames[i]["time"] - a["time"]) / dt
            frames[i]["ball"] = [x + (y - x) * weight for x, y in zip(a["ball"], b["ball"])]
            frames[i]["interpolated"] = True
            frames[i]["ball_track"] = a["ball_track"]


def smooth_players(frames):
    output = []
    weights = (2, 3, 4, 3, 2)
    for i, frame in enumerate(frames):
        points = []
        for player in frame["players"]:
            neighbors = [(p["position"], weights[j - i + 2])
                         for j in range(max(0, i - 2), min(len(frames), i + 3))
                         if frames[j]["segment"] == frame["segment"] and abs(frames[j]["time"] - frame["time"]) <= .41
                         for p in frames[j]["players"] if p["track"] == player["track"]
                         and distance(p["position"], player["position"]) < 80]
            total = sum(w for _, w in neighbors)
            points.append([sum(p[axis] * w for p, w in neighbors) / total for axis in (0, 1)])
        output.append(points)
    for frame, points in zip(frames, output):
        for player, position in zip(frame["players"], points):
            player["position"] = position
