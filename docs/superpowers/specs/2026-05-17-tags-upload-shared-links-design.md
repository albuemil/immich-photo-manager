# Tags, Upload, Asset List & Shared Links Expansion

**Date:** 2026-05-17
**Scope:** 12 new MCP tools (38 → 50)
**Motivation:** Competitive gap analysis against whitehara/immich-mcp (43 tools). Tags had zero coverage, upload didn't exist, asset listing without search was missing, shared links were incomplete CRUD.

---

## New Tools

### Tags (7 tools) — NEW CATEGORY

All tag operations via Immich REST API `/tags` endpoints.

| Tool | Method | Endpoint | Parameters | Returns |
|------|--------|----------|-----------|---------|
| `list_tags` | GET | `/tags` | — | All tags with IDs, names, colors |
| `get_tag` | GET | `/tags/{id}` | `tag_id` | Tag details |
| `create_tag` | POST | `/tags` | `name`, `color` (optional) | Created tag object |
| `update_tag` | PUT | `/tags/{id}` | `tag_id`, `name` (optional), `color` (optional) | Updated tag |
| `delete_tag` | DELETE | `/tags/{id}` | `tag_id` | None (204) |
| `tag_assets` | PUT | `/tags/{id}/assets` | `tag_id`, `asset_ids` (list) | Result per asset |
| `untag_assets` | DELETE | `/tags/{id}/assets` | `tag_id`, `asset_ids` (list) | Result per asset |

### Upload (1 tool) — ASSETS CATEGORY

| Tool | Method | Endpoint | Parameters | Returns |
|------|--------|----------|-----------|---------|
| `upload_asset` | POST | `/assets` (multipart) | `file_path`, `album_id` (optional) | Asset ID, checksum, duplicate status |

**Security:** File path must be absolute. No directory traversal. File must exist and be readable. Max size enforced by Immich server. If `album_id` provided, asset is added to album after upload.

**Implementation:** Read file from disk, construct multipart form with `assetData` field, include `deviceAssetId` (filename), `deviceId` ("MCP Upload"), `fileCreatedAt` and `fileModifiedAt` from file stat.

### Asset List (1 tool) — ASSETS CATEGORY

| Tool | Method | Endpoint | Parameters | Returns |
|------|--------|----------|-----------|---------|
| `list_assets` | GET | `/assets` | `is_favorite` (bool), `is_archived` (bool), `is_trashed` (bool), `type` (IMAGE/VIDEO), `page` (int), `size` (int, max 200) | Paginated asset list |

**Note:** This is NOT search. No query string, no CLIP, no metadata filters. Just a filtered list of all assets. Complements `search_metadata` and `search_smart`.

### Shared Links CRUD (3 tools) — SHARING CATEGORY

| Tool | Method | Endpoint | Parameters | Returns |
|------|--------|----------|-----------|---------|
| `get_shared_link` | GET | `/shared-links/{id}` | `link_id` | Full link details + permissions + assets |
| `update_shared_link` | PATCH | `/shared-links/{id}` | `link_id`, `allow_download` (bool), `show_metadata` (bool), `allow_upload` (bool), `description`, `expiry_at` (ISO date or empty to remove) | Updated link |
| `delete_shared_link` | DELETE | `/shared-links/{id}` | `link_id` | None (204) |

---

## Implementation Plan

### Layer 1: Client methods (immich_client.py)

Add to `ImmichClient`:

```python
# Tags
async def list_tags(self) -> list[dict]
async def get_tag(self, tag_id: str) -> dict
async def create_tag(self, name: str, color: str | None = None) -> dict
async def update_tag(self, tag_id: str, **fields) -> dict
async def delete_tag(self, tag_id: str) -> None
async def tag_assets(self, tag_id: str, asset_ids: list[str]) -> list[dict]
async def untag_assets(self, tag_id: str, asset_ids: list[str]) -> list[dict]

# Upload
async def upload_asset(self, file_path: str, device_id: str = "MCP Upload") -> dict

# Asset list
async def list_assets(self, **filters) -> list[dict]

# Shared links
async def get_shared_link(self, link_id: str) -> dict
async def update_shared_link(self, link_id: str, **fields) -> dict
async def delete_shared_link(self, link_id: str) -> None
```

### Layer 2: MCP tools (server.py)

12 new `@mcp.tool()` functions following existing patterns:
- JSON serialization with `default=str`
- Error handling via try/except returning `json.dumps({"error": ...})`
- Optional fields only included when provided

### Layer 3: Documentation

- `doc/MCP-TOOLS.md` — add all 12 tools with parameter tables and examples
- `README.md` — update tool count (38 → 50), add Tags to highlights
- `doc/SKILLS.md` — update tool count
- Drolosoft website — update i18n and tool tables

---

## File Changes

| File | Changes |
|------|---------|
| `src/immich_mcp_server/immich_client.py` | 12 new methods |
| `src/immich_mcp_server/server.py` | 12 new tool registrations |
| `doc/MCP-TOOLS.md` | 12 new tool docs, count 38 → 50 |
| `README.md` | Count update, Tags in highlights |
| `doc/SKILLS.md` | Count update |

---

## Testing

Verify against live Immich v2.7.2:
1. Create tag → list tags → verify it appears
2. Tag 3 assets → get_tag → verify assets listed
3. Untag 1 asset → verify removed
4. Upload a test image → verify asset created in Immich
5. List assets with is_favorite filter → verify results
6. Create shared link → get → update expiry → delete → verify gone
