# Unified Football Pipeline Implementation Plan

> Execute sequentially in this session using executing-plans.

**Goal:** Adopt a comprehensive modular analysis engine behind the existing Touchline UI.

**Architecture:** One tracking stream enriched with roles, teams, calibrated
coordinates and analytical outputs. Model adapters feed shared sample contracts;
UI and export consume the same evidence with explicit unavailable states.

**Tech Stack:** Python 3.11, OpenCV, NumPy, Ultralytics, Supervision, SQLite,
vanilla JavaScript/SVG and FFmpeg.

## Checklist
- [x] Inspect reference pipelines and current integration gaps.
- [x] Record approved design.
- [ ] Team/role enrichment and versioned module status.
- [ ] Shared all-player overlay independent of event availability.
- [ ] Pitch-model adapter and validated mapping.
- [ ] Speed/distance, heatmaps, territory and passing-lane modules.
- [ ] UI analytical views and export consistency.
- [ ] Actual Persibo verification and documented remaining model gaps.

## Task 1 — Team and role contract
Files: create `app/teams.py`, `tests/test_teams.py`; modify `app/analyze.py`.
1. Test temporal voting, unknown crops and role exclusions.
2. Extract jersey features from central upper-body crops; reject grass/background.
3. Fit two team clusters from outfield observations; associate per shot/track.
4. Preserve roles from detector metadata; avoid numeric class assumptions.
5. Include palette, confidence and module status in versioned automatic output.
Run: Python environment `-m unittest discover -s tests -p test_teams.py -v`.
Expected: stable colors despite isolated conflicting observations; unknown remains unknown.

## Task 2 — Render tracking as its own layer
Files: `web/app.js`, `web/index.html`, `app/export.py`.
1. Consume sampled players regardless of event count.
2. Interpolate only matching track/segment within .21 seconds.
3. Draw team rings, T-prefixed IDs, keeper double rings, referee dashes.
4. Draw cyan carrier highlight separately from team identity.
5. Preserve legacy observations when new samples are unavailable.
Check: node --check web/app.js; inspect Persibo at 5, 15, 30 and 60 seconds in una.

## Task 3 — Calibration adapter
Files: create `app/pitch.py`, `tests/test_pitch.py`; modify `app/analyze.py`.
1. Declare the expected landmark order and metric pitch dimensions.
2. Accept optional matching keypoint weights; resolve their actual availability.
3. Fit RANSAC homography with >=4 nondegenerate correspondences.
4. Reject missing, singular and high-error transforms; reset per shot.
5. Attach valid projected feet and calibration evidence to samples.
Tests: known synthetic transform, outliers, degenerate geometry and shot boundaries.

## Task 4 — Analytics
Files: create `app/metrics.py`, `tests/test_metrics.py`.
1. Calculate speed/distance from timestamps and metric positions, reject large gaps.
2. Aggregate time-weighted possession including unknown.
3. Accumulate pitch heatmaps using observed dwell time.
4. Derive geometric nearest-player territory and passing lane obstruction.
5. Label opportunities as heuristics; do not conflate them with completed passes.
Tests: known motion, irregular sample timing, unknown teams and missing calibration.

## Task 5 — Workstation and export
Files: `web/index.html`, `web/styles.css`, `web/app.js`, `app/export.py`.
1. Display module availability and reasons.
2. Add minimap and analytics views driven only by validated metrics.
3. Use identical role/team conventions in browser and export.
4. Preserve reviewed-only event export behavior and audio.
Checks: responsive screenshots, seek/play, correction persistence, actual export frames.

## Task 6 — Verification
Files: `README.md`, `docs/unified-pipeline-verification.md`.
1. Run full unittest discovery and JavaScript syntax checks.
2. Process real Persibo, inspect representative annotated samples and short motion.
3. Record model hashes, timings, coverage, team ambiguities and unavailable modules.
4. Never describe missing keypoint weights or unevaluated metrics as delivered.
