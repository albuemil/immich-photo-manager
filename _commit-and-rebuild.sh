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
git commit -m "fix: base64 thumbnails, lazy loading, pagination, rename setup command

Cowork sandbox:
- Viewer runs at about: protocol, blocks ALL external requests
- Only data: URIs (base64) work for images

Template (viewer-template.html):
- Reverted from URL-based to base64 embedded thumbnails
- Removed fetchThumb(), thumbUrl(), thumbCache, API_KEY
- loadPage(): first page immediate, rest lazy (IntersectionObserver)
- Disabled infinite scroll, manual Load more button only
- Force detail view on load (prevents gallery loading all pages)
- Album covers use coverSrc (base64)
- Labels show img.name instead of generic Photo N

SKILL.md (all 11 skills + 4 commands):
- Documented base64 approach with get_thumbnails_batch
- size=thumbnail (250px, ~18KB avg), limit ~50 photos
- Renamed /setup to /setup-immich-photo-manager to avoid
  collision with other plugins"

echo ""
echo "Pushing to remote..."
git push

echo ""
echo "Rebuilding plugin..."
bash build-plugin.sh

echo ""
echo "Done! Restart Cowork to pick up the new MCP server code."
