import unittest
import numpy as np
from app.pitch import fit_pitch, project


class PitchTests(unittest.TestCase):
    def test_known_mapping(self):
        source = [[.1, .1], [.9, .1], [.9, .9], [.1, .9], [.5, .5]]
        target = [[0, 0], [100, 0], [100, 60], [0, 60], [50, 30]]
        fit = fit_pitch(source, target)
        self.assertIsNotNone(fit)
        np.testing.assert_allclose(project([.5, .5], fit["matrix"]), [50, 30], atol=1e-4)

    def test_degenerate_and_missing_points(self):
        self.assertIsNone(fit_pitch([[0, 0]] * 4, [[1, 1]] * 4))
        self.assertIsNone(fit_pitch([[0, 0]], [[0, 0]]))
        self.assertIsNone(project([.5, .5], np.zeros((3, 3))))
