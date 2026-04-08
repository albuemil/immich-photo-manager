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
echo "Python: $(python3 --version)"

# Install dependencies
echo ""
echo "Installing Python dependencies..."
if [ -f "$SCRIPT_DIR/src/requirements.txt" ]; then
  pip3 install -r "$SCRIPT_DIR/src/requirements.txt" --break-system-packages 2>/dev/null \
    || pip3 install -r "$SCRIPT_DIR/src/requirements.txt" 2>/dev/null \
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

# Detect python3 absolute path
PYTHON_PATH="$(which python3)"

# Write project-level .mcp.json
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

echo ""
echo "Created $SCRIPT_DIR/.mcp.json"

# Optionally install globally for Cowork / all projects
echo ""
read -p "Also install globally for Cowork / all projects? (y/N): " GLOBAL
if [ "$GLOBAL" = "y" ] || [ "$GLOBAL" = "Y" ]; then
  mkdir -p ~/.claude
  GLOBAL_FILE=~/.claude/mcp.json

  if [ -f "$GLOBAL_FILE" ]; then
    echo ""
    echo "WARNING: $GLOBAL_FILE already exists."
    echo "You may need to manually merge the immich entry into it."
    echo "Here is the JSON block to add under \"mcpServers\":"
    echo ""
    echo "  \"immich\": {"
    echo "    \"command\": \"$PYTHON_PATH\","
    echo "    \"args\": [\"-m\", \"immich_mcp_server\"],"
    echo "    \"env\": {"
    echo "      \"PYTHONPATH\": \"$SRC_DIR\","
    echo "      \"MCP_TRANSPORT\": \"stdio\","
    echo "      \"IMMICH_BASE_URL\": \"$IMMICH_URL\","
    echo "      \"IMMICH_API_KEY\": \"$IMMICH_KEY\""
    echo "    }"
    echo "  }"
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
echo "  1. Register the plugin marketplace:"
echo "     claude plugin marketplace add $SCRIPT_DIR"
echo ""
echo "  2. Install the plugin:"
echo "     claude plugin install immich-photo-manager"
echo ""
echo "  3. Restart Claude Code or start a new Cowork session"
echo ""
echo "  4. Verify everything works:"
echo "     claude -p \"use the immich ping tool\""
echo ""
