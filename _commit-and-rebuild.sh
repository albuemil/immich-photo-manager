#!/usr/bin/env bash
# Commit all changes, push, and rebuild the .plugin file.
# Run from the repo root: bash _commit-and-rebuild.sh
set -euo pipefail

cd "$(dirname "$0")"

echo "📋 Git status:"
git status --short

echo ""
echo "📦 Committing changes..."
git add -A
git commit -m "feat: add get_thumbnails_batch tool + rewrite search workflow

- Added get_thumbnails_batch to immich_client.py and server.py (19th MCP tool)
  Fetches base64 thumbnails by asset ID list without requiring an album.
- Rewrote photo-search SKILL.md: NEVER create temporary albums during search.
  New workflow: search -> find real albums -> use get_album_thumbnails or
  get_thumbnails_batch for orphan photos. Related Albums = real albums only.
- Updated album-manager SKILL.md: clarified Related Albums must be real,
  user-created albums. Never fabricate album entries.
- Updated plugin.json: 18 -> 19 MCP tools."

echo ""
echo "🚀 Pushing to remote..."
git push

echo ""
echo "🔧 Rebuilding plugin..."
bash build-plugin.sh

echo ""
echo "✅ Done! Restart Cowork to pick up the new MCP server code."
