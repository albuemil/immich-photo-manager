# immich-photo-manager — Development & Release Workflow

> Reference document for the full plugin lifecycle: develop → demo → build → test → publish.
> Read this at the start of any session that involves modifying or releasing the plugin.

## Quick Reference

```bash
# Full release pipeline (run from repo root)
node scripts/record-demo.js       # 1. Record demo GIF
./build-plugin.sh                 # 2. Build .plugin file
# Then: drag .plugin into Cowork → Settings → Plugins to test
```

---

## 1. Development

### Repo structure

```
immich-photo-manager/
├── .claude-plugin/          # Plugin metadata (plugin.json, icon)
├── assets/
│   ├── demo.html            # Self-playing animated demo page
│   ├── demo.gif             # Generated GIF for README/marketplace
│   ├── demo-script.md       # Source of truth for demo scenes
│   └── icon.png             # Plugin icon
├── commands/                # Slash commands (/cleanup, /setup, etc.)
├── skills/                  # 11 skills (album-manager, photo-search, etc.)
├── scripts/
│   └── record-demo.js       # Automated demo GIF recorder
├── src/                     # Python MCP server (immich-mcp)
├── build-plugin.sh          # Plugin packager
├── .mcp.json                # MCP server config (local dev)
├── .mcp.json.example        # MCP config template for users
├── .env                     # Local Immich credentials (DO NOT COMMIT)
├── .env.example             # Credentials template for users
└── README.md                # GitHub page with demo GIF
```

### Adding/modifying a skill

1. Create or edit `skills/<skill-name>/SKILL.md`
2. Update the skill description (first paragraph = trigger detection)
3. Test in Cowork by saying something that should trigger it
4. Update `assets/demo-script.md` if the demo needs to reflect the change

### Adding a command

1. Create `commands/<command-name>.md`
2. Commands appear as `/<command-name>` in Cowork
3. Keep the file short — it's loaded into context on every invocation

---

## 2. Demo (demo.html → demo.gif)

### Editing the demo animation

1. **Edit `assets/demo-script.md`** — this is the source of truth for what the demo shows
2. **Update `assets/demo.html`** to match (or ask Claude to regenerate from the script)
3. **Test locally**: open `demo.html` in a browser to preview the animation

### Key files

| File | Purpose |
|------|---------|
| `assets/demo-script.md` | Scenes, timing, visual spec — edit this first |
| `assets/demo.html` | Self-contained HTML with base64 photos, CSS animations, JS timing |
| `scripts/record-demo.js` | Playwright + ffmpeg recorder |
| `assets/demo.gif` | Output — referenced by README.md |

### Recording the demo GIF

**Prerequisites** (one-time setup):

```bash
npm install playwright
npx playwright install chromium
# macOS: brew install ffmpeg
# Linux: apt install ffmpeg xvfb
# Linux also needs emoji font: apt install fonts-noto-color-emoji
#   (or user-install: download NotoColorEmoji.ttf to ~/.local/share/fonts/)
```

**Record:**

```bash
# macOS (has a display):
node scripts/record-demo.js

# Linux / CI / Cowork sandbox (headless):
xvfb-run node scripts/record-demo.js
```

**What the script does:**
1. Serves `assets/demo.html` on a local HTTP server (port 9876)
2. Opens headless Chromium (800×640, 2× retina, dark mode, zoom 0.7)
3. Records the full ~20s animation via Playwright's video recorder
4. Converts WebM → GIF with ffmpeg two-pass palette optimization
5. Saves to `assets/demo.gif`

**Tuning** (edit `scripts/record-demo.js`):

| Variable | Default | Description |
|----------|---------|-------------|
| `WIDTH` | 800 | Viewport width |
| `HEIGHT` | 640 | Viewport height |
| `WAIT_MS` | 20000 | Recording duration (ms) |
| `TRIM_START` | 0.3 | Trim dark intro (seconds) |
| `GIF_FPS` | 10 | GIF frame rate |
| `MAX_COLORS` | 96 | GIF palette size (lower = smaller file) |
| `zoom` | 0.7 | CSS zoom applied to page (in `page.evaluate`) |

