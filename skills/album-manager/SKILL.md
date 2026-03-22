---
name: album-manager
description: >
  Create, curate, and publish Immich albums organized by geography, theme, or custom criteria.
  Use when the user says "create an album", "organize my photos by location",
  "make a gallery album", "curate photos from Italy", "publish album",
  "geographic albums", "album from my trip to X", "share this album",
  or any variation of creating, managing, or publishing photo albums in Immich.
  Also triggers on "what albums do I have", "list albums", "album stats".
version: 0.1.0
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

## Reference Files

See `references/geographic-search-patterns.md` for GPS bounding boxes of common destinations and search strategies.
