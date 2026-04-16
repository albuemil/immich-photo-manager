# MCP Tools Reference

The Immich Photo Manager MCP server exposes 22 tools that Claude can use to interact with your Immich instance. These tools are the building blocks that all skills use internally.

---

## Tool Categories

### Health & Info (3)

| Tool | Description | Returns |
|------|-------------|---------|
| `ping` | Check if the Immich server is reachable | Connection status |
| `get_server_version` | Get Immich server version | Version string |
| `get_statistics` | Get library-wide statistics | Photo count, video count, storage used |

### Assets (3)

| Tool | Description | Returns |
|------|-------------|---------|
| `get_asset_info` | Get full metadata for a specific asset | EXIF data, GPS, dates, dimensions, file info |
| `update_asset_metadata` | Update asset properties (favorites, visibility). EXIF fields (dates, GPS, description) accepted but persistence depends on Immich server version | Updated asset object |
| `get_map_markers` | Get GPS markers for all geotagged assets | Array of {lat, lng, id} for mapping |

### Search (2)

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
| `is_favorite` | boolean | true |
| `page` | number | 1 |
| `size` | number | 50 (max 200) |

**`search_smart` parameters:**

| Parameter | Type | Example |
|-----------|------|---------|
| `query` | string | "sunset at the beach" |
| `city` | string | "Barcelona" (optional filter) |
| `state` | string | "Catalonia" (optional filter) |
| `country` | string | "Spain" (optional filter) |
| `taken_after` | ISO date | "2023-06-01" |
| `taken_before` | ISO date | "2023-06-30" |
| `page` | number | 1 |
| `size` | number | 50 (max 200) |

### Albums (7)

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_albums` | List all albums with asset counts | No |
| `get_album` | Get album details including all asset IDs | No |
| `create_album` | Create a new album with name, description, and optional initial assets | Yes |
| `update_album` | Update album name or description | Yes |
| `delete_album` | Delete an album (photos are NOT deleted) | Yes |
| `add_assets_to_album` | Add assets to an album by ID | Yes |
| `remove_assets_from_album` | Remove assets from an album (photos stay in library) | Yes |

### Sharing (2)

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_shared_links` | List all shared links | No |
| `create_shared_link` | Create a public link for an album | Yes |

### Thumbnails (3)

| Tool | Description | Returns |
|------|-------------|---------|
| `get_asset_thumbnail` | Get base64-encoded thumbnail for a single asset | Base64 image data + MIME type |
| `get_album_thumbnails` | Get base64 thumbnails for assets in an album (batch) | Array of {asset_id, data, mime_type, filename, date} |
| `get_thumbnails_batch` | Get base64 thumbnails for a list of asset IDs (no album needed) | Array of {asset_id, data, mime_type, filename, date} |

### Configuration (2)

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `get_connection_info` | Return the Immich base URL and masked API key | No |
| `update_credentials` | Update Immich URL and API key at runtime (persisted to disk, no restart needed) | Yes |

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
  "limit": 20,
  "size": "thumbnail"
}
```

Batch version of `get_asset_thumbnail` — fetches thumbnails for assets in an album in a single call. Returns album info and a list of thumbnail entries with asset IDs, base64 data, filenames, and dates. Default limit is 20, max 50. This is the primary tool for gallery HTML generation when working with albums.

### `get_thumbnails_batch`

```json
{
  "asset_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "limit": 20,
  "size": "thumbnail"
}
```

Like `get_album_thumbnails` but works with arbitrary asset IDs — no album needed. Use this when displaying search results or orphan photos that aren't in any album. Default limit is 20, max 50.

### `update_asset_metadata`

```json
{
  "asset_id": "uuid-of-asset",
  "is_favorite": true
}
```

Updates properties on a single asset. Only provided fields are modified — omitted fields are left unchanged.

| Parameter | Type | Status | Description |
|-----------|------|--------|-------------|
| `asset_id` | string | **Required** | The asset to update |
| `is_favorite` | boolean | **Verified** | Mark as favorite |
| `date_time_original` | ISO 8601 string | Experimental | Original capture date and time |
| `latitude` | number (-90 to 90) | Experimental | GPS latitude |
| `longitude` | number (-180 to 180) | Experimental | GPS longitude |
| `description` | string | Experimental | Asset description text |
| `rating` | integer (1-5) | Experimental | Star rating |

> **Note:** Asset-level fields (`is_favorite`) persist reliably. EXIF-level fields (dates, GPS, description, rating) are sent to the Immich API but persistence depends on your Immich server version and configuration. This matches a known limitation in some Immich deployments where the `asset_exif` table does not accept writes via the REST API. We are tracking this upstream.

### `create_album`

```json
{
  "name": "🇮🇹 Roma, Italia",
  "description": "Summer 2023 — 45 photos across historic center, Trastevere, and Vatican",
  "asset_ids": ["uuid-1", "uuid-2"]
}
```

Returns: Album object with `id` for use with other tools. `asset_ids` is optional — pass it to add photos at creation time.

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

### `update_credentials`

```json
{
  "base_url": "https://photos.example.com",
  "api_key": "new-api-key-here"
}
```

Updates the Immich connection credentials at runtime. The new credentials are persisted to disk and take effect immediately — no restart required. Use this when the API key has been rotated or when switching Immich instances.

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

Uses Immich's machine learning container to find visually similar photos. Requires the ML container to be running. Can be combined with location and date filters for more precise results.

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
