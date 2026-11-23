import tempfile
import unittest
import numpy as np
from pathlib import Path

from app.automatic import infer, sample_path
from app.store import Store
from app.export import draw_events


def frame(t, ball, owner=1, segment=0, ambiguous=False):
    players = [{"track": owner, "position": [.3 if owner == 1 else .6, .7],
                "height": .12, "width": .035}]
    if ambiguous:
        players.append(dict(players[0], track=9))
    return dict(time=t, segment=segment, ball=ball, players=players)


class AutomaticTests(unittest.TestCase):
    def test_ball_track_break_prevents_interpolated_flight(self):
        path = [dict(time=0, segment=0, track=1, position=[.5, .7]),
                dict(time=.2, segment=0, track=2, position=[.4, .7])]
        self.assertIsNone(sample_path(path, .1))

    def test_interpolation_stops_at_gaps_and_cuts(self):
        path = [dict(time=0, position=[.2, .4], segment=0),
                dict(time=.1, position=[.4, .4], segment=0),
                dict(time=1, position=[.8, .4], segment=0),
                dict(time=1.1, position=[.2, .4], segment=1)]
        self.assertAlmostEqual(sample_path(path, .05)["position"][0], .3)
        self.assertIsNone(sample_path(path, .5))
        self.assertIsNone(sample_path(path, 1.05))
        self.assertIsNone(sample_path(path, 2))

    def test_ambiguous_or_missing_ball_has_no_owner(self):
        rows = [frame(i / 10, [.3, .7], ambiguous=True) for i in range(8)]
        self.assertEqual(infer(rows, "fixture")["events"], [])
        rows = [frame(i / 10, None) for i in range(8)]
        self.assertEqual(infer(rows, "fixture")["owners"], [])

    def test_short_missing_ball_requires_same_owner_on_both_sides(self):
        rows = [frame(i / 10, [.3, .7]) for i in range(9)]
        rows[4]["ball"] = None
        result = infer(rows, "fixture")
        self.assertEqual(len(result["events"]), 1)
        bridge = next(p for p in result["owners"] if p["time"] == .4)
        self.assertEqual(bridge["ownership_evidence"], "bridged")
        self.assertEqual(result["ownership_coverage"]["bridged"], 1)

    def test_contested_and_observed_release_never_bridge(self):
        for middle in [frame(.4, [.3, .7], ambiguous=True), frame(.4, [.5, .7])]:
            rows = [frame(i / 10, [.3, .7]) for i in range(9)]
            rows[4] = middle
            result = infer(rows, "fixture")
            self.assertFalse(any(p["time"] == .4 for p in result["owners"]))

    def test_no_trailing_owner_hold_without_reacquisition(self):
        rows = [frame(i / 10, [.3, .7]) for i in range(4)]
        rows += [frame(i / 10, None) for i in range(4, 9)]
        self.assertEqual(max(p["time"] for p in infer(rows, "fixture")["owners"]), .3)

    def test_pass_requires_observed_flight_and_stable_receiver(self):
        rows = [frame(i / 10, [.3, .7]) for i in range(5)]
        rows += [frame(.5, [.4, .7]), frame(.6, [.5, .7])]
        rows += [frame(i / 10, [.6, .7], owner=2) for i in range(7, 12)]
        result = infer(rows, "fixture")
        passes = [e for e in result["events"] if e["kind"] == "pass"]
        self.assertEqual(len(passes), 1)
        self.assertFalse(passes[0]["reviewed"])
        self.assertEqual(passes[0]["outcome"], "unknown")
        self.assertEqual(result["events"], infer(rows, "fixture")["events"])
        for row in rows[5:7]:
            row["ball"] = None
        self.assertEqual([e for e in infer(rows, "fixture")["events"] if e["kind"] == "pass"], [])

    def test_camera_cut_cannot_create_pass(self):
        rows = [frame(i / 10, [.3, .7]) for i in range(5)]
        rows += [frame(i / 10, [.6, .7], owner=2, segment=1) for i in range(5, 10)]
        self.assertFalse(any(e["kind"] == "pass" for e in infer(rows, "fixture")["events"]))

    def test_generated_deletion_and_correction_survive_merge(self):
        rows = [frame(i / 10, [.3, .7]) for i in range(5)]
        generated = infer(rows, "fixture")["events"]
        self.assertTrue(generated)
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "events.sqlite", 3)
            self.assertEqual(len(store.merged(generated)), 1)
            store.save(dict(generated[0], note="Coach correction"))
            self.assertEqual(store.merged(generated)[0]["note"], "Coach correction")
            store.delete(generated[0]["id"])
            self.assertEqual(store.merged(generated), [])

    def test_review_retains_trajectory_but_moved_anchor_discards_it(self):
        original = infer([frame(i / 10, [.3, .7]) for i in range(5)], "fixture")["events"][0]
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "events.sqlite", 3)
            saved = store.save(dict(original, reviewed=True), original)
            self.assertEqual(saved["trajectory"], original["trajectory"])
            changed = store.save(dict(original, source=[.1, .1]), original)
            self.assertNotIn("trajectory", changed)

    def test_export_uses_measured_path_and_hides_gap(self):
        event = dict(reviewed=True, provenance="automatic", kind="possession",
                     start=0, end=1, source=[.1, .1], target=[.9, .9],
                     trajectory=[dict(time=0, position=[.5, .5], segment=0),
                                 dict(time=.1, position=[.5, .5], segment=0),
                                 dict(time=1, position=[.9, .9], segment=0)])
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        shown = draw_events(image.copy(), .05, [event])
        self.assertGreater(shown[345:375, 600:680].sum(), 0)
        self.assertEqual(draw_events(image.copy(), .5, [event]).sum(), 0)
        self.assertEqual(draw_events(image.copy(), .05, [dict(event, reviewed=False)]).sum(), 0)
