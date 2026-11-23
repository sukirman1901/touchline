import unittest
import numpy as np

from app.teams import jersey_feature, assign_teams


class TeamsTests(unittest.TestCase):
    def test_grass_only_crop_stays_unknown(self):
        frame = np.full((100, 100, 3), [30, 130, 30], dtype=np.uint8)
        self.assertIsNone(jersey_feature(frame, [.5, .9], .6, .3))

    def test_dark_jersey_with_green_spill_is_not_grass(self):
        frame = np.full((100, 100, 3), [18, 35, 20], dtype=np.uint8)
        self.assertIsNotNone(jersey_feature(frame, [.5, .9], .6, .3))

    def test_temporal_vote_and_referee_exclusion(self):
        frames = []
        for i in range(12):
            frames.append(dict(segment=0, players=[
                dict(track=1, role="player", jersey=[20, 30, 220] if i != 5 else [220, 30, 20]),
                dict(track=2, role="player", jersey=[220, 30, 20]),
                dict(track=3, role="referee", jersey=[20, 30, 220]),
                dict(track=4, role="player", jersey=None)]))
        palette = assign_teams(frames)
        self.assertEqual(len(palette), 2)
        self.assertNotEqual(frames[0]["players"][0]["team"], frames[0]["players"][1]["team"])
        self.assertEqual(frames[0]["players"][0]["team"], frames[5]["players"][0]["team"])
        self.assertIsNone(frames[0]["players"][2]["team"])
        self.assertIsNone(frames[0]["players"][3]["team"])

    def test_one_color_cannot_invent_two_teams(self):
        frames = [dict(segment=0, players=[dict(track=i, role="player", jersey=[220, 30, 20])])
                  for i in range(20)]
        self.assertEqual(assign_teams(frames), [])

    def test_shadow_does_not_split_red_jerseys_from_dark_opponent(self):
        frames = [dict(segment=0, players=[
            dict(track=1, role="player", jersey=[190, 80, 60]),
            dict(track=2, role="player", jersey=[95, 40, 30]),
            dict(track=3, role="player", jersey=[25, 45, 28])]) for _ in range(6)]
        assign_teams(frames)
        a, b, c = frames[0]["players"]
        self.assertEqual(a["team"], b["team"])
        self.assertNotEqual(a["team"], c["team"])

    def test_track_with_conflicting_jerseys_is_unknown(self):
        rows = [dict(segment=0, players=[
            dict(track=1, role="player", jersey=[190, 40, 40]),
            dict(track=2, role="player", jersey=[25, 45, 28]),
            dict(track=3, role="player", jersey=[190, 40, 40] if i < 5 else [25, 45, 28])
        ]) for i in range(10)]
        assign_teams(rows)
        self.assertIsNone(rows[0]["players"][2]["team"])
