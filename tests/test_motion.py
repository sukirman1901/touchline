import unittest

from app.motion import MetricMotion


class MotionTests(unittest.TestCase):
    def test_no_startup_zero_bias(self):
        estimator = MetricMotion()
        self.assertIsNone(estimator.update("0:1", 0, [0, 0])["speed_kmh"])
        self.assertAlmostEqual(estimator.update("0:1", .1, [.2, 0])["speed_kmh"], 7.2)

    def test_valid_samples_are_smoothed(self):
        estimator = MetricMotion()
        estimator.update("0:1", 0, [0, 0])
        estimator.update("0:1", .1, [.2, 0])
        value = estimator.update("0:1", .2, [.6, 0])
        self.assertAlmostEqual(value["speed_kmh"], 10.8)
        self.assertAlmostEqual(value["distance_m"], .4)

    def test_gap_spike_and_missing_projection_reset_history(self):
        estimator = MetricMotion()
        estimator.update("0:1", 0, [0, 0])
        self.assertIsNone(estimator.update("0:1", 2, [4, 0])["speed_kmh"])
        self.assertIsNone(estimator.update("0:1", 2.1, [50, 0])["speed_kmh"])
        self.assertIsNone(estimator.update("0:1", 2.2, None)["speed_kmh"])
        self.assertIsNone(estimator.update("0:1", 2.3, [4, 0])["speed_kmh"])
        self.assertAlmostEqual(estimator.update("0:1", 2.4, [4.2, 0])["speed_kmh"], 7.2)

    def test_shot_identity_has_independent_history(self):
        estimator = MetricMotion()
        estimator.update("0:1", 0, [0, 0])
        self.assertIsNone(estimator.update("1:1", .1, [.2, 0])["speed_kmh"])
