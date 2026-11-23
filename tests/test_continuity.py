import unittest

from app.tracking import stitch_tracks


def observation(time, track, x, team=0, segment=0):
    return dict(time=time, segment=segment, players=[dict(
        track=track, position=[x, .6], height=.1, width=.03,
        team=team, team_confidence=.9, role="player")])


class ContinuityTests(unittest.TestCase):
    def test_short_unambiguous_fragment_joins_with_provenance(self):
        rows = [observation(0, 1, .2), observation(.1, 1, .21),
                observation(.3, 35, .23), observation(.4, 35, .24)]
        links = stitch_tracks(rows)
        self.assertEqual(len(links), 1)
        self.assertEqual(rows[-1]["players"][0]["track"], 1)
        self.assertEqual(rows[-1]["players"][0]["raw_track"], 35)

    def test_other_team_cut_and_long_gap_never_join(self):
        for last in [observation(.3, 35, .23, team=1),
                     observation(.3, 35, .23, segment=1),
                     observation(1, 35, .23)]:
            rows = [observation(0, 1, .2), observation(.1, 1, .21), last]
            self.assertEqual(stitch_tracks(rows), [])

    def test_two_nearby_predecessors_are_ambiguous(self):
        first = observation(0, 1, .2)
        first["players"].append(dict(first["players"][0], track=2))
        last = observation(.2, 35, .2)
        self.assertEqual(stitch_tracks([first, last]), [])

    def test_overlapping_tracklets_cannot_be_merged(self):
        rows = [observation(0, 1, .2), observation(.1, 35, .21), observation(.2, 1, .22)]
        self.assertEqual(stitch_tracks(rows), [])
