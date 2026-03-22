#!/bin/bash
# Immich MCP Server launcher
# Configure IMMICH_BASE_URL and IMMICH_API_KEY in your environment or .env file

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

exec ./immich-mcp-server
