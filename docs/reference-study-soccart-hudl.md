# Reference study: SoccArt + Hudl Sportscode Toolkit

Inspected 2026-11-23. Source-level research and asset inspection, not a successful
execution or accuracy evaluation of the external pipeline.

## Sources
- https://github.com/adityapgupta/Sports-Analysis
- Commit inspected: `f2256081e3f8257aeda5892935a983ffa6e28078`
- https://www.hudl.com/sportscode-toolkit
- Hudl Soccer ZIP and Donut Graph ZIP downloaded through the toolkit's browser links.
- Included `Sportscode Design Toolkit Read-Me.pdf` inspected.

## SoccArt: useful architecture

| Component | Observed source | Relevance |
|---|---|---|
| Separate ball/player models | `tracking/detect.py:163–164`; `models/ball.pt` (6,221,027 bytes), `models/players.pt` (33,450,316 bytes) | Highest-priority detector candidates for comparison with our generic YOLO11n |
| ByteTrack | `tracking/detect.py:166–168,191–194` | Stable identity within a shot |
| Team embeddings | `tracking/utils/team.py:13,58–62` | SigLIP embeddings + UMAP + KMeans; more than averaging jersey color |
| Pitch calibration | `tracking/utils/homography.py:53–101,104–113` | Keypoints + field lines, camera estimation, normalized pitch projection |
| Five-frame smoothing | `tracking/interpolate.py:6–25,54–83` | Symmetric weighted smoothing over common track IDs |
| Possession | `analytics/utils/ball.py:75–102` | Radius-based proximity heuristic |
| Passing opportunities | `analytics/utils/passing.py:109–123,160 onward` | Geometric lane, pressure, risk/reward heuristics; not observed successful-pass labels |
| Markers | `tracking/draw.py:17–38` | Supervision ellipse and triangle annotators; not a 3D broadcast-effects engine |

The README reports player AP@0.5 = 0.862 for its YOLOv10 model. This is an
author-reported player metric, not evidence of ball accuracy or performance on Persibo.

## Adaptation gaps

- CUDA is hard-coded in `tracking/detect.py:22` and `tracking/utils/homography.py:21`.
  Our existing environment reports MPS unavailable and currently uses CPU.
- `requirements.txt` includes machine-local Linux Conda file URLs and NVIDIA
  dependencies. It is not a portable Mac installation recipe.
- Calibration needs the separately downloaded `SV_FT_WC14_kp` and
  `SV_FT_WC14_lines` weights.
- Ball selection takes maximum confidence per frame; it is not a complete
  motion/occlusion association model.
- `ball_interpolate()` uses unrestricted pandas interpolation without explicit
  camera-cut or maximum-gap boundaries. Do not carry that behavior into Touchline.
- `find_possessing_player()` checks home within radius before away, rather than
  comparing both nearest distances. This can favor home when both are nearby.
- `analyze_possession()` updates the current event when the team stays the same,
  without updating the stored player ID on same-team transfers. Team possession
  logic must not be mistaken for an individual pass-event detector.
- Passing success probability is an exponential heuristic using distance,
  interceptors and pressure, not a calibrated learned probability.
- No root-level LICENSE found in the checked-out tree. A nested evaluation
  directory has a LICENSE; that does not establish a blanket license for the repo
  or bundled weights.

## Hudl assets inspected

Toolkit home describes assets for Sportscode users' code/output windows.
Categories: Buttons, Scripts and Graphs, Fields of Play, Backgrounds.

Soccer ZIP:
- `soccer/light@2x.png`: 900×580 RGBA, transparent background, light pitch lines.
- `soccer/dark@2x.png`: 900×580 RGBA, transparent background, dark pitch lines.
- No license text in this ZIP.
- Local reference copies: `data/reference-assets/hudl-soccer/`.

Donut Graph ZIP:
- PNG graph states for percentages 0–100 in increments of 5, light/dark variants.
- `.CWcode2SC` Sportscode code-window files.
- Two-page PDF instructions with Sportscode button-name/opacity scripts.
- These scripts are not JavaScript components. Web graphs need native SVG/Canvas
  implementation driven by our real statistics.
- Read-me: `data/reference-assets/hudl-toolkit-readme.pdf`.

The inspected home and read-me describe usage inside Sportscode. They do not
explicitly establish redistribution permission for a separate web product.
Assets are stored as references, not shipped in `web/`.

## Recommended order for Touchline

1. Benchmark a dedicated football ball detector on a short annotated Persibo
   excerpt. Compare misses, false positives, continuity, and runtime; raw detection
   coverage alone is not enough.
2. Keep detections, tracking, event inference, and overlay rendering separate.
   Preserve existing overlays until replacement data is ready.
3. Use track-aware smoothing, bounded short-gap interpolation, shot resets, and
   explicit unknown/contested possession.
4. Detect candidate passes from release → flight → stable receiver transitions.
   Infer same/opposing team only after team classification is validated.
5. Calibrate the pitch before minimap positions, physical distances, or speeds.
   Hudl's pitch art supplies a drawing surface, not calibration.
6. Keep the requested cyan carrier ring/triangle and short ball trail as our
   renderer. Inspect motion on real clips, not only screenshots.
7. Use the Hudl pitch layout as a minimap reference; confirm applicable asset
   permissions before including the supplied PNGs in a distributed product.

## Remaining verification
- External model weights not executed or benchmarked.
- External demo motion not watched; no temporal-quality claim made from stills.
- No full repository correctness audit or license determination.
