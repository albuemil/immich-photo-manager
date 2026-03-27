# Getting Started

Step-by-step guide to installing, configuring, and running the Immich Photo Manager plugin.

---

## Prerequisites

### Required

- **Immich instance** — Self-hosted, any recent version (v1.90+). [Installation guide](https://immich.app/docs/install/docker-compose)
- **Immich API key** — Generated from Immich web UI → User Settings → API Keys. [How to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key)
- **Go 1.24+** — To build the MCP server binary. [Download Go](https://go.dev/dl/)
- **Claude** — Desktop app with Cowork mode, or Claude Code CLI

### Optional (for advanced skills)

- **Python 3.10+** — Required for `duplicate-report` and `metadata-fixer` skills
- **PostgreSQL client** — Required for database-level analysis skills (`library-health-report`, `timeline-gaps`, `people-report`, `storage-optimizer`)
- **Python packages** (for `duplicate-report`):
  ```bash
  pip3 install Pillow imagehash pillow-heif
  ```

---

## Installation

### 1. Clone and build

```bash
git clone https://github.com/drolosoft/immich-photo-manager.git
cd immich-photo-manager
go build -o immich-mcp-server .
```

### 2. Configure environment

```bash
cp .mcp.json.example .mcp.json
```

Edit `.mcp.json` with your Immich credentials:

```json
{
  "mcpServers": {
    "immich": {
      "command": "./immich-mcp-server",
      "env": {
        "IMMICH_BASE_URL": "http://your-immich-server:2283",
        "IMMICH_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### 3. Test the connection

Start the server manually to verify:

```bash
export IMMICH_BASE_URL="http://your-immich-server:2283"
export IMMICH_API_KEY="your-api-key-here"
./immich-mcp-server
```

The server starts on port `8626` by default. Check the health endpoint:

```bash
curl http://localhost:8626/health
```

### 4. Install in Claude

**Cowork mode** (desktop app):
- Drag the `.plugin` file into Settings → Plugins
- Or add the MCP server URL to your Cowork configuration

**Claude Code** (CLI):
- Add to your project's `.mcp.json`:
  ```json
  {
    "mcpServers": {
      "immich": {
        "url": "http://localhost:8626/mcp"
      }
    }
  }
  ```

---

## First Run

After installation, verify everything works:

### Check connection

```
/immich-status
```

You should see your library statistics: photo count, video count, storage used.

### Explore your library

```
/my-travels
```

This discovers all geotagged locations in your library and shows countries and cities.

### Run a health check

```
"How healthy is my library?"
```

This triggers the `library-health-report` skill and gives you a comprehensive overview with recommendations for what to do next.

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `IMMICH_BASE_URL` | Yes | — | Your Immich server URL (e.g., `http://localhost:2283`) |
| `IMMICH_API_KEY` | Yes | — | API key from Immich user settings |
| `MCP_PORT` | No | `8626` | Port for the MCP HTTP server |

### Database Access (for advanced skills)

Skills that query Immich's PostgreSQL directly need these credentials (typically the same database that Immich uses):

| Variable | Description |
|----------|-------------|
| `DB_HOST` | PostgreSQL host (usually `127.0.0.1`) |
| `DB_PORT` | PostgreSQL port (usually `5432`) |
| `DB_USER` | Database user (usually `immich`) |
| `DB_PASS` | Database password |
| `DB_NAME` | Database name (usually `immich`) |

These are only needed for: `library-health-report`, `timeline-gaps`, `metadata-fixer`, `duplicate-report`, `storage-optimizer`, `people-report`, `travel-map`.

---

## Deployment Options

### Local development

Run the server directly:

```bash
./immich-mcp-server
```

### macOS (launchd)

For persistent background service on macOS:

```bash
cp deploy/com.immich-mcp.plist.example ~/Library/LaunchAgents/com.immich-mcp.plist
# Edit the plist: set paths and environment variables
launchctl load ~/Library/LaunchAgents/com.immich-mcp.plist
```

### Linux (systemd)

Create a systemd unit file:

```ini
[Unit]
Description=Immich MCP Server
After=network.target

[Service]
ExecStart=/path/to/immich-mcp-server
Environment=IMMICH_BASE_URL=http://localhost:2283
Environment=IMMICH_API_KEY=your-key-here
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Behind nginx

See `deploy/nginx-immich-mcp.conf.example` for a reverse proxy configuration with HTTPS.

---

## Recommended First Steps

After installation, we recommend this sequence:

1. **`/immich-status`** — Verify connection
2. **`library-health-report`** — Understand your library's current state
3. **`duplicate-report`** — If you have multiple import sources (Apple + Google)
4. **`photo-cleanup`** — Remove screenshots and junk
5. **`/my-travels`** — See all your geotagged destinations
6. **`album-manager`** — Start organizing photos into geographic albums

See [SKILLS.md](./SKILLS.md) for detailed documentation of every skill.

---

## Troubleshooting

### "Connection refused" on startup

- Verify your Immich server is running: `curl http://your-server:2283/api/server/ping`
- Check that the API key is valid: `curl -H "x-api-key: YOUR_KEY" http://your-server:2283/api/server/version`

### Skills that need PostgreSQL report errors

- Ensure PostgreSQL is accessible from where the MCP server runs
- Check credentials with: `psql -h HOST -U immich -d immich -c "SELECT count(*) FROM asset"`
- If using Docker, the PostgreSQL port may not be exposed — add `ports: ["5432:5432"]` to your docker-compose

### HEIC files not processed (duplicate-report)

- Install `pillow-heif`: `pip3 install pillow-heif`
- Without it, Apple Photos HEIC files (40%+ of typical libraries) can't be hashed
- Error shows as thousands of "cannot identify image file" messages

### Perceptual hashing hangs (duplicate-report)

- Don't use `ProcessPoolExecutor` — native HEIF libraries deadlock on fork on macOS
- Use `ThreadPoolExecutor(max_workers=4)` instead
