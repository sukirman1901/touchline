# First-clip verification — 2026-11-23

## Observed
- Source inspected with ffprobe: 75.000 seconds, 1280×720, H.264, 30 fps, AAC.
- Eight Python unit/integration tests passed: frame timestamp, event validation,
  statistics denominator, SQLite persistence/update/delete, media byte ranges,
  path restriction, overlay time interval, export duration/audio.
- Browser checked using una at `http://127.0.0.1:8876`.
- Video reached readyState 4; playback advanced from 2 s to 18.416762 s.
- UI-created fixture pass saved, survived page reload, and opened through the
  event row. It was explicitly named “UJI TEKNIS — bukan kejadian pertandingan”.
- Changing fixture outcome to unknown produced zero known reviewed outcomes,
  one unknown outcome, and no completion percentage.
- Fixture deleted through the UI. Native confirmation was stubbed to accept only
  for this deletion test; reloading restored normal browser behavior.
- After reload/data load, event count was zero.
- UI export for source seconds 3–5 completed. ffprobe reported H.264 + AAC,
  30 fps, exactly 2.000 seconds.
- Export frame inspected: test arrow/ring present. Browser SVG source and target
  were (320,468) and (768,324), matching normalized fixture anchors.
- Export fixture is a rendering test, NOT a factual annotation of an actual pass.

## Responsive evidence
Same-origin iframe viewports used because the automation browser viewport could
not be resized with `window.resizeTo`. Layout measurements:

| CSS viewport | Document scrollWidth | Main columns | Primary action width |
|---|---|---|---|
| 320 | 320 | 296 px | 262 px (full content width) |
| 768 | 768 | 720 px | 133.34 px |
| 1024 | 1024 | 670 + 290 px | 133.34 px |
| 1440 | 1440 | 1026 + 326 px | 133.34 px |

No page horizontal overflow measured. Desktop composition was visually inspected
in a scaled 1440 px iframe; this is not a full-resolution desktop screenshot audit.

## Conventions check
- Tokens: project graphite/amber system in `web/styles.css`; waiver from pack
  preset scoring to follow the supplied amber broadcast reference and a neutral
  video-editing surface.
- Icons: intentional text-first controls; no third-party icon runtime.
- States: loading, empty, server/form errors, saving, export progress and success.
- Responsive: 320/768/1024/1440 measured; primary actions full-width below 768.
- Hierarchy: video primary; one amber “Tandai kejadian” action at rest.
- Typography: one h1, h2 section titles, h3 supporting titles; system sans + mono.
- A11y: labelled fields, visible focus, native dialogs/selects, status regions,
  keyboard playback and coordinate-entry alternative. Not a full WCAG audit.
- WebGL: n/a.
- Shell: logo + local status + help; no account/theme controls in local-only MVP.
- Landing: n/a.
- Motion: restrained hover transitions with reduced-motion support; video overlays
  follow media time, not decorative animation.
- Foundations: video/timeline column paired with inspector; stacked below 851 px.
- Control geometry: shared radius, pending and keyboard-focus states; native
  selects retained for offline robustness and keyboard access.

## Coverage limits
No model fine-tuning, calibrated geometry, automatic pass extraction, ground-truth
accuracy measurement, full-match load test, screen-reader audit, or cross-browser
matrix. Possession ring motion is coach-authored linear interpolation. Player IDs
are not verified identities and camera cuts are not automatically segmented.
