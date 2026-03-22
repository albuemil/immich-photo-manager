---
description: Check Immich connection and library stats
allowed-tools: ["mcp__immich__*"]
---

Connect to Immich and report the current library status.

1. Call `immich_get_statistics` to get total counts
2. Call `immich_list_albums` to get album count and names

Present a concise dashboard:

```
📊 Immich Library Status
━━━━━━━━━━━━━━━━━━━━━━
Photos: {count}
Videos: {count}
Albums: {count} ({shared_count} shared)
Storage: {size}

Recent albums:
- {album_name} ({asset_count} items)
```

If the connection fails, explain what went wrong and suggest checking IMMICH_URL and IMMICH_API_KEY environment variables.
