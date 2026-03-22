"""Entry point: python -m immich_mcp_server"""

import uvicorn
import os

def main():
    port = int(os.environ.get("MCP_PORT", "8626"))
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    print(f"🚀 Immich MCP Server starting on {host}:{port}")
    uvicorn.run(
        "immich_mcp_server.server:app",
        host=host,
        port=port,
        log_level="info",
    )

if __name__ == "__main__":
    main()
