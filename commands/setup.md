---
name: setup
description: First-time setup — configure your Immich MCP server connection and verify everything works
---

# Immich Photo Manager — Setup

Guide the user through connecting their Immich instance to this plugin.

## Prerequisites Check

Before starting, verify these are available:

1. **Immich instance** — Ask the user for their Immich server URL (e.g., `http://192.168.1.100:2283` or `https://photos.example.com`)
2. **Immich API key** — The user needs to generate one from Immich → User Settings → API Keys. Link: https://immich.app/docs/features/command-line-interface#obtain-the-api-key
3. **MCP server** — The Go binary must be built and running. Check if it's accessible.

## Setup Workflow

### Step 1: Get the user's Immich details

Ask the user:
- What is your Immich server URL? (e.g., `http://localhost:2283`)
- Do you have an API key? If not, guide them to create one.

### Step 2: Verify the MCP server is running

The MCP server should be running on the user's machine. Default port is `8626`.

Test connectivity by calling the `ping` tool. If it works, the MCP server is already configured and running.

If ping fails:
- Ask if they've built the MCP server: `go build -o immich-mcp-server .`
- Ask if it's running: `./immich-mcp-server` (needs `IMMICH_BASE_URL` and `IMMICH_API_KEY` env vars)
- Check if the port is different from default

### Step 3: Update plugin MCP config

Once you have the correct MCP server URL, update `.claude-plugin/mcp.json`:

```json
{
  "mcpServers": {
    "immich": {
      "type": "http",
      "url": "http://localhost:8626/mcp"
    }
  }
}
```

Replace the URL with whatever the user's MCP server is running on.

### Step 4: Verify connection

Run these checks:
1. `ping` — Should return "pong"
2. `get_statistics` — Should show photo count, video count, storage
3. `get_server_version` — Should return Immich version

### Step 5: Show summary

```
✅ Connected to Immich v1.XX.X
📸 XX,XXX photos | 🎬 X,XXX videos | 💾 XXX GB
🔗 MCP server: http://localhost:8626/mcp

You're all set! Try these to get started:
  • "How healthy is my photo library?" — full library health report
  • "Show me my albums" — browse your albums with interactive galleries
  • "Find photos of sunsets" — AI-powered visual search
  • /my-travels — discover all your travel destinations
```

### For macOS persistent setup

If the user wants the MCP server to start automatically, offer the launchd setup from `deploy/com.immich-mcp.plist.example`.

### For Linux persistent setup

Offer the systemd unit from `doc/GETTING-STARTED.md`.
