# Demo Context — immich-photo-manager

> This context is automatically loaded when working on the immich-photo-manager project.
> It ensures any Claude session understands the demo pipeline without rediscovery.

## Quick facts

- **Demo page**: `assets/demo.html` — self-contained animated HTML, ~470 KB, base64-embedded real photos
- **Demo GIF**: `assets/demo.gif` — auto-generated, 800×640, ~3 MB, for GitHub README
- **Demo spec**: `assets/demo-script.md` — source of truth for scenes and timing
- **Recorder**: `scripts/record-demo.js` — Playwright + ffmpeg, run with `node scripts/record-demo.js`
- **Full docs**: `doc/DEMO-SYSTEM.md` — read this before making any demo changes

## Critical rules

1. **Always read `doc/DEMO-SYSTEM.md` before modifying demo files** — it has the full architecture, file map, and quality checklist
2. **Edit `demo-script.md` first**, then update `demo.html` to match — the script is the source of truth
3. **Re-record after every change**: `node scripts/record-demo.js` (or `xvfb-run` on Linux)
4. **Emoji font required**: headless Chromium needs Noto Color Emoji installed or emojis render as squares
5. **demo.gif is NOT in the .plugin file** — it's hosted on GitHub raw URL, referenced by README
6. **demo.html will be embedded as iframe on drolosoft.com** — it must work standalone

## Recording parameters (scripts/record-demo.js)

- Viewport: 800×640, zoom: 0.7, FPS: 10, duration: 20s
- To change: edit the `const` block at the top of the script

## Photo replacement workflow

1. `search_smart` on Immich with descriptive query
2. `get_asset_thumbnail` → WebP
3. Python: WebP → square crop → 200×200 JPEG → base64
4. Replace `background-image:url(data:image/jpeg;base64,...)` in `thumb-N` div
