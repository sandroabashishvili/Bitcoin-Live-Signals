# Current Status

Updated: 2026-08-26

## Current behavior

- Daily generation reads original news automatically; no prepared summaries.
- Word-budget and pixel-fit excerpts end in `…`; SRT matches displayed text.
- Default 23-second fixed timeline: intro 1.5 + three stories 6 each + outro 3.5.
- No automatic duration growth. Hard duration range 10–60 seconds and 1–5 stories;
  invalid combinations are rejected before rendering.
- Compact fixed slots, larger description, eased text entrance, revealing
  orange divider, muted-amber story count and soft-white elapsed-time line.
- Frame zero contains the full intro heading/date (no fade-in). Outro has no fade
  to black; QR remains, with SmartSignalHub above the product URL (not portfolio).
- Historical manual editorial overrides remain optional for backward compatibility;
  the daily example no longer uses them.

## Verification

- 38 passing focused tests cover truncation, actual raster content, SRT, timing limits,
  animation and 1080p/720p geometry.
- August 24 stories 1/6/9 previewed from original source, without overrides.
- A 720p/10 FPS smoke MP4 passed a full decode: exactly 23 seconds, H.264/AAC.
  Sampled encoded frames confirm entrance/reveal animation and progress changes.
- After the cover/outro polish, a separate 5-second 720p intro/outro encode was
  checked: the decoded first frame contains the full title/date, and the final
  QR/product address is visible. The existing full August 26 MP4 is not replaced.
- Full-quality 1080p encoding remains user-run; previous video is unchanged.

## Limits

Excerpts are not automatically written summaries or fact-checked reporting.
Reading-time budgeting is heuristic. Ellipses make omissions visible but cannot
guarantee that omitted context is unimportant. Review the preview before sharing.
MoviePy/ImageIO deprecation warnings remain non-blocking.

Changes are local and newer than the August 24–25 migration backups.
No new backup, external publishing, or dependency installation was performed.
