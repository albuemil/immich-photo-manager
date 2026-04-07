#!/bin/bash
# setup-mcp.sh - Interactive setup for the Immich MCP server (Claude Code / Cowork)
set -e

echo ""
echo "=== Immich Photo Manager - MCP Setup ==="
echo ""

# Detect repo directory
SCRIPT_DIR="\$(cd "\$(dirname "\$0")/.." && pwd)"
SRC_DIR="\$SCRIPT_DIR/src"

echo "Detected project directory: \$SCRIPT_DIR"
echo "Python source directory:    \$SRC_DIR"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Please install Python 3.10+."
  exit 1
fi
echo "Python: \$(python3 --version)"

# Install dependencies
echo ""
echo "Installing Python dependencies (mcp, httpx)..."
pip3 install mcp httpx --break-system-packages 2>/dev/null || pip3 install mcp httpx
echo ""

# Ask for Immich details
read -p "Enter your Immich server URL (e.g. https://photos.example.com): " IMMICH_URL
read -p "Enter your Immich API key: " IMMICH_KEY

if [ -z "\$IMMICH_URL" ] || [ -z "\$IMMICH_KEY" ]; then
  echo "ERROR: Both URL and API key are required."
  exit 1
fi

# Detect python3 path
PYTHON_PATH="\$(which python3)"

# Write project-level .mcp.json
cat > "\$SCRIPT_DIR/.mcp.json" << EOF
{
  "mcpServers": {
    "immich": {
      "command": "\$PYTHON_PATH",
      "args": ["-m", "immich_mcp_server"],
      "env": {
        "PYTHONPATH": "\$SRC_DIR",
        "MCP_TRANSPORT": "stdio",
        "IMMICH_BASE_URL": "\$IMMICH_URL",
        "IMMICH_API_KEY": "\$IMMICH_KEY"
      }
    }
  }
}
EOF

echo ""
echo "Created \$SCRIPT_DIR/.mcp.json"

# Optionally install globally for Cowork
echo ""
read -p "Also install globally for Cowork / all projects? (y/N): " GLOBAL
if [ "\$GLOBAL" = "y" ] || [ "\$GLOBAL" = "Y" ]; then
  mkdir -p ~/.claude
  GLOBAL_FILE=~/.claude/mcp.json

  if [ -f "\$GLOBAL_FILE" ]; then
    echo "WARNING: ~/.claude/mcp.json already exists."
    echo "You may need to manually merge the immich entry."
  else
    cat > "\$GLOBAL_FILE" << EOF
{
  "mcpServers": {
    "immich": {
      "command": "\$PYTHON_PATH",
      "args": ["-m", "immich_mcp_server"],
      "env": {
        "PYTHONPATH": "\$SRC_DIR",
        "MCP_TRANSPORT": "stdio",
        "IMMICH_BASE_URL": "\$IMMICH_URL",
        "IMMICH_API_KEY": "\$IMMICH_KEY"
      }
    }
  }
}
EOF
    echo "Created ~/.claude/mcp.json"
  fi
fi

echo ""
echo "Setup complete! To verify, run:"
echo "  cd \$SCRIPT_DIR"
echo '  claude -p "use the immich ping tool"'
echo ""
