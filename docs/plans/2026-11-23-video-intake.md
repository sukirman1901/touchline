# Video Intake Implementation Plan

**Goal:** Start Touchline from upload or YouTube, then preview, analyze and review.
**Architecture:** Persisted per-project directories with asynchronous import and
analysis jobs. Project-qualified URLs isolate workspace state and exports.
**Tech Stack:** Python HTTP server, FFmpeg/ffprobe, yt-dlp CLI, existing YOLO
analyzer, vanilla JS/CSS.

## Tasks
- [ ] Add `app/projects.py`: manifest storage, bounded upload, YouTube validation,
  background import/trim/analyze, retry and restart recovery.
- [ ] Add `tests/test_projects.py`: rejected URLs/ranges, upload validation,
  duplicate jobs, persisted sources and isolated contexts. Run failing tests,
  implement, then run `python -m unittest discover -s tests -p test_projects.py`.
- [ ] Integrate project routes in `app/server.py`; keep legacy tests and project
  isolated media/events/export. Server must boot with no Persibo input files.
- [ ] Add `web/home.html`, `home.js`, `home.css`: source form, preview/range,
  progress/retry, project list. Reuse existing visual tokens and SVG icons.
- [ ] Adapt `web/app.js`/`index.html`: project URL parameter, dynamic names,
  duration/timeline/media, export storage key; no Persibo content for new inputs.
- [ ] Verify a real small fixture through upload/clip/analysis, failed YouTube
  input, persistence, legacy reopening, browser layout at 320/768/1024/1440.
- [ ] Update README/dependency instructions. Run Python suite, JS syntax,
  diff checks; deploy local server and verify the new home route.

Execution stays in this session, sequentially; no delegated agents.
