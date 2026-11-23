# Automatic possession and cyan tracking implementation plan

**Goal:** Automatically propose possession and pass events from the Persibo clip, with bounded, smoothly interpolated cyan overlays.

**Approved design:** Cyan ground ellipse and overhead triangle on the inferred carrier; short fading ball trail. Processing is offline. Detection gaps and camera cuts terminate tracks instead of inventing ownership. Machine events remain unreviewed estimates.

**Architecture:** Cached full-frame player detections and tiled ball detections feed conservative temporal association. Offline smoothing is confined to continuous tracks. Generated candidates are merged with coach edits using stable IDs, without overwriting corrections. The browser renders time-indexed tracks; export uses the same sampled geometry.

**Tech Stack:** Existing Python 3.11, Ultralytics YOLO11n, OpenCV, SQLite, vanilla JS/SVG.

## Tasks
1. `app/automatic.py`, `tests/test_automatic.py`: test short-gap interpolation, long-gap/cut suppression, ambiguous ownership, and possession-to-pass transitions. Build deterministic inference without ML dependencies.
2. `app/analyze.py`: cache high-resolution player and tiled ball detections, scene segments and bounded ball associations; run on the actual clip. Record coverage and processing parameters, not accuracy claims.
3. `app/server.py`, `app/store.py`: serve cached analysis and merge generated events with persistent coach edits and deletion tombstones. Preserve reviewed-only statistics.
4. `web/app.js`, `web/index.html`: cyan carrier ring, triangle, short fading ball trail; automatic event labels and uncertainty status. Review remains available as correction.
5. `app/export.py`: render reviewed automatic trajectories using the cached samples; preserve audio and frame timing.
6. Run Python tests, JS syntax checks, browser review and inspect actual-source evidence. Report missing detections and candidate counts honestly.

## Acceptance
- No ring when ownership is unknown or tracking is stale.
- No trail or event across a camera cut or long missing-ball interval.
- No automatic event counts as reviewed.
- Manual correction/deletion survives reload and does not modify cached detector output.
- Analysis is tied to source identity and detector settings.
- No claims of confirmed pass accuracy, team identity, physical speed or calibrated pitch projection.
