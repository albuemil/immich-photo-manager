---
name: album-manager
description: >
  Create, curate, and publish Immich albums organized by geography, theme, or custom criteria.
  Use when the user says "create an album", "organize my photos by location",
  "make a gallery album", "curate photos from Italy", "publish album",
  "geographic albums", "album from my trip to X", "share this album",
  or any variation of creating, managing, or publishing photo albums in Immich.
  Also triggers on "what albums do I have", "list albums", "album stats",
  "show me photos from", "generate gallery for", "show me the album".
version: 0.2.0
---

# Album Manager

Intelligent album creation and curation for Immich photo libraries. Organizes photos **geographically by default** — albums represent places, not dates.

## Core Principle

**Geography first, chronology second.** A user who visited Mexico twice gets one "Mexico" album (or sub-albums by city), not "Mexico 2018" and "Mexico 2023". Dates are metadata shown inside the album, never the organizing principle.

## Available MCP Tools

Use the Immich MCP tools for all API interactions:

- `immich_search_assets` — Search by GPS coordinates, date range, city, country, camera, person, or smart/CLIP text query
- `immich_create_album` — Create a new album with name and description
- `immich_add_assets_to_album` — Add photos/videos to an album by asset IDs
- `immich_remove_assets_from_album` — Remove assets from an album
- `immich_list_albums` — List all albums with asset counts
- `immich_get_album` — Get album details including all assets
- `immich_delete_album` — Delete an album (does NOT delete the photos)
- `immich_create_shared_link` — Create a public shared link for an album (makes it visible in Gallery)
- `immich_get_asset_info` — Get full metadata for a specific asset (GPS, EXIF, dates)
- `immich_get_statistics` — Get library statistics (total photos, videos, storage)
- `immich_get_asset_thumbnail` — Get base64 thumbnail for an asset (used for gallery HTML generation)

## Album Creation Workflow

### 1. Discover photos for a location

Search by GPS bounding box OR by CLIP semantic search OR by date range:

```
# GPS-based (most accurate)
immich_search_assets(latitude=41.87, longitude=12.49, radius_km=50)  # Rome area

# CLIP semantic search (when GPS is missing)
immich_search_assets(query="Colosseum Rome Italy")

# Date-based (supplement)
immich_search_assets(date_from="2023-06-01", date_to="2023-06-15")

# Combined
immich_search_assets(latitude=41.87, longitude=12.49, radius_km=50, date_from="2023-06-01")
```

### 2. Filter and curate

From the search results, filter out:
- Screenshots (typical screen resolutions, no GPS, no lens info)
- Duplicate/near-duplicate images
- Blurry or very dark photos (if quality metadata available)
- Photos that don't match the location theme

Prefer photos that:
- Have strong composition or visual interest
- Show landmarks, landscapes, or characteristic scenes of the place
- Have good resolution and quality
- Tell the story of the place

Target: **20-50 photos per album** for optimal gallery experience. Can go up to 100 for major destinations.

### 3. Create the album

Naming convention:
```
[Country emoji] Place, Country
Examples:
🇮🇹 Cinque Terre, Italia
🇪🇬 Cairo & Luxor, Egypt
🇲🇽 Chiapas, México
🏝️ Lanzarote
🌴 La Palma
🏙️ Barcelona
```

For the description, include:
- When the photos were taken (year or date range)
- Brief context (e.g., "Summer road trip through coastal villages")
- Number of photos

### 4. Share for Gallery publication

After creating the album, create a shared link to make it visible in the Gallery frontend:

```
immich_create_shared_link(album_id="{id}", show_metadata=true, allow_download=false)
```

### 5. Verify

Confirm the album appears correctly:
- Check album name and description
- Verify photo count matches expectations
- Confirm shared link is active

## Batch Album Creation

When creating multiple albums at once (e.g., "create albums for all my trips"):

1. First, get library statistics and map view data to understand what locations exist
2. Cluster photos by GPS coordinates to identify distinct locations
3. Present a proposed album list to the user for approval BEFORE creating
4. Create albums one by one, reporting progress
5. Summarize all created albums at the end

Always err on the side of creating MORE albums — the user can merge or delete later. It's easier to remove an unwanted album than to discover a missing one.

## Handling Missing GPS Data

Many photos (especially older ones or screenshots) lack GPS coordinates. Strategy:

1. First search by GPS for photos that have it
2. Then search by date range to find photos taken during the same trip
3. Use CLIP semantic search as a fallback ("beach Lanzarote", "pyramid Egypt")
4. Flag photos without GPS that were found by date/CLIP — they may or may not belong

## Album Maintenance

When asked to update or refine an existing album:

1. Get current album contents
2. Search for additional photos that might belong (expanded date range, nearby GPS, related CLIP queries)
3. Present additions and potential removals to the user
4. Apply changes after approval

---

## Gallery HTML Generation

