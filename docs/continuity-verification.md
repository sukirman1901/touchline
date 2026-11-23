# Continuity implementation — 2026-11-23

## Implemented

- Short same-team, same-role tracklet stitching with motion prediction,
  ambiguity rejection, scene boundaries and raw-ID provenance.
- Team assignment requires at least 75% agreement among jersey observations.
- Offline possession bridging requires observed same-player endpoints, a gap
  at most 0.21 seconds and player observations throughout. Contested balls,
  observed releases and trailing missing detections are not bridged.
- Possession candidates require three observed owner samples; inferred samples
  alone cannot qualify an event. Output records ownership evidence counts.
- Optional tiled ball benchmark, separate from production inference.

## Verification

- `python -m unittest discover -s tests -v`: 42 passed.
- `node --check web/app.js`: passed.
- `git diff --check`: passed.
- Cached Persibo replay: `data/continuity-preview.json`.
- Track count: 174 → 172. Links: raw 64 → 39 at 13.8s and 68 → 63 at
  14.3s. Before/after frames saved to `data/continuity-link-proof.jpg`.
- Unassigned player observations: 231 → 317 following stricter jersey voting.
- Possession candidates: 4 → 3; surviving intervals remain 0.3 seconds each.
  The fourth candidate no longer meets the observed-evidence minimum.
- Ownership evidence: 12 observed samples, 0 interpolated, 0 bridged.
  The bridging implementation therefore has synthetic regression coverage,
  but did not improve possession continuity on this clip.
- Ball coverage unchanged: 179 accepted observations and 18 interpolations
  from 750 sampled frames. Scene count remains one and needs validation.

## Detector experiment

Same model, confidence 0.15, 18 fixed timestamps, input size 640:

| Mode | Frames with candidates | Wall time |
|---|---:|---:|
| Whole frame | 6/18 | 8.92s |
| Four overlapping crops | 8/18 | 13.85s |

Outputs: `data/ball-benchmark-full640/` and `data/ball-benchmark-tiled/`.
Candidate presence is not accuracy. The first tiled review sheet still shows
missing detections and multiple candidates; this does not establish a better
production detector. Timing is one local run, not a robust performance estimate.

## Publication status

Backend changes are implemented. The replay is a preview, not promoted to
`data/automatic.json`: it does not resolve intermittent possession. Published
observations remain available. Comprehensive upstream adoption, calibrated
analytics and full-video motion validation remain unfinished.

## Follow-up: detector versus association failure

- Whole-frame input 1280: 6/18 frames with candidates, 44.71 seconds.
  Input 640: 6/18, 8.92 seconds. These counts do not measure accuracy.
- Inspected source frames 9.1–9.6s: the detector finds the released ball at
  9.4 and 9.5s, but the previous-position displacement gate rejects it.
  Evidence: `data/ball-release-diagnostic.jpg`.
- Tested an offline, opt-in recovery policy requiring a confident seed and
  two subsequent unique nearby observations, with a new ball trajectory ID.
  A velocity alternative preserves subsequent observations of the moving ball.
- Experimental replay: 184 accepted observations versus 179 baseline, with
  all prior sample timestamps retained. However, manual inspection of all
  five additions found only two balls and three sock/foot false positives.
  Evidence: `data/reacquisition-review.jpg`; structured decisions:
  `data/reference-comparison/reacquisition-review.json`.
- Therefore `experimental_ball_reacquisition` defaults to false. This result
  is a rejected promotion, not a completed possession fix.
- Ball trajectory IDs and discontinuity guards are active independently:
  Python sampling, pass inference, browser trails and export refuse to connect
  different trajectories. Older data without these IDs remains supported.
- Remaining root causes include small/blurred ball misses and persistent
  sideline false positives. Raising resolution or accepting more temporally
  persistent candidates did not solve these. Next detector evaluation needs
  labeled ball and hard-negative crops, including the sideline sock examples,
  plus validation of shot/play-area context before promoting a replacement.
- Final checks: 46 Python tests pass; JavaScript syntax and diff checks pass.
  Default replay retains 179 accepted + 18 interpolated observations; opt-in
  replay records 184 + 18. Both have three possession candidates and zero passes.

## Publication follow-up

The user confirmed the website still looked unchanged. Live browser inspection
confirmed four old events and no `track_links` or ball trajectory IDs.
Published the default (non-experimental) continuity output atomically to
`data/automatic.json`, after checking the video hash. Previous output is saved at
`data/automatic.before-continuity-20261123-181402.json`.

Verified in the reloaded live page:
- Three events, two track links, experimental recovery false, ball track IDs.
- At 13.8 seconds the rendered SVG contains player track 39, not raw track 64.
- Browser screenshot: `data/published-continuity-browser.png`.

This supersedes the earlier preview-only publication status. It does not claim
stable possession or completion of the broader analytical feature adoption.
