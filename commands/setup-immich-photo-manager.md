---
name: setup-immich-photo-manager
description: First-time setup or credential update — configure your Immich MCP server connection and verify everything works
---

# Immich Photo Manager — Setup

Guide the user through connecting their Immich instance to this plugin.
This skill handles both **first-time setup** and **credential updates** (e.g. API key rotation).

## Prerequisites Check

Before starting, verify these are available:

1. **Immich instance** — Ask the user for their Immich server URL (e.g., `http://192.168.1.100:2283` or `https://photos.example.com`)
2. **Immich API key** — The user needs to generate one from Immich → User Settings → API Keys. Link: https://immich.app/docs/features/command-line-interface#obtain-the-api-key

## Setup Workflow

### Step 1: Check if MCP server is already running

Call `ping` to test if the MCP server is already up.

- **If ping succeeds** → the MCP server is running. Proceed to Step 2 to verify the API key works.
- **If ping fails** → the MCP server is not running or not configured. Ask the user to check their plugin installation.

### Step 2: Test if credentials are valid

Call `get_statistics` or `search_metadata` (any authenticated endpoint).

- **If it succeeds** → credentials are valid. Jump to Step 5 (show summary).
- **If it returns 401 Unauthorized** → the API key is invalid or expired. Go to Step 3.

### Step 3: Get new credentials from the user

Ask the user:
- What is your Immich server URL? (e.g., `https://photos.example.com`)
- What is your new API key? (guide them to create one if needed: Immich → User Settings → API Keys)

### Step 4: Update credentials via MCP tool

**Use the `update_credentials` tool** to update the connection in-place:

```
update_credentials(base_url="https://photos.example.com", api_key="the-new-key")
```

This tool will:
1. Validate the new credentials by pinging Immich
2. Persist them to `.mcpb-cache/config.json` (survives session restarts)
3. Hot-swap the live connection (no restart required)

**If `update_credentials` succeeds** → proceed to Step 5.
**If it fails** → tell the user the credentials didn't work, ask them to double-check.

**IMPORTANT:** Do NOT try to edit `mcp.json` directly — it's read-only for remote plugins.
The `update_credentials` tool is the correct way to change credentials.

### Step 5: Verify connection

Run these checks:
1. `ping` — Should return "pong"
2. `get_statistics` — Should show photo count, video count, storage
3. `get_server_version` — Should return Immich version

### Step 6: Show summary

```
Connected to Immich vX.XX.X
Photos: XX,XXX | Videos: X,XXX | Storage: XXX GB
Server: https://photos.example.com

You're all set! Try these to get started:
  - "How healthy is my photo library?" — full library health report
  - "Show me my albums" — browse your albums with interactive galleries
  - "Find photos of sunsets" — AI-powered visual search
  - /my-travels — discover all your travel destinations
```

## Credential Rotation (Key Change)

When a user needs to update their API key (expired, rotated, etc.), the flow is simple:

1. User provides the new API key
2. Call `update_credentials(base_url, api_key)`
3. Done — no restart, no reinstall, no manual file editing

The `update_credentials` tool validates the key before committing it, so the user
gets immediate feedback if the key is wrong.
