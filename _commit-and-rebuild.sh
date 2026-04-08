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
- PAGE_SIZE, PHOTO_COUNT: wrapped in parseInt() with fallbacks (6 and 0)
  Previously: bare injection like PAGE_SIZE=not-a-number caused SyntaxError
- ALBUM_NAME in JS: replaced injection with document.title.split() read
  Previously: apostrophes in names (L'Hospitalet) broke JS string literals
- ALBUM_TOTAL: already had parseInt (confirmed)
- ALBUMS_JSON: already had safe parser with try/catch (confirmed)

Updated SKILL.md docs with relaxed placeholder rules reflecting the
defensive template."

echo ""
echo "Pushing to remote..."
git push

echo ""
echo "Rebuilding plugin..."
bash build-plugin.sh

echo ""
echo "Done! Restart Cowork to pick up the new MCP server code."
