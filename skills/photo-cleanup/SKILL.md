---
name: photo-cleanup
description: >
  Detect and remove screenshots, duplicates, and low-quality photos from an Immich library.
  Use when the user says "clean up my photos", "remove screenshots",
  "find duplicates", "deduplicate", "photo cleanup", "library cleanup",
  "how many screenshots do I have", "free up space", "remove junk photos",
  or any variation of cleaning, deduplicating, or optimizing a photo library.
version: 0.1.0
---

# Photo Cleanup

Intelligent photo library cleanup for Immich. Identifies and helps remove screenshots, duplicates, and low-quality images while protecting valuable photos.

## Safety First

**NEVER delete photos automatically.** Always:
1. Identify candidates for removal
2. Present findings with counts and examples to the user
3. Get explicit approval before any deletion
4. Prefer archiving over deleting when possible (Immich archive = hidden, not destroyed)

## Cleanup Categories

### 1. Screenshot Detection

Screenshots are the #1 source of library bloat. Detection criteria (combine multiple signals):

| Signal | Weight | How to detect |
|--------|--------|--------------|
| Screen resolution | High | Dimensions match known screen sizes exactly |
| No GPS data | Medium | EXIF GPS fields empty |
| No lens info | Medium | No focal length, aperture, or lens model |
| Filename pattern | Low | Contains "Screenshot", "Screen Shot", "Captura" |
| No camera make/model | Medium | Missing or generic device info |

**Screen resolutions to flag** (exact pixel matches):

iPhone screens: 750x1334, 1125x2436, 1170x2532, 1242x2688, 1284x2778, 1290x2796
Mac screens: 1920x1080, 2560x1440, 2560x1600, 2880x1800, 3024x1964, 3456x2234
Common Android: 1080x1920, 1080x2340, 1080x2400, 1440x2560, 1440x3200

A photo matching 2+ signals is a strong screenshot candidate. Report confidence level:
- **High confidence**: Screen resolution + no GPS + no lens → almost certainly screenshot
- **Medium confidence**: Screen resolution only, or no GPS + no lens but non-standard resolution
- **Low confidence**: Only one signal matches → needs human review

### 2. Duplicate Detection

Sources of duplicates:
- Same photo in Google Fotos AND Apple Fotos (most common)
- Multiple exports of the same original (different formats: HEIC, JPEG, PNG)
- Burst photos that look identical
- Edited versions alongside originals

Detection strategy:
1. **Exact duplicates**: Same file hash (SHA-256) → safe to remove the copy
2. **Format duplicates**: Same timestamp + same dimensions, different format → keep highest quality (HEIC > JPEG > PNG)
3. **Near-duplicates**: Same timestamp + similar dimensions + high CLIP similarity → present to user
4. **Burst groups**: Sequential timestamps (< 2 seconds apart) + same location → let user pick best

### 3. Low-Quality Photo Detection

| Issue | Detection | Action |
|-------|-----------|--------|
| Very dark | Average brightness < 20 (if available) | Flag for review |
| Very blurry | Motion blur EXIF hints, very low sharpness | Flag for review |
| Tiny resolution | Under 640x480 | Flag for review |
| Corrupt/partial | File size anomalies, unreadable EXIF | Flag for review |

**Important**: Some intentionally dark or blurry photos are artistic. Always flag, never auto-remove.

## Cleanup Workflow

### Quick Scan (recommended first step)

1. Get library statistics: total photos, videos, storage
2. Estimate screenshots: search for assets with screen-resolution dimensions
3. Estimate duplicates: search for same-timestamp clusters
4. Report summary:

```
📊 Library: {total} assets ({size})
📱 Probable screenshots: ~{count} ({percentage}%)
🔄 Probable duplicates: ~{count} ({percentage}%)
📉 Low quality candidates: ~{count} ({percentage}%)
💾 Estimated space recoverable: {size}
```

### Targeted Cleanup

After the quick scan, clean up category by category:

1. **Screenshots first** (highest confidence, biggest impact)
   - Search by screen resolution dimensions
   - Filter: no GPS + no lens info
   - Present list grouped by confidence level
   - User approves → archive or delete

2. **Duplicates second** (requires more care)
   - Find exact hash duplicates first (safest)
   - Then find format duplicates (same photo, different format)
   - Keep the highest quality version
   - User approves → delete copies

3. **Low quality last** (most subjective)
   - Present candidates with thumbnails if possible
   - User decides per-photo or in batches

### Progress Reporting

For large cleanups, report progress every 500 assets processed:
```
🧹 Scanning... {processed} / {total} ({percentage}%)
Found so far: {screenshots} screenshots, {duplicates} duplicates
```

## Cleanup by Source

Since Immich imports from specific folders, cleanup can target specific sources:

- **Google Photos imports** — Oldest photos, most likely to have duplicates with Apple Photos
- **Apple Photos imports** — Higher quality (HEIC), but overlaps with Google
- **Manual imports** — Manually organized, least likely to need cleanup
- **Screen capture folders** — ALL screenshots by definition

## What NOT to Clean

- Photos with faces detected (Immich's face recognition) — may be valuable memories
- Photos in existing albums — someone already curated these
- Favorited photos — explicitly marked as wanted
- Videos — different cleanup criteria, handle separately
- Photos with GPS in known "home" locations — daily life photos may seem like junk but are memories