When the user asks to **"show me photos from [album]"**, **"generate a gallery for [album]"**, **"show me [album name]"**, or any variation of viewing/displaying album contents visually, generate an interactive HTML gallery page.

### Template

Use the gallery template at `assets/viewer-template.html` (from the plugin root). This is a self-contained, single-file HTML gallery with:

- **Dark/light theme** (system-aware, toggleable)
- **4 view modes**: detail grid, icon grid, list, masonry
- **Full-screen gallery overlay** with keyboard navigation (arrows, Escape, Space for slideshow)
- **Touch/swipe gestures** for mobile
- **Lazy loading** with intersection observers
- **Infinite scroll** with "Load more" button
- **Slideshow mode** with progress bar
- **Polaroid-style album cards** linking back to Immich
- **Responsive design** for all screen sizes

### Placeholder Reference

The template uses these placeholders that MUST be replaced:

| Placeholder | Description | Example |
|---|---|---|
| `{{ALBUM_NAME}}` | Display name of the album | `Lanzarote Verde` |
| `{{ALBUM_TOTAL}}` | Total number of photos in the album | `273` |
| `{{SEARCH_QUERY}}` | The query or description used to find photos | `&ldquo;green landscapes in Lanzarote&rdquo;` |
| `{{IMMICH_URL}}` | Immich server base URL | `https://fotos.txeo.club` |
| `{{PAGE_SIZE}}` | Number of photos per lazy-load page | `6` |
| `{{PHOTO_COUNT}}` | Number of photos included in the HTML (may be less than ALBUM_TOTAL for performance) | `20` |
| `{{PHOTO_ENTRIES}}` | The photo data entries (see format below) | See below |
| `{{ALBUMS_JSON}}` | JSON array of album links | See below |

### Photo Entry Format

Each photo entry in `{{PHOTO_ENTRIES}}` is a JS object:

```javascript
{id:"<asset-id>",src:"data:image/webp;base64,<thumbnail-base64>",date:"<ISO-date>"}
```

- `id`: The Immich asset ID (used for linking to the full photo in Immich)
- `src`: Base64-encoded WebP thumbnail from `immich_get_asset_thumbnail`
- `date`: ISO date string from the asset metadata (optional, used in list view)

Entries are comma-separated, one per line.

### Albums JSON Format

```javascript
{id:"<album-id>",name:"<Album Name>",total:<count>}
```

### Generation Workflow

1. **Get album data**: Call `immich_get_album` to get the album ID, name, and asset list
2. **Get thumbnails**: For each asset (up to a reasonable batch, e.g. 20-50), call `immich_get_asset_thumbnail` to get base64 thumbnails
3. **Read the template**: Read `assets/viewer-template.html` from the plugin root
4. **Replace placeholders**: Fill in all `{{...}}` placeholders with actual data
5. **Write the HTML**: Save to the outputs directory as `<album-name-slug>.html`
6. **Present to user**: Share the file link

### Performance Notes

- **PAGE_SIZE**: Keep at 6 for initial load, the rest lazy-loads
- **PHOTO_COUNT (TOTAL)**: This is the number of photos embedded in the HTML. Keep reasonable (20-50) for file size. The gallery shows `ALBUM_TOTAL` as the full count but only embeds `TOTAL` thumbnails.
- **Thumbnails**: Use the smallest available thumbnail size. Base64 WebP is preferred.
- For very large albums (100+), embed only the first 20-50 photos. The gallery's "Load more" button will show them progressively.

### Example: Generating a gallery

```
User: "Show me photos from Lanzarote Verde"

1. immich_list_albums() → find "Lanzarote Verde" album
2. immich_get_album(album_id) → get asset list (273 photos)
3. For first 20 assets: immich_get_asset_thumbnail(asset_id) → base64 thumbnails
4. Read assets/viewer-template.html
5. Replace:
   - {{ALBUM_NAME}} → "Lanzarote Verde"
   - {{ALBUM_TOTAL}} → "273"
   - {{SEARCH_QUERY}} → "&ldquo;show me photos from Lanzarote Verde&rdquo;"
   - {{IMMICH_URL}} → "https://fotos.txeo.club"
   - {{PAGE_SIZE}} → "6"
   - {{PHOTO_COUNT}} → "20"
   - {{PHOTO_ENTRIES}} → actual photo entries
   - {{ALBUMS_JSON}} → {id:"...",name:"Lanzarote Verde",total:273}
6. Save as lanzarote-verde.html
7. Present link to user
```

## Reference Files

- `references/geographic-search-patterns.md` — GPS bounding boxes of common destinations and search strategies
- `assets/index-template.html` — Dashboard template listing all saved gallery HTML files
- `assets/viewer-template.html` — Self-contained HTML gallery template with dark/light themes, multiple view modes, slideshow, Cowork Actions Panel, and keyboard navigation
