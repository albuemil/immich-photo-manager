# MCP Tools Reference

The Immich Photo Manager MCP server exposes 16 tools that Claude can use to interact with your Immich instance. These tools are the building blocks that all skills use internally.

---

## Tool Categories

### Health & Info

| Tool | Description | Returns |
|------|-------------|---------|
| `ping` | Check if the Immich server is reachable | Connection status |
| `get_server_version` | Get Immich server version | Version string |
| `get_statistics` | Get library-wide statistics | Photo count, video count, storage used |

### Assets

| Tool | Description | Returns |
|------|-------------|---------|
| `get_asset_info` | Get full metadata for a specific asset | EXIF data, GPS, dates, dimensions, file info |
| `get_map_markers` | Get GPS markers for all geotagged assets | Array of {lat, lng, id} for mapping |

### Search

| Tool | Description | Returns |
|------|-------------|---------|
| `search_metadata` | Search by EXIF metadata: location, camera, dates, type | Paginated asset list |
| `search_smart` | AI-powered visual search via CLIP embeddings | Ranked asset list by visual similarity |

**`search_metadata` parameters:**

| Parameter | Type | Example |
|-----------|------|---------|
| `city` | string | "Barcelona" |
| `state` | string | "Catalonia" |
| `country` | string | "Spain" |
| `make` | string | "Apple" |
| `model` | string | "iPhone 14 Pro" |
| `taken_after` | ISO date | "2023-06-01" |
| `taken_before` | ISO date | "2023-06-30" |
| `asset_type` | string | "IMAGE" or "VIDEO" |
| `page` | number | 1 |
| `size` | number | 50 (max 200) |

**`search_smart` parameters:**

| Parameter | Type | Example |
|-----------|------|---------|
| `query` | string | "sunset at the beach" |
| `page` | number | 1 |
| `size` | number | 50 (max 200) |

### Albums

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_albums` | List all albums with asset counts | No |
| `get_album` | Get album details including all asset IDs | No |
| `create_album` | Create a new album with name and description | Yes |
| `update_album` | Update album name or description | Yes |
| `delete_album` | Delete an album (photos are NOT deleted) | Yes |
| `add_assets_to_album` | Add assets to an album by ID | Yes |
| `remove_assets_from_album` | Remove assets from an album (photos stay in library) | Yes |

### Sharing

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_shared_links` | List all shared links | No |
| `create_shared_link` | Create a public link for an album | Yes |
| `delete_shared_link` | Delete a shared link | Yes |

---

## Tool Details

### `create_album`

```json
{
  "name": "🇮🇹 Roma, Italia",
  "description": "Summer 2023 — 45 photos across historic center, Trastevere, and Vatican"
}
```

Returns: Album object with `id` for use with other tools.

### `add_assets_to_album`

```json
{
  "album_id": "uuid-of-album",
  "asset_ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

Accepts up to ~2000 asset IDs per call. For larger batches, make multiple calls.

### `create_shared_link`

```json
{
  "album_id": "uuid-of-album",
  "show_metadata": true,
  "allow_download": false
}
```

Returns: Shared link URL that can be accessed without authentication.

### `search_metadata` — Pagination

Results are paginated. First call returns `total` count:

```json
{
  "assets": [...],
  "page": 1,
  "total": 234
}
```

For large result sets, iterate pages: `page=1`, `page=2`, etc., with `size=200` for maximum efficiency.

### `search_smart` — CLIP Search

Uses Immich's machine learning container to find visually similar photos. Requires the ML container to be running.

Good queries: "sunset", "birthday cake", "mountains with snow", "group photo at dinner"
Less effective: Very specific queries, proper nouns, text-heavy images

---

## Architecture

```
Claude ←→ MCP (Streamable HTTP) ←→ Go Server ←→ Immich REST API
                                     :8626          your-instance
```

- **Protocol**: Streamable HTTP on `/mcp`
- **Health check**: GET `/health`
- **Transport**: HTTP/1.1, JSON payloads
- **Auth**: Immich API key passed via environment variable (never exposed to Claude)
- **Network**: Forces `tcp4` binding for IPv4 compatibility

Built with [mcp-go](https://github.com/mark3labs/mcp-go) v0.32.0.

---

## Rate Limits

The MCP server does not impose its own rate limits, but Immich may:

- Search operations: Generally unlimited for self-hosted instances
- Bulk operations (add 2000 assets to album): May take 2-5 seconds
- CLIP search: Depends on ML container resources — may be slower on first query

For bulk operations, skills automatically batch requests (typically 100-2000 items per call) and report progress.
