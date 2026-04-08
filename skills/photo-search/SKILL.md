---
name: photo-search
description: >
  Search and explore an Immich photo library using natural language, GPS locations,
  dates, people, cameras, and AI-powered visual search (CLIP).
  Use when the user says "find photos of", "search my photos", "show me pictures from",
  "where are my photos of", "do I have photos of", "find all screenshots",
  "photos taken with", "photos from 2019", "photos near", "photos of [person]",
  or any variation of searching, browsing, or exploring their photo library.
version: 1.0.0
---

# Photo Search

## ⚠️ Connection Required — ALWAYS CHECK FIRST

**Before doing ANYTHING else in this skill, call `ping` on the Immich MCP server.**

- If `ping` succeeds → proceed with the skill normally.
- If `ping` fails or the MCP tools are not available → **STOP. Do not continue.** Tell the user:

> ❌ **Immich is not connected.** This plugin needs a running Immich MCP server to work.
>
> Run **/setup** to configure your Immich connection. You'll need:
> 1. Your Immich server URL (e.g., `http://192.168.1.100:2283`)
> 2. An Immich API key ([how to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key))
> 3. The MCP server running (`./immich-mcp-server`)
>
> Nothing in this plugin will work until the connection is configured.

**Do NOT skip this check. Do NOT try to run any other tool first. Always ping, always block if it fails.**

Natural language photo search across an Immich library. Translates user intent into the optimal combination of Immich search APIs.

## Search Capabilities

Immich supports multiple search dimensions. Combine them for precise results:

| Dimension | MCP Tool Parameter | Example |
|-----------|-------------------|---------|
| **Visual/semantic** | `query` (CLIP) | "sunset at the beach", "birthday cake" |
| **Location (GPS)** | `latitude`, `longitude`, `radius_km` | Near Rome (41.90, 12.50, 15km) |
| **Location (text)** | `city`, `state`, `country` | city="Barcelona" |
| **Date range** | `date_from`, `date_to` | 2023-06-01 to 2023-06-30 |
| **Camera/device** | `make`, `model` | make="Apple", model="iPhone 14 Pro" |
| **File type** | `type` | "IMAGE" or "VIDEO" |
| **Person** | `person_name` | "Alice", "Bob" (requires face recognition) |
| **Favorites** | `is_favorite` | true |
| **Archived** | `is_archived` | true/false |

## Query Translation

Convert natural language to search parameters:

| User says | Search strategy |
|-----------|----------------|
| "photos from my Italy trip" | GPS bounding box for Italy OR CLIP "Italy" + date if known |
| "pictures of Alice" | `person_name="Alice"` |
| "screenshots on my phone" | `make="Apple"` + screen resolution dimensions + no GPS |
| "sunset photos" | CLIP `query="sunset"` |
| "photos from last Christmas" | `date_from="2025-12-20"`, `date_to="2025-12-31"` |
| "my best photos" | `is_favorite=true` |
| "photos taken with iPhone" | `make="Apple"` + `type="IMAGE"` |
| "videos from Barcelona" | GPS Barcelona + `type="VIDEO"` |

## Search Workflow

1. **Parse intent**: Identify which dimensions the user is asking about
2. **Translate to parameters**: Map natural language to MCP tool parameters
3. **Execute search**: Call `immich_search_assets` with combined parameters
4. **Present results**: Show count, date range, location spread, sample thumbnails
5. **Offer actions**: "Want me to create an album from these?" / "Should I narrow the search?"

## Result Presentation

When showing search results:

- **Count first**: "Found 147 photos matching your search"
- **Date range**: "Spanning from June 2019 to June 2023"
- **Location summary**: "Across 3 locations: Rome, Florence, Venice"
- **Visual preview**: Show thumbnail samples inline (see Thumbnail Display below)
- **Quality note**: "12 appear to be screenshots (no GPS, screen resolution)"
- **Action prompt**: Suggest next steps (create album, refine search, clean up)

## Thumbnail Display

**ALWAYS show visual thumbnails** when presenting search results. Never list asset IDs as plain text — users need to *see* their photos.

### How it works — the HTML pipeline

Thumbnail data (base64 WebP) always exceeds the Cowork context window limit. **This is expected.** Cowork automatically saves the response to a temp file. The pipeline:

1. Call `get_album_thumbnails` → response overflows to temp file (this is normal)
2. Extract the file path from the overflow message
3. Use Python to read the file, build an HTML viewer with embedded images
4. Write HTML to Documents folder, share via `computer://` link

**Cost: ~580 tokens per request regardless of photo count.** The base64 never enters context.

### For search results

After a search returns asset IDs, you can show thumbnails by:
1. Creating a temporary album with the results, OR
2. Using `get_asset_thumbnail` one at a time for 1-3 specific photos (these also overflow but are simpler for single confirmations)

For bulk results, prefer `get_album_thumbnails` if the photos are already in an album.

### HTML viewer standard

**IMPORTANT: Use the canonical template at `assets/viewer-template.html`.**
Read the template file, replace `{{PLACEHOLDERS}}` with actual data, and write the result.
See `skills/album-manager/references/viewer-template-spec.md` for the full placeholder list.

The template includes:
- **🗾 header** with icon scroll-shrink (38px→26px) + shadow effect
- **5 view modes**: Detail, Icon, List, Masonry, Gallery
- **3 themes**: Light (warm parchment), System, Dark (warm espresso)
- **Gallery overlay** with keyboard nav, swipe, slideshow
- **Cowork Actions Panel** — floating toolbar for web↔chat interactivity
- **Related Albums** section with polaroid cards

**After generating a viewer, also update the index dashboard** (`index.html`)
by rebuilding it from `assets/index-template.html`. See viewer-template-spec.md.

### ⚠️ Placeholder Rules (IMPORTANT)

- **`{{PAGE_SIZE}}`**, **`{{PHOTO_COUNT}}`**, **`{{ALBUM_TOTAL}}`**: Must be **plain integers** (e.g. `200`, not `200+` or `"200"`). These are injected directly into JavaScript.
- **`{{ALBUM_NAME}}`**, **`{{SEARCH_QUERY}}`**, **`{{IMMICH_URL}}`**: Can be any string.
- **`{{PHOTO_ENTRIES}}`**: Must be valid JS object literals, comma-separated.

### Guidelines
- Show **all photos** for small sets (≤50), use `count=20` + pagination for larger sets
- Every thumbnail MUST link to its Immich entity
- After showing results, offer: "Want to see more?", "Create an album with these?", "Refine search?"

## Advanced Search Patterns

### Finding duplicates
Search the same date range across Google Photos and Apple Photos import folders. Compare by:
- Exact file hash (identical copies)
- Same timestamp + similar dimensions (same photo, different export)
- CLIP similarity (visually identical, different compression)

### Finding screenshots
Combine: no GPS data + screen-resolution dimensions + no lens/focal length EXIF. Common screen resolutions:
- iPhone: 1170x2532, 1125x2436, 1242x2688, 750x1334, 1290x2796
- Mac: 2560x1600, 2880x1800, 3024x1964, 1920x1080
- Android: 1080x2400, 1080x2340, 1440x3200

### Finding low-quality photos
- Very small file size for resolution (over-compressed)
- Motion blur indicators in EXIF (slow shutter + no stabilization)
- Very dark or very bright exposure values

## Pagination

Immich API returns paginated results. For large result sets:
- Fetch first page to get total count
- Report total to user before fetching all
- For operations (album creation, deletion), fetch all pages
- For browsing, show first page and offer to load more
