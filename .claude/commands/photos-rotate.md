Process the "rotate LEFT" and "rotate RIGHT" Immich albums:

1. Use `mcp__immich__list_albums` to find albums named "rotate LEFT" and "rotate RIGHT".
2. For each album that has assets (assetCount > 0):
   - Use `mcp__immich__get_album` to retrieve all asset IDs.
   - Use `mcp__immich__rotate_assets` with the album_id:
     - "rotate LEFT" → angle: 270 (counter-clockwise)
     - "rotate RIGHT" → angle: 90 (clockwise)
   - Use `mcp__immich__remove_assets_from_album` to clear all assets from the album.
3. Report how many photos were rotated and removed from each album.
