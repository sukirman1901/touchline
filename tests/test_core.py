import tempfile
import unittest
from pathlib import Path

from app.data import load_observations
from app.events import validate_event, summary
from app.store import Store


def event(**changes):
    result = dict(kind="pass", start=1.0, end=2.0, source=[0.2, 0.4],
                  target=[0.7, 0.5], outcome="completed", reviewed=True,
                  note="Review pelatih", player="Track 12")
    result.update(changes)
    return result


class DataTests(unittest.TestCase):
    def test_one_based_frame_time_and_no_filling_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.csv"
            path.write_text("frame,timestamp_sec,entity_type,tracker_id,team_id,x_px,y_px\n"
                            "2,0.07,ball,0,Ball,640,360\n"
                            "8,0.27,player,12,Team_1,128,72\n")
            rows = load_observations(path, 1280, 720, 30)
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0]["time"], 1 / 30)
        self.assertEqual(rows[0]["position"], [0.5, 0.5])
        self.assertEqual(rows[1]["team"], "Cluster B")


class EventTests(unittest.TestCase):
    def test_rejects_invalid_intervals_and_coordinates(self):
        for changes in [dict(start=-1), dict(end=1), dict(end=76),
                        dict(source=[float("nan"), .2]), dict(target=[1.1, .2]),
                        dict(start=float("inf")), dict(outcome="perfect")]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_event(event(**changes), 75)

    def test_unknown_and_unreviewed_excluded_from_completion_rate(self):
        result = summary([event(), event(outcome="unknown"),
                          event(reviewed=False), event(outcome="intercepted")])
        self.assertEqual(result["completion"], 50)
        self.assertEqual(result["unknown"], 1)
        self.assertEqual(result["unreviewed"], 1)
        self.assertIsNone(summary([])["completion"])

    def test_persists_updates_and_deletes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "project.sqlite"
            store = Store(path, 75)
            saved = store.save(event())
            saved["note"] = "Koreksi"
            store.save(saved)
            reopened = Store(path, 75)
            self.assertEqual(reopened.list()[0]["note"], "Koreksi")
            self.assertEqual(reopened.list()[0]["provenance"], "coach")
            reopened.delete(saved["id"])
            self.assertEqual(reopened.list(), [])


if __name__ == "__main__":
    unittest.main()
