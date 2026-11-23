# Unified pipeline verification — work in progress

2026-11-23:
- 28 unittest cases passed after team, pitch and metrics modules were added.
- `node --check web/app.js` passed.
- `git diff --check` passed.
- Live app reopened through una; screenshot: `data/unified-pipeline-pending.png`.
  This captures pending state, not proof of colored tracking.

Implemented:
- Versioned sample enrichment, metadata-based roles and per-track jersey groups.
- Player rendering independent of event counts, team-color rings, role styles,
  track IDs, separate cyan owner/trail.
- Optional pose-landmark adapter with explicit metric layout.
- Validated homography and metric motion, dwell heatmaps, grid territory,
  geometric passing lanes, time-weighted possession.
- Module availability UI and conditional pitch map/speed labels.

Pending evidence:
- Jersey enrichment on cached actual Persibo frames is running separately to
  `data/team-preview.json`; it has not been published as production output.
- Football-specific detector run started before the latest pipeline edits;
  its output needs a finalize/reuse pass using current code after completion.
- No matching landmark weights available locally, so no actual-video speed,
  distance, heatmap, minimap or territory accuracy has been established.
- Full analytical UI, shared all-player export, responsive and motion inspection
  remain outstanding. Existing reviewed-event export tests still pass.

Actual jersey proof:
- Baseline enrichment finished: 750 samples, 140 observed ball samples accepted,
  11 interpolated, 1 possession candidate, 0 passes.
- Initial extractor incorrectly discarded dark jerseys; relaxed dark-pixel grass
  rejection and used chromaticity to avoid separating sun/shadow red kits.
- Palette now separates dark green/black (`#243e1b`) and red (`#ae554a`).
- `data/team-proof-15s.jpg` still reveals an incorrectly assigned referee in
  generic person tracks. This baseline output has NOT been published.
  Role-aware football detector output is required for the next proof.

Do not mark the overall adoption complete based on the deterministic tests.

Football-model completion and publication:
- Detection run completed: 750 samples, 286 with candidates, 179 accepted
  observations, 18 interpolations, 4 possession candidates, 0 passes.
- Re-finalized current football detections through the team/metric schema.
- Inspected `data/football-team-proof-15s.jpg`: visible red and dark-shirted
  tracked players have distinct team groups; several players remain undetected.
- Published enriched output atomically after matching source identity. Previous
  result retained as `data/football-before-team-enrichment.json`.
- Live una snapshot confirms four events and the team-color annotation notice.
  `data/live-team-15s.png` shows colored rings in the visible video portion.
- This detector run predates role metadata preservation, so goalkeeper/referee
  styling is implemented but not verified in these published samples.
- Latest full suite: 30 tests passed. No actual-video metric calibration yet.

Carrier-ring overlap fix:
- Team ring layer is replaced by the cyan marker for the active owner.
- Live inference/event/draft carrier markers deduplicate by track; later layers
  have priority. Labels remain visible.
- Removed the extra cyan glow ellipse.
- JavaScript syntax check passed.
- Live browser at possession 8.9s: one carrier group, one carrier ellipse,
  and zero team ellipses for track 21 (una check PASS).
- Subsequent editor-close/scroll/screenshot batch failed with CDP timeouts.
  No post-fix video screenshot was obtained; the earlier DOM count checks passed.
