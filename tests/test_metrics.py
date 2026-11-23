import unittest
from app.metrics import analyze_metrics


class MetricsTests(unittest.TestCase):
    def test_metric_motion_and_unknown_gap(self):
        frames = [dict(time=t, segment=0, players=[dict(track=1, role="player",
                  team=0, pitch=[t * 2, 10])]) for t in (0, .1, .2, 2)]
        result = analyze_metrics(frames, [], 100, 60)
        self.assertAlmostEqual(frames[2]["players"][0]["speed_kmh"], 7.2)
        self.assertIsNone(frames[3]["players"][0]["speed_kmh"])
        self.assertAlmostEqual(result["tracks"]["0:1"]["distance_m"], .4)

    def test_missing_calibration_has_no_speed(self):
        frames = [dict(time=0, segment=0, players=[dict(track=1, role="player")])]
        result = analyze_metrics(frames, [], 100, 60)
        self.assertIsNone(frames[0]["players"][0]["speed_kmh"])
        self.assertEqual(result["tracks"], {})
