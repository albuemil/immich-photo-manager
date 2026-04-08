#!/usr/bin/env bash
# Build the immich-photo-manager.plugin file for Cowork distribution.
# Usage: ./build-plugin.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

OUTPUT="immich-photo-manager.plugin"

echo "🔧 Building $OUTPUT ..."

# Remove old build if present
rm -f "$OUTPUT"

zip -r "$OUTPUT" \
  .claude-plugin/ \
  .claude/ \
  commands/ \
  skills/ \
  assets/viewer-template.html \
  assets/index-template.html \
  assets/icon.png \
  src/ \
  scripts/ \
  README.md \
  .env.example \
  -x "*.DS_Store" \
  -x "*__pycache__*" \
  -x "*.pyc"

SIZE=$(du -h "$OUTPUT" | cut -f1)
echo "✅ Built $OUTPUT ($SIZE)"
echo "   Share this file in a Cowork chat to install the plugin."
