# mradovic38/football-analysis: detailed integration study

Source: https://github.com/mradovic38/football-analysis
Inspected local checkout and Touchline source on 2026-11-23.
This is source inspection, not an execution/accuracy evaluation of the reference.

## Why Touchline currently draws white rings

`web/app.js:137–146` renders legacy observations whenever automatic events are
empty. Every player receives hard-coded `#e8eeea`; balls use `#fff`.
The renderer does not consume the new `automatic.players` stream.
`app/analyze.py` emits track, position, height and width, but no team/club color
or retained player/goalkeeper role. Referees are excluded from its player classes.
Consequently this is a missing classification-to-rendering path, not a CSS bug.
The live page also reports zero events and neutral player detections.

Player visibility is incorrectly coupled to event availability: once events
exist, the general player-ring layer disappears. All-player tracking should be
independent of possession/pass events.

## Reference data flow

`annotation/football_video_processor.py:88–128`:

1. Object detector and pitch-keypoint detector process frames.
2. ByteTrack assigns object IDs.
3. ClubAssigner reads jersey crops and attaches club and club_color.
4. ObjectPositionMapper computes homography and projects feet.
5. BallToPlayerAssigner selects nearby possession candidates.
6. SpeedEstimator uses projected displacement and frame timing.
7. JSON writer saves tracks; annotators draw the result.

## Team classification and annotation

`club_assignment/club_assigner.py`:
- Two club palettes are supplied explicitly in main.py, including goalkeeper
  jersey colors. These are not automatically discovered club identities.
- Uses the upper half of each bounding box, HSV grass masking and two-cluster
  KMeans. Corner-majority cluster is treated as background.
- Chooses the nearest configured RGB centroid. Goalkeepers use a separate
  centroid set, then receive their club's outfield annotation color.
- Reclassifies each frame, with no track-level voting or ambiguity rejection.
- Green-kit handling needs care: masking the grass hue can remove jersey pixels.

`annotation/object_annotator.py`:
- Color comes from club_color, converted RGB → OpenCV BGR.
- Players: open ellipse at the feet, from -30° to 240°.
- Goalkeepers: double open ellipse.
- Referees: dark dashed ellipse.
- Track ID sits in a filled team-color rectangle; it is NOT a jersey number.
- Possessor: overhead team-color triangle; ball: a separately colored triangle.
- Text contrast is selected from color luminance; speed appears beneath the ID.
- Ellipse width follows the box; its vertical radius is fixed at 20 pixels.

## Calibration, minimap and speed

- `tracking/keypoints_tracker.py`: 32 pitch landmarks, confidence filtering,
  luminance equalization, square 1280 input, fixed scaling back to 1920×1080.
- `position_mappers/homography.py`: cv2.findHomography using default method,
  then matrix exponential averaging (90% current, 10% previous).
- No explicit minimum-four-point, degeneracy, reprojection-error, missing-H,
  denominator or camera-cut handling in these functions.
- `ObjectPositionMapper` uses bounding-box feet for all object categories.
  A ball centroid and airborne uncertainty deserve separate treatment.
- `ProjectionAnnotator`: team-colored player dots, goalkeeper squares,
  referee marks, ball cross, Voronoi regions.
- Voronoi is geometric nearest-player territory, not a validated tactical
  control probability.
- `SpeedEstimator`: projected displacement → meters → km/h, five-sample mean.
  Defaults to 100×50 m and clamps speed to 40 km/h. Missing projection is shown
  as zero. Touchline should use unknown instead and reject bad calibration.

## Possession caveats observed in source

- Uses projected distance, with max_ball_distance=10 in pitch-image units.
- Configures 4-second possession grace and 2-second missing-ball grace at
  default 30 fps. This may visually retain an owner without current evidence.
- Calls add_possession twice in several successful assignment branches, while
  some neutral branches call once. This can bias the displayed proportions.
- The no-nearby-player case is nested under best_ball_key being non-null, making
  intended grace handling incomplete for valid balls far from all players.
- Processor supplies keypoint 24 as the second penalty-point exclusion, but
  main.py labels keypoint 21 as the right penalty dot and 24 as a goal-line point.
- This is possession assignment, not a complete pass-release/flight/reception
  or pass-success classifier.

## Portability and prerequisites

- models/weights referenced by main.py is absent in this checkout; training
  notebooks are present. Existing SoccArt weights have a different class order:
  class IDs must be resolved by model metadata, not copied numeric indices.
- ObjectTracker detection uses conf=.5 in main.py before a downstream .05 ball
  threshold. The downstream threshold cannot recover detections already removed.
- Source assumes 1920×1080 in object/keypoint scaling and composition.
  Persibo is 1280×720; derive dimensions from the source instead.
- Root MIT license exists; model/dataset/dependency terms are separate.

## Concrete Touchline integration requirements

1. Preserve role and team confidence with each player sample.
2. Extract jersey features and establish two consistent team palettes; use
   temporal voting per track and an explicit unknown state.
3. Render current player samples independently of the event list. Use team
   colors, track labels, double keeper rings and distinct referee marks.
4. Keep cyan for the carrier highlight/ball trail, without recoloring every
   player's team ring cyan.
5. Interpolate positions only across short gaps within the same track and shot.
6. Feed the same annotated sample schema to browser and export rendering.
7. Add pitch landmarks, validated homography and metric dimensions before speed
   or minimap positions. Hide invalid metrics instead of showing fabricated zero.
8. Count possession by elapsed time with one state update per sample; preserve
   contested/unknown periods and separate predicted persistence from observation.

## Acceptance checks

- On the same Persibo frame, distinguish both teams using actual jersey evidence.
- Colors remain consistent for a track through motion and brief occlusion.
- Unknown/team ambiguity remains visible rather than forced into a team.
- Player rings still render when automatic events exist.
- Role shapes, track labels and carrier highlight convey different meanings.
- Camera cuts reset identity/calibration-dependent history.
- Real-video motion and export must be inspected; unit tests alone do not prove
  visual stability or detector accuracy.
