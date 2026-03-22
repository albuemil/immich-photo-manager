---
description: Create a geographic album from a location
argument-hint: <location> [--share]
allowed-tools: ["mcp__immich__*"]
---

Create an Immich album for the location specified in $ARGUMENTS.

Follow the album-manager skill workflow:

1. Parse the location from $ARGUMENTS (e.g., "Rome, Italy" or "Lanzarote")
2. Search for photos at that location using GPS coordinates and CLIP semantic search
3. Report how many photos were found
4. Filter out screenshots and obvious non-travel photos
5. Create the album with the naming convention: [Country emoji] Place, Country
6. Add the curated photos
7. If --share flag is present, create a shared link for Gallery publication

Report the result:
```
✅ Created: 🇮🇹 Roma, Italia
   Photos: 47 selected from 203 found
   Date range: Jun 2023
   Shared: Yes — visible on Gallery
```
