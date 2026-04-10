# drolosoft.com/immich-photo-manager — Fixes Needed

Changes required on the website at `https://drolosoft.com/immich-photo-manager.html` to match the actual plugin implementation.

---

## Critical (breaks user onboarding)

### 1. Quick Start: Go build instructions → Python setup

**Current (wrong):**
```
git clone https://github.com/drolosoft/immich-photo-manager.git
cd immich-photo-manager && go build -o immich-mcp-server .
export IMMICH_BASE_URL=https://your-immich-instance.com
export IMMICH_API_KEY=your-api-key
./immich-mcp-server
```

**Should be:**
```
git clone https://github.com/drolosoft/immich-photo-manager.git
cd immich-photo-manager
./scripts/setup-mcp.sh
claude plugin marketplace add ~/immich-photo-manager
claude plugin install immich-photo-manager
```

Or for manual setup:
```
pip3 install -r src/requirements.txt
```
Then configure `.mcp.json` with Python/stdio config (see README Option B).

### 2. Architecture diagram: Go Server → Python Server

**Current (wrong):**
```
Claude ←→ MCP (Streamable HTTP) ←→ Go Server ←→ Immich REST API
                                     :8626          your-instance
```

**Should be:**
```
Claude ←→ MCP (stdio) ←→ Python Server ←→ Immich REST API
                                              your-instance
```

### 3. Technical Requirements: Go 1.24+ → Python 3.10+

**Current (wrong):**
| Go | 1.24+ |

**Should be:**
| Python | 3.10+ |

### 4. "Built With" section: Go references → Python references

**Current:** mentions "Go 1.24+" and "mcp-go v0.32.0"

**Should be:** "Python 3.10+", "mcp (Python SDK)", "httpx"

---

## Important (inconsistent data)

### 5. Tool count: 19 → 21

The page says "19 MCP Tools" but the actual server exposes 21. The missing tools:
- `get_thumbnails_batch` (fetch thumbnails for arbitrary asset IDs without an album)
- `get_connection_info` (return current Immich URL and API key)
- `update_credentials` (rotate API key at runtime without restart)

The tools table also lists `delete_shared_link` which does not exist in the current server.

### 6. Tool table needs updating

**Current Thumbnails section (2 tools):** `get_album_thumbnails`, `get_asset_thumbnail`

**Should be Thumbnails section (3 tools):** `get_album_thumbnails`, `get_asset_thumbnail`, `get_thumbnails_batch`

**Add new Config section (2 tools):** `get_connection_info`, `update_credentials`

**Remove from Sharing:** `delete_shared_link` (does not exist in current server)

### 7. Overview paragraph says "16 MCP tools"

Should say "21 MCP tools".

---

## Minor

### 8. Remove Go Report Card badge

The page includes a Go Report Card badge that links to goreportcard.com. Since the project is now Python-based, this badge is misleading.

### 9. Cowork Plugin section

The section says "No terminal or configuration files required" but users still need to run `./scripts/setup-mcp.sh` or manually install Python dependencies (`pip3 install mcp httpx`). This should mention the Python dependency requirement.
