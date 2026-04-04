---
description: Scan library for screenshots, duplicates, junk
argument-hint: [screenshots|duplicates|all]
allowed-tools: ["mcp__immich__*"]
---

## ⚠️ Connection Required — ALWAYS CHECK FIRST

**Before doing ANYTHING else in this skill, call `ping` on the Immich MCP server.**

- If `ping` succeeds → proceed with the skill normally.
- If `ping` fails or the MCP tools are not available → **STOP. Do not continue.** Tell the user:

> ❌ **Immich is not connected.** This plugin needs a running Immich MCP server to work.
>
> Run **/setup** to configure your Immich connection. You'll need:
> 1. Your Immich server URL (e.g., `http://192.168.1.100:2283`)
> 2. An Immich API key ([how to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key))
> 3. The MCP server running (`./immich-mcp-server`)
>
> Nothing in this plugin will work until the connection is configured.

**Do NOT skip this check. Do NOT try to run any other tool first. Always ping, always block if it fails.**

Run a cleanup scan on the Immich library. Scope determined by $ARGUMENTS:
- `screenshots` — Find only screenshots
- `duplicates` — Find only duplicate photos
- `all` — Full scan (default if no argument)

Follow the photo-cleanup skill workflow:

1. Get library statistics first
2. Run the requested scan type(s)
3. Present findings as a summary report — NEVER delete anything automatically
4. Ask the user what action to take: archive, delete, or skip

Always use dryRun mode for any destructive operations. Report results in this format:

```
🧹 Cleanup Scan Results
━━━━━━━━━━━━━━━━━━━━━━
Library: {total} assets ({size})

📱 Screenshots detected: {count} ({percentage}%)
   High confidence: {count}
   Medium confidence: {count}
   Estimated space: {size}

🔄 Duplicates detected: {count} ({percentage}%)
   Exact copies: {count}
   Format duplicates: {count}
   Estimated space: {size}

💾 Total recoverable: {size}

What would you like to do?
```
