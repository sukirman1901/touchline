import unittest
from app.tracking import associate_ball, smooth_players


def sample(t, candidates, segment=0, players=None):
    return dict(time=t, segment=segment, players=players or [],
                candidates=[dict(position=p, confidence=c) for p, c in candidates])


class TrackingTests(unittest.TestCase):
    def test_supported_reacquisition_starts_new_ball_path(self):
        rows = [sample(0, [([.55, .75], .7)]),
                sample(.1, [([.546, .75], .7)]), sample(.2, []),
                sample(.3, [([.44, .78], .5)]),
                sample(.4, [([.422, .78], .6)]),
                sample(.5, [([.378, .79], .3)]),
                sample(.6, [([.35, .79], .4)])]
        associate_ball(rows, experimental_reacquisition=True)
        self.assertEqual(rows[3]["ball"], [.44, .78])
        self.assertNotEqual(rows[1]["ball_track"], rows[3]["ball_track"])
        self.assertIsNone(rows[2]["ball"])
        self.assertEqual(rows[5]["ball"], [.378, .79])

    def test_reacquisition_requires_two_future_observations_in_same_scene(self):
        for final in [sample(.5, []), sample(.5, [([.38, .78], .7)], segment=1)]:
            rows = [sample(0, [([.55, .75], .7)]),
                    sample(.1, [([.546, .75], .7)]), sample(.2, []),
                    sample(.3, [([.44, .78], .5)]),
                    sample(.4, [([.422, .78], .6)]), final]
            associate_ball(rows, experimental_reacquisition=True)
            self.assertIsNone(rows[3]["ball"])

    def test_experimental_reacquisition_is_disabled_by_default(self):
        rows = [sample(0, [([.55, .75], .7)]),
                sample(.1, [([.546, .75], .7)]), sample(.2, []),
                sample(.3, [([.44, .78], .5)]),
                sample(.4, [([.422, .78], .6)]),
                sample(.5, [([.378, .79], .3)])]
        associate_ball(rows)
        self.assertIsNone(rows[3]["ball"])

    def test_trajectory_does_not_jump_to_distant_higher_confidence(self):
        frames = [sample(i / 10, [([.2 + .005 * i, .6], .7)]) for i in range(5)]
        frames[3]["candidates"].append(dict(position=[.8, .2], confidence=.99))
        associate_ball(frames)
        self.assertAlmostEqual(frames[3]["ball"][0], .215)

    def test_short_gap_interpolated_but_long_gap_not(self):
        frames = [sample(i / 10, [([.2 + .005 * i, .6], .7)]) for i in range(10)]
        for i in (3, 6, 7, 8):
            frames[i]["candidates"] = []
        associate_ball(frames)
        self.assertIsNotNone(frames[3]["ball"])
        self.assertTrue(frames[3]["interpolated"])
        self.assertIsNone(frames[7]["ball"])

    def test_cut_and_body_detections_are_rejected(self):
        player = dict(track=1, position=[.5, .8], height=.4, width=.1)
        rows = [sample(i / 10, [([.5, .5], .9)], players=[player]) for i in range(5)]
        associate_ball(rows)
        self.assertTrue(all(row["ball"] is None for row in rows))
        rows = [sample(0, [([.2, .5], .8)]), sample(.1, []),
                sample(.2, [([.3, .5], .8)], segment=1)]
        associate_ball(rows)
        self.assertIsNone(rows[1]["ball"])

    def test_smoothing_does_not_cross_id_or_scene(self):
        rows = [sample(0, [], players=[dict(track=1, position=[.2, .5])]),
                sample(.1, [], segment=1, players=[dict(track=1, position=[.8, .5])])]
        smooth_players(rows)
        self.assertEqual(rows[0]["players"][0]["position"], [.2, .5])
