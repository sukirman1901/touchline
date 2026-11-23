# Workstation UI review

## Changes
- Replaced the card-heavy dark shell with neutral application chrome and a dark video viewer.
- Reduced header height, removed promotional copy, and moved events into the inspector.
- Added a source-frame filmstrip, separate event lanes, local SVG icons, and fullscreen control.
- Retained amber as the primary action and annotation accent.

## Verification
- Eight Python tests passed after the redesign.
- `node --check web/app.js` passed.
- Browser measurements at 320, 768, 1024 and 1440 px: document width equalled viewport width.
- Visually inspected desktop overview, desktop editor, and mobile editor screenshots.
- Editor opened with labelled fields and visible save action. Mobile primary action spans the panel.
- Final filmstrip/export interaction attempt timed out; subsequent una invocation reported a locked browser profile. Those new interactions are not claimed verified.

## Conventions
Project semantic color/spacing tokens; locally vendored Reicon glyphs; one primary action per panel; semantic heading hierarchy; explicit empty/loading/error states; labelled controls and focus styles; reduced-motion support. No WebGL or landing-page layout. Full accessibility and cross-browser audits remain outside this pass.
