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
git commit -m "fix: revert to base64 thumbnails + fix lazy loading & pagination

Cowork sandbox discovery:
- Cowork viewer runs at about: protocol with origin: null
- ALL external network requests are blocked (fetch, img src, etc.)
- Only data: URIs (base64) work for images
- URL-based approach (fetch + x-api-key) does NOT work in Cowork

Template changes (viewer-template.html):
- Reverted from URL-based to base64 embedded thumbnails
- Removed fetchThumb(), thumbUrl(), thumbCache, API_KEY constant
- showGal() reverted from async/fetchThumb to sync/img.src
- loadPage(): first page loads images immediately (src=img.src),
  subsequent pages use lazy loading (dataset.src + IntersectionObserver)
- Disabled infinite scroll (was auto-loading all pages at once)
- Pagination is now manual via Load more button only
- Album covers use coverSrc (base64) instead of fetchThumb(coverId)
- Labels show img.name instead of generic Photo N
- Kept all previous hardening: parseInt wrappers, document.title
  for alt-text, ALBUMS_JSON .flat() pattern

SKILL.md updates (photo-search + album-manager):
- Documented base64 approach: get_thumbnails_batch is REQUIRED
- Always use size=thumbnail (250px, ~18KB avg)
- Limit galleries to ~50 photos (~0.9MB HTML)
- Removed all references to fetch(), API_KEY, URL-based loading
- Updated generation workflow to include thumbnail fetch step"

echo ""
echo "Pushing to remote..."
git push

echo ""
echo "Rebuilding plugin..."
bash build-plugin.sh

echo ""
echo "Done! Restart Cowork to pick up the new MCP server code."
