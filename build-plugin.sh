#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# build-plugin.sh — Package immich-photo-manager as a .plugin
#
# Usage:
#   ./build-plugin.sh          # builds immich-photo-manager.plugin
#   ./build-plugin.sh v1.2.0   # builds immich-photo-manager-v1.2.0.plugin
#
# The .plugin file is a zip archive that can be dragged into
# Cowork Settings → Plugins to install the plugin locally.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Read version from plugin.json
VERSION="${1:-$(python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])" 2>/dev/null || echo "unknown")}"
PLUGIN_NAME="immich-photo-manager"
OUTPUT="${PLUGIN_NAME}-v${VERSION}.plugin"

echo "📦 Building ${OUTPUT}..."

# Clean previous builds
rm -f "${PLUGIN_NAME}"*.plugin

# Build the Go MCP server binary (if Go is available)
if command -v go &>/dev/null; then
  echo "🔨 Compiling MCP server..."
  go build -o immich-mcp-server .
  echo "   ✅ immich-mcp-server built ($(du -h immich-mcp-server | cut -f1))"
else
  if [[ -f immich-mcp-server ]]; then
    echo "⚠️  Go not found — using existing immich-mcp-server binary"
  else
    echo "❌ Go not found and no pre-built binary exists. Install Go 1.24+ first."
    exit 1
  fi
fi

# Create the .plugin zip
# Include everything the plugin needs, exclude dev/build artifacts
zip -r "$OUTPUT" \
  .claude-plugin/ \
  assets/ \
  commands/ \
  deploy/ \
  doc/ \
  scripts/ \
  skills/ \
  src/ \
  immich-mcp-server \
  immich.go \
  main.go \
  go.mod \
  go.sum \
  run-mcp-server.sh \
  LICENSE \
  README.md \
  .env.example \
  .mcp.json.example \
  .gitignore \
  -x "assets/.gitkeep" \
  -x "assets/demo-script.md" \
  -x "src/immich_mcp_server/__pycache__/*" \
  -x "scripts/location_inventory.json" \
  -x "*.DS_Store"

# Report
SIZE=$(du -h "$OUTPUT" | cut -f1)
COUNT=$(unzip -l "$OUTPUT" | tail -1 | awk '{print $2}')
echo ""
echo "✅ Built: ${OUTPUT} (${SIZE}, ${COUNT} files)"
echo ""
echo "To install:"
echo "  • Cowork: Drag ${OUTPUT} into Settings → Plugins"
echo "  • Claude Code: unzip into your plugins directory"
echo ""
echo "To test locally before publishing:"
echo "  1. Open Cowork"
echo "  2. Drag ${OUTPUT} into the chat or Settings → Plugins"
echo "  3. Say: /immich-status"
