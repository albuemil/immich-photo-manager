# MCP Tools Reference

The Immich Photo Manager MCP server exposes 19 tools that Claude can use to interact with your Immich instance. These tools are the building blocks that all skills use internally.

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
| `get_asset_thumbnail` | Get base64-encoded thumbnail for a single asset | Base64 image data + MIME type |
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
| `get_album_thumbnails` | Get base64 thumbnails for assets in an album (batch) | No |
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

### `get_asset_thumbnail`

```json
{
  "asset_id": "uuid-of-asset",
  "size": "thumbnail"
}
```

`size` accepts `"thumbnail"` (~250px, default) or `"preview"` (~1440px). Returns `{data, mime_type}` with base64-encoded image data. Used by the gallery HTML generator to embed thumbnails directly in self-contained HTML files.

### `get_album_thumbnails`

```json
{
  "album_id": "uuid-of-album",
  "count": 20,
  "offset": 0
}
```

Batch version of `get_asset_thumbnail` — fetches thumbnails for all (or a subset of) assets in an album in a single call. Returns `{thumbnails: [{asset_id, data, mime_type}, ...], total_assets, immich_url}`. Set `count=0` (default) for all photos; use `count` + `offset` to paginate large albums. This is the primary tool for gallery HTML generation.

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
Claude ←→ MCP (stdio) ←→ Python Server ←→ Immich REST API
                                              your-instance
```

- **Protocol**: stdio (standard MCP transport for Claude Code / Cowork)
- **Auth**: Immich API key passed via environment variable (never exposed to Claude)
- **Thumbnail delivery**: Base64 data URIs embedded directly in self-contained HTML galleries — required because the Cowork viewer runs in an `about:` sandbox that blocks all external network requests

For a detailed explanation of the thumbnail delivery architecture and why base64 embedding is the only viable approach in Cowork, see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Rate Limits

The MCP server does not impose its own rate limits, but Immich may:

- Search operations: Generally unlimited for self-hosted instances
- Bulk operations (add 2000 assets to album): May take 2-5 seconds
- CLIP search: Depends on ML container resources — may be slower on first query

For bulk operations, skills automatically batch requests (typically 100-2000 items per call) and report progress.
