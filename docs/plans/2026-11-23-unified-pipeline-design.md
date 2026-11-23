# Touchline unified football pipeline — approved design

User approved adopting the comprehensive reference pipelines while retaining the
Touchline coaching UI. Reference studies: `../reference-study-mradovic.md` and
`../reference-study-soccart-hudl.md`.

Video → object/keypoint detection → tracking → roles/team assignment → validated
pitch mapping → metrics/events → shared browser/export annotations.

Adopt the modular processing structure of mradovic, with SoccArt detector and
analytics techniques. Use adapters rather than running two competing trackers.
Retain source hashes, raw observations, review overrides and deletion tombstones.
Use one versioned output with frames, roles, team confidence/colors, calibrated
positions, metrics, events, coverage and per-module availability/reasons.

Target scope: team-colored tracking, keeper/referee styles, possession, passes,
speed/distance, heatmaps, minimap, geometric territory and passing opportunities.
Metric outputs require valid pitch calibration. Missing models or invalid
geometry produce unavailable states, not invented speed/positions.

Validate deterministic geometry and state rules with tests and inspect actual
Persibo frame sequences and exported video. Detection coverage is not accuracy.
CPU execution and optional external models must remain supported.