**Target:** < 5 MB, landscape orientation (wider than tall), suitable for GitHub README.

---

## 3. Build the .plugin file

```bash
./build-plugin.sh           # auto-reads version from .claude-plugin/plugin.json
./build-plugin.sh v1.1.0    # or specify version explicitly
```

**Output:** `immich-photo-manager-v1.1.0.plugin` (a zip archive)

The build script:
1. Compiles the Go MCP server binary (if Go is installed)
2. Packages all skills, commands, assets, scripts, and config into a `.plugin` zip
3. Excludes dev artifacts (demo-script.md, __pycache__, .DS_Store)

**Important:** Always rebuild the `.plugin` after:
- Changing any skill or command
- Updating demo.gif
- Modifying README.md
- Changing .mcp.json.example or .env.example

---

## 4. Test locally

### In Cowork (recommended)

1. Open Cowork on your Mac
2. Go to Settings → Plugins
3. Drag the `.plugin` file into the plugins area
4. Start a new session and test:
   - `/immich-status` — verify server connection
   - `/setup` — test the setup flow
   - `show me my Barcelona photos` — test photo search + gallery
   - `/create-album Rome` — test album creation
   - `/cleanup` — test screenshot/duplicate detection

### In Claude Code CLI

```bash
# Install the plugin
claude plugin install ./immich-photo-manager-v1.1.0.plugin

# Or unzip manually to the plugins directory
unzip immich-photo-manager-v1.1.0.plugin -d ~/.claude/plugins/immich-photo-manager/
```

### Testing checklist

- [ ] `/immich-status` connects to Immich server
- [ ] Photo search returns results with thumbnails
- [ ] Gallery HTML opens in browser with working selection
- [ ] Album creation works end-to-end
- [ ] demo.gif plays correctly in README (check GitHub after push)
- [ ] Plugin icon displays correctly

---

## 5. Publish

### Push to GitHub

```bash
git push origin main        # juanatsap/immich-photo-manager
git push drolosoft main     # drolosoft/immich-photo-manager (public)
```

**Note:** SSH keys are required. Push from your local terminal, not from Cowork sandbox.

### Publish to Claude Code Plugin Registry

(TODO: Document registry submission process once available)

The plugin needs to be discoverable via:
```
claude plugin search immich
```

---

## 6. Release Checklist

Use this for every release:

- [ ] All skills tested and working
- [ ] `demo-script.md` updated if features changed
- [ ] `demo.html` updated to match script
- [ ] `demo.gif` re-recorded: `node scripts/record-demo.js`
- [ ] GIF is < 5 MB and looks correct
- [ ] `.plugin` rebuilt: `./build-plugin.sh`
- [ ] Tested locally in Cowork (drag & drop install)
- [ ] Version bumped in `.claude-plugin/plugin.json`
- [ ] README.md reflects current features
- [ ] `git push` to both remotes
- [ ] Plugin registry updated (if applicable)

---

## Troubleshooting

### Emojis show as squares in demo.gif
Install Noto Color Emoji font before recording:
```bash
# Linux:
mkdir -p ~/.local/share/fonts
curl -sL "https://github.com/googlefonts/noto-emoji/raw/main/fonts/NotoColorEmoji.ttf" \
  -o ~/.local/share/fonts/NotoColorEmoji.ttf
fc-cache -f ~/.local/share/fonts
```

### demo.gif is too large
- Reduce `GIF_FPS` (8 instead of 10)
- Reduce `MAX_COLORS` (64 instead of 96)
- Increase `zoom` (0.65 instead of 0.7) — smaller content = less motion = smaller file

### Playwright can't find Chromium
```bash
npx playwright install chromium
```

### Build fails — Go not found
The MCP server can also run via Python (uvx immich-mcp). The Go binary is optional.
If you don't have Go, the build will use the existing binary if present.
