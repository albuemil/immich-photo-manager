---
description: Scan library for screenshots, duplicates, junk
argument-hint: [screenshots|duplicates|all]
allowed-tools: ["mcp__immich__*"]
---

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
