# Video intake — approved design

User approved a dedicated home page with local upload and YouTube URL intake,
preview, selectable clip range, analysis progress/retry, and saved projects.
The existing workstation remains the review/export destination.

Use a local project directory per UUID, a persisted manifest, source and prepared
MP4, analysis files and SQLite corrections. URLs identify the project explicitly;
two open tabs must never share mutable selection. Keep Persibo as a legacy entry.

Upload streams into a bounded temporary file. YouTube uses yt-dlp as a subprocess,
one video only. Validate the source using ffprobe, prepare a browser-compatible
H.264 clip via FFmpeg, then run the existing analyzer in a background subprocess.
Persist stages and errors; interrupted jobs become retryable after server restart.
Failed analysis never deletes prior results. Models are resolved from local data.

Home matches existing paper/amber tokens. Use accessible forms, native file input
with drag/drop enhancement, progress/error status and a project list. Preview is
separate from processing and exposes start/end seconds. Retry retains the source.

Verify source validation, isolation, range checks, retry, subprocess failures,
actual local upload/trim/analysis, saved project reopening, and responsive browser
states. YouTube external availability is reported separately from mocked tests.
