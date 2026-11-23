"""Timestamp/validity adapter for the adopted mradovic speed component."""
import math

from .vendor.mradovic.speed_estimator import SpeedEstimator


class MetricMotion:
    def __init__(self):
        # Input coordinates are already meters, so both scale factors equal one.
        self.estimator = SpeedEstimator(field_width=1, field_height=1,
                                        real_field_length=1, real_field_width=1)
        self.last = {}

    def update(self, key, timestamp, position):
        unknown = dict(speed_kmh=None, distance_m=0., elapsed=0.)
        if position is None or not all(math.isfinite(v) for v in [timestamp, *position]):
            self.last.pop(key, None)
            self.estimator.reset_track(key)
            return unknown
        previous = self.last.get(key)
        elapsed, distance = 0., 0.
        if previous:
            elapsed = timestamp - previous[0]
            distance = math.dist(position, previous[1])
            if elapsed <= 0 or elapsed > .21:
                self.estimator.reset_track(key)
                elapsed, distance = 0., 0.
            elif distance / elapsed > 12:
                self.last.pop(key, None)
                self.estimator.reset_track(key)
                return unknown
        tracks = {"player": {key: dict(projection=position)}}
        self.estimator.calculate_speed(tracks, timestamp, 1.)
        self.last[key] = (timestamp, position)
        return dict(speed_kmh=tracks["player"][key]["speed"],
                    distance_m=distance, elapsed=elapsed)
