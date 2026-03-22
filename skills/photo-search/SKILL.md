---
name: photo-search
description: >
  Search and explore an Immich photo library using natural language, GPS locations,
  dates, people, cameras, and AI-powered visual search (CLIP).
  Use when the user says "find photos of", "search my photos", "show me pictures from",
  "where are my photos of", "do I have photos of", "find all screenshots",
  "photos taken with", "photos from 2019", "photos near", "photos of [person]",
  or any variation of searching, browsing, or exploring their photo library.
version: 0.1.0
---

# Photo Search

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
- **Quality note**: "12 appear to be screenshots (no GPS, screen resolution)"
- **Action prompt**: Suggest next steps (create album, refine search, clean up)

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
