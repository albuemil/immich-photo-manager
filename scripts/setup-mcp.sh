#!/bin/bash
# setup-mcp.sh - Interactive setup for the Immich MCP server (Claude Code / Cowork)
set -e

echo ""
echo "=== Immich Photo Manager - MCP Setup ==="
echo ""

# Detect repo directory
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$SCRIPT_DIR/src"

echo "Detected project directory: $SCRIPT_DIR"
echo "Python source directory:    $SRC_DIR"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Please install Python 3.10+."
  exit 1
fi
PYTHON_PATH="$(which python3)"
echo "Python: $(python3 --version) ($PYTHON_PATH)"

# Install dependencies
echo ""
echo "Installing Python dependencies..."
if [ -f "$SRC_DIR/requirements.txt" ]; then
  pip3 install -r "$SRC_DIR/requirements.txt" --break-system-packages 2>/dev/null \
    || pip3 install -r "$SRC_DIR/requirements.txt" 2>/dev/null \
    || echo "WARNING: pip install failed. Please install dependencies manually: pip3 install mcp httpx"
else
  pip3 install mcp httpx --break-system-packages 2>/dev/null \
    || pip3 install mcp httpx 2>/dev/null \
    || echo "WARNING: pip install failed. Please install manually: pip3 install mcp httpx"
fi
echo ""

# Ask for Immich details
read -p "Enter your Immich server URL (e.g. https://photos.example.com): " IMMICH_URL
read -p "Enter your Immich API key: " IMMICH_KEY

if [ -z "$IMMICH_URL" ] || [ -z "$IMMICH_KEY" ]; then
  echo "ERROR: Both URL and API key are required."
  exit 1
fi

# Build the immich MCP server JSON block
IMMICH_BLOCK="{\"command\":\"$PYTHON_PATH\",\"args\":[\"-m\",\"immich_mcp_server\"],\"env\":{\"PYTHONPATH\":\"$SRC_DIR\",\"MCP_TRANSPORT\":\"stdio\",\"IMMICH_BASE_URL\":\"$IMMICH_URL\",\"IMMICH_API_KEY\":\"$IMMICH_KEY\"}}"

# ---- Project-level .mcp.json ----
cat > "$SCRIPT_DIR/.mcp.json" << MCPEOF
{
  "mcpServers": {
    "immich": {
      "command": "$PYTHON_PATH",
      "args": ["-m", "immich_mcp_server"],
      "env": {
        "PYTHONPATH": "$SRC_DIR",
        "MCP_TRANSPORT": "stdio",
        "IMMICH_BASE_URL": "$IMMICH_URL",
        "IMMICH_API_KEY": "$IMMICH_KEY"
      }
    }
  }
}
MCPEOF
echo "Created $SCRIPT_DIR/.mcp.json"

# ---- Global ~/.claude/mcp.json (auto-merge) ----
echo ""
read -p "Also install globally for Cowork / all projects? (y/N): " GLOBAL
if [ "$GLOBAL" = "y" ] || [ "$GLOBAL" = "Y" ]; then
  mkdir -p ~/.claude
  GLOBAL_FILE=~/.claude/mcp.json

  if [ -f "$GLOBAL_FILE" ]; then
    # Auto-merge: use python3 to insert/replace the immich key in existing JSON
    python3 -c "
import json, sys

gf = '$GLOBAL_FILE'
try:
    with open(gf, 'r') as f:
        config = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    config = {'mcpServers': {}}

if 'mcpServers' not in config:
    config['mcpServers'] = {}

config['mcpServers']['immich'] = json.loads('$IMMICH_BLOCK')

with open(gf, 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')

print(f'Updated {gf} — immich entry merged successfully.')
"
  else
    cat > "$GLOBAL_FILE" << MCPEOF
{
  "mcpServers": {
    "immich": {
      "command": "$PYTHON_PATH",
      "args": ["-m", "immich_mcp_server"],
      "env": {
        "PYTHONPATH": "$SRC_DIR",
        "MCP_TRANSPORT": "stdio",
        "IMMICH_BASE_URL": "$IMMICH_URL",
        "IMMICH_API_KEY": "$IMMICH_KEY"
      }
    }
  }
}
MCPEOF
    echo "Created $GLOBAL_FILE"
  fi
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Restart Claude Desktop or start a new Cowork session"
echo "  2. Verify: ask Claude to 'use the immich ping tool'"
echo ""
