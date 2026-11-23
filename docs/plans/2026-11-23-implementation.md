# Football Coaching Workspace Implementation Plan

> Execute sequentially in this session using the executing-plans skill. No delegation is required.

**Goal:** Run a local coaching workspace for the existing Persibo clip with synchronized overlays, editable pass events, and annotated video export.

**Architecture:** A loopback Python HTTP server serves source media and a browser frontend. SQLite stores reviewed events independently of the imported CSV observations. An export worker renders annotations and uses FFmpeg to preserve timing and audio.

**Tech Stack:** Python 3.11, SQLite, OpenCV, FFmpeg, browser HTML/CSS/JavaScript and SVG; existing local CV environment.

---

### Task 1: Project data and timing
**Files:** `app/data.py`, `tests/test_data.py`, `README.md`.
1. Confirm source video width, height, fps, duration, and audio with ffprobe.
2. Add a CSV import test for frame two at 30fps, missing ball observations, and neutral team labels.
3. Run `python -m unittest discover -s tests -v`; verify new tests fail before implementation.
4. Implement CSV import and explicitly map frame indices to video time. Preserve gaps rather than assigning the ball to the nearest player.
5. Re-run targeted tests.

### Task 2: Project storage and local service
**Files:** `app/store.py`, `app/server.py`, `tests/test_store.py`, `tests/test_server.py`.
1. Test event insertion, update, persistence after reopening, and invalid timestamps.
2. Implement SQLite event storage with parameterized SQL and input validation.
3. Serve only configured project media and frontend assets on `127.0.0.1`; support byte-range video requests.
4. Expose project metadata, observations, event CRUD, and export-job status.
5. Verify a ranged media request, invalid path rejection, and persistence tests.

### Task 3: Review workspace
**Files:** `web/index.html`, `web/app.js`, `web/styles.css`.
1. Load frontend design guidance before implementation.
2. Build a video-first layout with project identity, playback controls, timeline and event inspector.
3. Synchronize SVG overlays to media timestamps; handle video letterboxing with an explicit source-image viewBox.
4. Display team clusters and track IDs without pretending they are verified player identities.
5. Open the local app through una and verify playback, seeking, overlay positions, keyboard controls and a narrow viewport.

### Task 4: Coach corrections
**Files:** `web/app.js`, `app/events.py`, `tests/test_events.py`.
1. Test `0 <= start < end <= duration` and source-normalized coordinates in `[0,1]`.
2. Add release/reception marking, selectable outcomes, notes, possession intervals and coach-confirmation controls.
3. Save via the local API and verify reload restores edits.
4. Show confirmed completion rate only when its denominator is nonzero; list unknown and unreviewed events separately.
5. Check that adding an event on a letterboxed video records the correct video coordinates.

### Task 5: Export
**Files:** `app/export.py`, `tests/test_export.py`.
1. Create a small synthetic video fixture with known event timestamps and an audio track.
2. Test overlay presence within its interval and absence outside it.
3. Render confirmed overlays at source timing; encode H.264/yuv420p with FFmpeg, retain source audio when present.
4. Store exports with unique names, surface worker errors, and provide a download link.
5. Verify output duration, codec, frame rate and audio with ffprobe; inspect matching browser/export frames.

### Task 6: First-clip acceptance
**Files:** `README.md`, `docs/first-clip-review.md`.
1. Launch locally using the existing Python 3.11 environment.
2. Load the actual Persibo clip and imported observations.
3. Verify creation, correction, deletion and persistence of a manually marked pass.
4. Export a reviewed interval and inspect it.
5. Record observed limitations and commands to relaunch. Report generated artifacts separately from analytical accuracy.

## Acceptance
- Source clip plays locally and timeline seeks correctly.
- Imported observations and coach-confirmed events are distinguishable.
- Coach can mark and correct possession and pass outcomes.
- Edits survive reload; unknown events do not inflate completion rates.
- Export matches confirmed overlays and preserves available audio.
- No invented physical metrics or automatic pass-quality claims.
