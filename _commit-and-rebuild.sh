#!/usr/bin/env bash
# Commit all changes, push, and rebuild the .plugin file.
# Run from the repo root: bash _commit-and-rebuild.sh
set -euo pipefail

cd "$(dirname "$0")"

echo "Git status:"
git status --short

echo ""
echo "Committing changes..."
git add -A
git commit -m "feat: add get_thumbnails_batch + harden template against JS injection

New MCP tool:
- get_thumbnails_batch: fetch base64 thumbnails by asset ID list without
  requiring an album (19th tool). Used by search workflow to avoid creating
  temporary albums.

Search workflow redesign (photo-search SKILL.md):
- NEVER create temporary albums during search
- Find real user-created albums matching the query
- Use get_album_thumbnails for real albums, get_thumbnails_batch for orphans
- Related Albums = only real albums

Template hardening (viewer-template.html):
- PAGE_SIZE, PHOTO_COUNT, ALBUM_TOTAL: wrapped in parseInt() with fallbacks
  Previously: bare injection like PAGE_SIZE= caused SyntaxError
- ALBUM_NAME in JS alt-text: replaced string injection with document.title
  read. Previously: apostrophes in names (L'Hospitalet) broke JS strings
- ALBUMS_JSON: changed to [{{ALBUMS_JSON}}].flat() pattern
  Previously: empty string caused parse-time SyntaxError (var d=;)
  that try/catch could not catch, killing the entire script block.
  The .flat() pattern handles all formats: empty, single object,
  comma-separated objects, or JSON array.

Updated SKILL.md docs (photo-search + album-manager):
- Documented {{PHOTO_ENTRIES}} placeholder format
- Documented .flat() pattern and parseInt fallbacks
- Added EXIF location quirks (Tikal=Flores, Lanzarote=municipalities)"

echo ""
echo "Pushing to remote..."
git push

echo ""
echo "Rebuilding plugin..."
bash build-plugin.sh

echo ""
echo "Done! Restart Cowork to pick up the new MCP server code."
