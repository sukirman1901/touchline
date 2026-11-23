"""Adapted from mradovic38/football-analysis speed_estimation/speed_estimator.py.

Upstream: 1aaac243cc41924f80c0fc904cb0f1ce8c9ecc7d. MIT; see LICENSE.
Retained: scaling, displacement/time calculation and per-ID moving averages.
Changes: valid-only warm-up, missing values are unknown, outliers rejected rather
than clipped, selective history reset. Timing/gap guards live in app.motion.
"""
import math
from collections import deque


class SpeedEstimator:
    def __init__(self, field_width=528, field_height=352,
                 real_field_length=100, real_field_width=50, smoothing_window=5):
        self.scale_x = real_field_length / field_width
        self.scale_y = real_field_width / field_height
        self.previous_positions = {}
        self.speed_history = {}
        self.smoothing_window = smoothing_window
        self.max_speed = 43.2

    def calculate_speed(self, tracks, frame_number, fps):
        for track_type in tracks:
            for player_id, track in tracks[track_type].items():
                track["speed"] = None
                if track.get("projection") is None:
                    self.reset_track(player_id)
                    continue
                current_position = track["projection"]
                if player_id in self.previous_positions:
                    prev_position, prev_frame = self.previous_positions[player_id]
                    distance = self._calculate_distance(prev_position, current_position)
                    time_diff = (frame_number - prev_frame) / fps
                    speed = (distance / time_diff) * 3.6 if time_diff > 0 else None
                    if speed is None or not math.isfinite(speed) or speed > self.max_speed:
                        self.reset_track(player_id)
                        continue
                    track["speed"] = self._smooth_speed(player_id, speed)
                self.previous_positions[player_id] = (current_position, frame_number)
        return tracks

    def _calculate_distance(self, pos1, pos2):
        dx = (pos2[0] - pos1[0]) * self.scale_x
        dy = (pos2[1] - pos1[1]) * self.scale_y
        return math.sqrt(dx**2 + dy**2)

    def _smooth_speed(self, player_id, speed):
        if player_id not in self.speed_history:
            self.speed_history[player_id] = deque(maxlen=self.smoothing_window)
        self.speed_history[player_id].append(speed)
        return sum(self.speed_history[player_id]) / len(self.speed_history[player_id])

    def reset_track(self, player_id):
        self.previous_positions.pop(player_id, None)
        self.speed_history.pop(player_id, None)

    def reset(self):
        self.previous_positions = {}
        self.speed_history = {}
