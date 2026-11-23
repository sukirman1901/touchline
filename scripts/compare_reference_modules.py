"""Run bounded, deterministic probes against pinned external source checkouts.

No model downloads, source changes, or remote execution. Not an accuracy benchmark.
"""
import argparse
import importlib.util
import json
import pickle
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mradovic", type=Path, required=True)
    parser.add_argument("--soccart", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = []

    def probe(name, function):
        try:
            results.append(dict(probe=name, result=function()))
        except Exception as exc:
            results.append(dict(probe=name, exception=type(exc).__name__, detail=str(exc)))

    sys.path.insert(0, str(args.mradovic))
    from club_assignment import Club
    from club_assignment.club_assigner import ClubAssignerModel
    from ball_to_player_assignment import BallToPlayerAssigner
    speed = load("reference_speed", args.mradovic / "speed_estimation/speed_estimator.py")
    mapping = load("reference_homography", args.mradovic / "position_mappers/homography.py")

    def possession_count():
        assigner = BallToPlayerAssigner(Club("A", (255, 0, 0), (255, 0, 0)),
                                       Club("B", (0, 0, 0), (0, 0, 0)))
        tracks = dict(ball={5: dict(projection=(50, 50), bbox=[48, 48, 52, 52])},
                      player={1: dict(projection=(50, 50), club="A")}, goalkeeper={})
        assigner.assign(tracks, 1, None, None)
        return dict(input_frames=1, possession_updates=assigner.possession_tracker.sum)

    def speed_startup():
        estimator = speed.SpeedEstimator(field_width=100, field_height=50)
        estimator.calculate_speed({"player": {1: {"projection": (0, 0)}}}, 0, 10)
        result = estimator.calculate_speed({"player": {1: {"projection": (.2, 0)}}}, 1, 10)
        return dict(true_constant_speed_kmh=7.2, second_sample_kmh=result["player"][1]["speed"])

    probe("mradovic.one_frame_possession_count", possession_count)
    probe("mradovic.speed_startup_zero_padding", speed_startup)
    def steady_speed():
        estimator = speed.SpeedEstimator(field_width=100, field_height=50)
        for frame in range(10):
            result = estimator.calculate_speed({"player": {1: {"projection": (frame * .2, 0)}}}, frame, 10)
        return dict(expected_kmh=7.2, actual_kmh=result["player"][1]["speed"])

    def known_jersey():
        classifier = ClubAssignerModel(Club("red", (190, 40, 40), (0, 255, 0)),
                                      Club("black", (25, 25, 25), (255, 255, 0)))
        return dict(red_class=int(classifier.predict((180, 45, 35))),
                    black_class=int(classifier.predict((30, 30, 30))))

    probe("mradovic.steady_metric_speed", steady_speed)
    probe("mradovic.known_jersey_centroids", known_jersey)
    probe("mradovic.insufficient_landmarks", lambda: mapping.get_homography(
        {0: (0, 0), 1: (1, 0), 2: (0, 1)}, __import__("numpy").array([[0, 0], [100, 0], [0, 50]])))

    ball = load("soccart_ball", args.soccart / "analytics/utils/ball.py")
    interpolate = load("soccart_interpolate", args.soccart / "tracking/interpolate.py")
    config = args.soccart / "analytics/config/config.yaml"

    def home_bias():
        analyzer = ball.BallPossessionAnalyzer(str(config))
        radius = analyzer.control_radius
        result = analyzer.find_possessing_player((0, 0), [(1, (.8 * radius, 0))],
                                                [(2, (.1 * radius, 0))])
        return dict(closer_team="away", selected_team=result[0], selected_player=int(result[1]))

    def player_transfer():
        analyzer = ball.BallPossessionAnalyzer(str(config))
        start = datetime(2026, 1, 1)
        analyzer.analyze_possession(start, (10, 10), [(1, (10, 10)), (2, (20, 10))], [(3, (80, 50))])
        reported = analyzer.analyze_possession(start + timedelta(seconds=1), (20, 10),
                                               [(1, (10, 10)), (2, (20, 10))], [(3, (80, 50))])
        return dict(current_player=int(reported["player_id"]),
                    event_player=int(analyzer.current_possession.player_id))

    def missing_ball():
        data = [([(-1, 0, (.1, .2))], [])]
        data += [([(1, 1, (.4, .5))], []) for _ in range(20)]
        data += [([(-1, 0, (.9, .8))], [])]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.pkl"
            path.write_bytes(pickle.dumps(([], data)))
            output = interpolate.ball_interpolate(path)
        return dict(missing_samples=20, filled_middle=list(output[10]))

    probe("soccart.nearest_player_home_bias", home_bias)
    probe("soccart.empty_team", lambda: ball.BallPossessionAnalyzer(str(config)).find_possessing_player(
        (0, 0), [], [(2, (0, 0))]))
    probe("soccart.same_team_player_transfer", player_transfer)
    probe("soccart.unbounded_ball_interpolation", missing_ball)
    probe("soccart.stationary_smoothing", lambda: interpolate.interpolate(
        [[(1, 1, (.5, .5))] for _ in range(5)], 0, "players"))

    # Integration imports a generic package named utils. Isolate it from the
    # previously loaded mradovic package; the loaded classes retain their objects.
    for name in list(sys.modules):
        if name == "utils" or name.startswith("utils."):
            del sys.modules[name]
    sys.path.remove(str(args.mradovic))
    sys.path.insert(0, str(args.soccart / "analytics"))
    integration = load("soccart_integration", args.soccart / "analytics/integration.py")
    def direct_passing():
        analyzer = integration.PassingOpportunitiesAnalyzer()
        options = analyzer.analyze_passing_opportunities(1, (10, 10), [(2, (20, 10))],
                                                       [(3, (90, 60))], 0)
        return dict(options=len(options), receivers=[p.receiver_id for p in options],
                    interpretation="geometric opportunity, not a completed pass")

    probe("soccart.direct_passing_module", direct_passing)
    probe("soccart.heatmap_missing_ball_right_pitch", lambda: integration.heatmap_integrate([
        [(-1, 0, (100, 10)), (1, 1, (10, 10))],
        [(1, 1, (10, 10))]]))
    probe("soccart.passing_integration", lambda: integration.passing_opportunity_integrate(
        [[(1, 1, (10, 10)), (2, 1, (20, 10)), (3, 2, (90, 60))]], 0, 1))
    versions = {name: subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
                for name, path in [("mradovic", args.mradovic), ("soccart", args.soccart)]}
    report = dict(versions=versions, scope="Controlled source-module probes; not full-video accuracy",
                  probes=results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
