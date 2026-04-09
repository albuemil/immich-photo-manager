#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "=== Git status ==="
git status --short

echo ""
echo "=== Committing ==="
git add -A
git commit -m "feat: add update_credentials MCP tool for in-session API key rotation

Cowork mounts remote plugin configs as read-only, so users cannot update
their Immich API key without reinstalling the plugin. This adds a
credentials override mechanism using the writable .mcpb-cache directory:

- ImmichClient now checks .mcpb-cache/config.json before env vars
- New update_credentials tool validates, persists, and hot-swaps creds
- mcp.json exposes IMMICH_CACHE_DIR for reliable cache dir discovery
- Setup skill updated to use update_credentials for key rotation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

echo ""
echo "=== Pushing ==="
git push

echo ""
echo "=== Rebuilding plugin ==="
bash build-plugin.sh

echo ""
echo "=== Done! ==="
echo "Restart Cowork to pick up the new plugin."

# Self-destruct
rm -- "$0"
