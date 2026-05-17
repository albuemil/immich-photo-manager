"""
Immich MCP Server — Photo management tools for Claude.

Part of the immich-photo-manager plugin.
License: MIT
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from mcp.server.fastmcp import FastMCP, Context

from .immich_client import ImmichClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Initialize the Immich client on server startup."""
    client = ImmichClient()
    # Verify connection at startup
    try:
        await client.ping()
    except Exception as e:
        print(f"Warning: Could not connect to Immich at {client.base_url}: {e}")
    yield {"immich": client}


mcp = FastMCP(
    "immich-photo-manager",
    instructions="Intelligent photo management for Immich. Search, curate albums, and publish galleries.",
    lifespan=app_lifespan,
)


def _client(ctx: Context) -> ImmichClient:
    """Get the Immich client from the request context."""
    return ctx.request_context.lifespan_context["immich"]


# ── Health & Stats ──────────────────────────────────────────


@mcp.tool()
async def ping(ctx: Context) -> str:
    """Check Immich server connectivity. Returns 'pong' if connected."""
    result = await _client(ctx).ping()
    return json.dumps(result)


@mcp.tool()
async def get_server_version(ctx: Context) -> str:
    """Get the Immich server version."""
    result = await _client(ctx).get_server_version()
    return json.dumps(result)


@mcp.tool()
async def get_statistics(ctx: Context) -> str:
    """Get library statistics: total photos, videos, and storage usage."""
    result = await _client(ctx).get_statistics()
    return json.dumps(result)


# ── Credential Management ──────────────────────────────────


@mcp.tool()
async def update_credentials(ctx: Context, base_url: str, api_key: str) -> str:
    """Update the Immich connection credentials. Use this when the API key
    has been rotated or when the server URL has changed. The new credentials
    are persisted to disk and take effect immediately — no restart required.

    Args:
        base_url: The Immich server URL (e.g. 'https://photos.example.com').
        api_key: A valid Immich API key.
    """
    # 1. Create a new client with the provided credentials to validate them
    import os
    old_base = os.environ.get("IMMICH_BASE_URL", "")
    old_key = os.environ.get("IMMICH_API_KEY", "")

    try:
        # Temporarily set env vars so ImmichClient can init
        # (the config.json override hasn't been written yet)
        os.environ["IMMICH_BASE_URL"] = base_url
        os.environ["IMMICH_API_KEY"] = api_key
        new_client = ImmichClient()
    except Exception as e:
        # Restore old env vars
        os.environ["IMMICH_BASE_URL"] = old_base
        os.environ["IMMICH_API_KEY"] = old_key
        return json.dumps({
            "success": False,
            "error": f"Invalid credentials: {e}",
        })

    # 2. Verify the new credentials actually work
    try:
        await new_client.ping()
    except Exception as e:
        os.environ["IMMICH_BASE_URL"] = old_base
        os.environ["IMMICH_API_KEY"] = old_key
        return json.dumps({
            "success": False,
            "error": (
                f"Could not connect to Immich at {base_url}: {e}. "
                "Check the URL and API key are correct."
            ),
        })

    # 3. Persist to cache dir so they survive restarts
    try:
        config_path = ImmichClient.save_config(base_url, api_key)
    except RuntimeError as e:
        # Credentials work but can't persist — still swap the live client
        config_path = None

    # 4. Hot-swap the live client (no restart needed)
    ctx.request_context.lifespan_context["immich"] = new_client

    # 5. Get stats to confirm everything works
    try:
        stats = await new_client.get_statistics()
        photo_count = stats.get("photos", 0)
        video_count = stats.get("videos", 0)
    except Exception:
        photo_count = "?"
        video_count = "?"

    result = {
        "success": True,
        "base_url": base_url,
        "photos": photo_count,
        "videos": video_count,
    }
    if config_path:
        result["persisted_to"] = config_path
    else:
        result["warning"] = (
            "Credentials updated for this session but could NOT be persisted to disk. "
            "They will be lost on restart."
        )

    return json.dumps(result, default=str)


# ── Asset Info ──────────────────────────────────────────────


@mcp.tool()
async def get_asset_info(ctx: Context, asset_id: str) -> str:
    """Get full metadata for a specific asset (EXIF, GPS, dates, camera, etc).

    Args:
        asset_id: The unique ID of the asset.
    """
    result = await _client(ctx).get_asset(asset_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def update_asset_metadata(
    ctx: Context,
    asset_id: str,
    date_time_original: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    description: str = "",
    is_favorite: bool | None = None,
    rating: int | None = None,
) -> str:
    """Update metadata for a specific asset (dates, GPS coordinates, description, etc).
    Only provided fields are updated — omitted fields are left unchanged.

    Args:
        asset_id: The unique ID of the asset.
        date_time_original: ISO 8601 date string (e.g. '2019-07-14T15:23:41.000Z').
        latitude: GPS latitude (-90 to 90).
        longitude: GPS longitude (-180 to 180).
        description: Asset description text.
        is_favorite: Mark as favorite.
        rating: Rating from 1-5, or null for unrated.
    """
    fields: dict = {}
    if date_time_original:
        fields["dateTimeOriginal"] = date_time_original
    if latitude is not None:
        fields["latitude"] = latitude
    if longitude is not None:
        fields["longitude"] = longitude
    if description:
        fields["description"] = description
    if is_favorite is not None:
        fields["isFavorite"] = is_favorite
    if rating is not None:
        fields["rating"] = rating
    if not fields:
        return json.dumps({"error": "No fields to update. Provide at least one field."})
    result = await _client(ctx).update_asset(asset_id, **fields)
    return json.dumps(result, default=str)


@mcp.tool()
async def rotate_assets(
    ctx: Context,
    angle: int = 90,
    asset_ids: list[str] | None = None,
    album_id: str = "",
) -> str:
    """Rotate one or more assets. This is a non-destructive display transform —
    the original file is never modified.

    Provide EITHER asset_ids OR album_id. If album_id is given, all assets in
    that album are rotated.

    Args:
        angle: Rotation angle in degrees clockwise. Common values: 90, 180, 270. Default: 90.
        asset_ids: List of asset IDs to rotate.
        album_id: Rotate ALL assets in this album.
    """
    if angle % 90 != 0:
        return json.dumps({"error": "Angle must be a multiple of 90 (90, 180, 270)."})

    client = _client(ctx)

    # Resolve asset IDs from album if provided
    ids: list[str] = []
    album_name = ""
    if album_id:
        album = await client.get_album(album_id)
        album_name = album.get("albumName", "")
        ids = [a["id"] for a in album.get("assets", [])]
        if not ids:
            return json.dumps({"error": f"Album '{album_name}' is empty."})
    elif asset_ids:
        ids = asset_ids
    else:
        return json.dumps({"error": "Provide either asset_ids or album_id."})

    results: dict = {"rotated": 0, "failed": 0, "errors": []}
    for aid in ids:
        try:
            # Read current rotation and accumulate
            current_angle = 0
            try:
                edits = await client.get_asset_edits(aid)
                for edit in edits.get("edits", []):
                    if edit.get("action") == "rotate":
                        current_angle = edit["parameters"].get("angle", 0)
            except Exception:
                pass
            new_angle = (current_angle + angle) % 360
            if new_angle == 0:
                # Full circle — remove edits instead
                await client.delete_asset_edits(aid)
            else:
                await client.apply_asset_edits(aid, [
                    {"action": "rotate", "parameters": {"angle": new_angle}},
                ])
            results["rotated"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"asset_id": aid, "error": str(e)})

    results["angle"] = angle
    results["total_requested"] = len(ids)
    if album_name:
        results["album"] = album_name
    if not results["errors"]:
        del results["errors"]
    return json.dumps(results, default=str)


@mcp.tool()
async def revert_asset_edits(
    ctx: Context,
    asset_ids: list[str] | None = None,
    album_id: str = "",
) -> str:
    """Remove all non-destructive edits (rotation, crop, mirror) from assets,
    reverting them to their original appearance.

    Provide EITHER asset_ids OR album_id.

    Args:
        asset_ids: List of asset IDs to revert.
        album_id: Revert ALL assets in this album.
    """
    client = _client(ctx)

    ids: list[str] = []
    album_name = ""
    if album_id:
        album = await client.get_album(album_id)
        album_name = album.get("albumName", "")
        ids = [a["id"] for a in album.get("assets", [])]
        if not ids:
            return json.dumps({"error": f"Album '{album_name}' is empty."})
    elif asset_ids:
        ids = asset_ids
    else:
        return json.dumps({"error": "Provide either asset_ids or album_id."})

    results: dict = {"reverted": 0, "failed": 0, "errors": []}
    for aid in ids:
        try:
            await client.delete_asset_edits(aid)
            results["reverted"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"asset_id": aid, "error": str(e)})

    results["total_requested"] = len(ids)
    if album_name:
        results["album"] = album_name
    if not results["errors"]:
        del results["errors"]
    return json.dumps(results, default=str)


@mcp.tool()
async def get_map_markers(
    ctx: Context,
    file_created_after: str = "",
    file_created_before: str = "",
    is_favorite: bool | None = None,
) -> str:
    """Get all GPS map markers from the library. Returns asset IDs with lat/lon coordinates.
    Use this to discover all geographic locations in the photo library.

    Args:
        file_created_after: Optional ISO date filter (e.g. '2023-01-01').
        file_created_before: Optional ISO date filter.
        is_favorite: Filter favorites only.
    """
    result = await _client(ctx).get_map_markers(
        file_created_after=file_created_after or None,
        file_created_before=file_created_before or None,
        is_favorite=is_favorite,
    )
    return json.dumps({"total": len(result), "markers": result[:500]}, default=str)


# ── Search ──────────────────────────────────────────────────


@mcp.tool()
async def search_metadata(
    ctx: Context,
    city: str = "",
    state: str = "",
    country: str = "",
    make: str = "",
    model: str = "",
    taken_after: str = "",
    taken_before: str = "",
    is_favorite: bool | None = None,
    asset_type: str = "",
    page: int = 1,
    size: int = 50,
) -> str:
    """Search photos by EXIF metadata: location (city/state/country), camera (make/model),
    date range, favorites, and type (IMAGE/VIDEO).

    Args:
        city: Filter by city name (e.g. 'Barcelona', 'Cairo').
        state: Filter by state/region.
        country: Filter by country (e.g. 'Spain', 'Egypt').
        make: Camera manufacturer (e.g. 'Apple', 'Canon').
        model: Camera model (e.g. 'iPhone 14 Pro').
        taken_after: ISO date — only photos after this date.
        taken_before: ISO date — only photos before this date.
        is_favorite: Filter favorites only.
        asset_type: 'IMAGE' or 'VIDEO'.
        page: Page number (default 1).
        size: Results per page (default 50, max 200).
    """
    result = await _client(ctx).search_metadata(
        city=city or None,
        state=state or None,
        country=country or None,
        make=make or None,
        model=model or None,
        taken_after=taken_after or None,
        taken_before=taken_before or None,
        is_favorite=is_favorite,
        asset_type=asset_type or None,
        page=page,
        size=min(size, 200),
    )
    # Flatten the response for easier consumption
    assets = result.get("assets", {}).get("items", [])
    total = result.get("assets", {}).get("total", 0)
    return json.dumps({"total": total, "page": page, "assets": assets}, default=str)


@mcp.tool()
async def search_smart(
    ctx: Context,
    query: str,
    city: str = "",
    state: str = "",
    country: str = "",
    taken_after: str = "",
    taken_before: str = "",
    page: int = 1,
    size: int = 50,
) -> str:
    """AI-powered visual search using CLIP. Describe what you're looking for
    in natural language (e.g. 'sunset at the beach', 'birthday cake', 'mountain landscape').

    Can be combined with location and date filters.

    Args:
        query: Natural language description of what to find.
        city: Optional city filter.
        state: Optional state/region filter.
        country: Optional country filter.
        taken_after: ISO date — only photos after this date.
        taken_before: ISO date — only photos before this date.
        page: Page number (default 1).
        size: Results per page (default 50, max 200).
    """
    try:
        result = await _client(ctx).search_smart(
            query=query,
            city=city or None,
            state=state or None,
            country=country or None,
            taken_after=taken_after or None,
            taken_before=taken_before or None,
            page=page,
            size=min(size, 200),
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 500:
            return json.dumps({
                "error": "Smart search is not available on this Immich server.",
                "detail": (
                    "The Immich machine learning service may not be running, "
                    "or Smart Search (CLIP) is disabled. "
                    "Enable it in Administration > Settings > Machine Learning Settings > Smart Search. "
                    "See https://immich.app/docs/features/smart-search for details."
                ),
                "http_status": 500,
            })
        raise
    assets = result.get("assets", {}).get("items", [])
    total = result.get("assets", {}).get("total", 0)
    return json.dumps({"total": total, "page": page, "assets": assets}, default=str)


# ── Albums ──────────────────────────────────────────────────


@mcp.tool()
async def list_albums(ctx: Context, shared: bool | None = None) -> str:
    """List all albums with their asset counts.

    Args:
        shared: Filter by shared status. None = all albums.
    """
    result = await _client(ctx).list_albums(shared=shared)
    albums = [
        {
            "id": a["id"],
            "albumName": a.get("albumName", ""),
            "description": a.get("description", ""),
            "assetCount": a.get("assetCount", 0),
            "shared": a.get("shared", False),
            "hasSharedLink": a.get("hasSharedLink", False),
            "createdAt": a.get("createdAt", ""),
        }
        for a in result
    ]
    return json.dumps({"total": len(albums), "albums": albums}, default=str)


@mcp.tool()
async def get_album(ctx: Context, album_id: str) -> str:
    """Get album details including all asset IDs.

    Args:
        album_id: The album's unique ID.
    """
    result = await _client(ctx).get_album(album_id)
    assets = result.get("assets", [])
    asset_ids = [a["id"] for a in assets]
    return json.dumps(
        {
            "id": result["id"],
            "albumName": result.get("albumName", ""),
            "description": result.get("description", ""),
            "assetCount": result.get("assetCount", 0),
            "shared": result.get("shared", False),
            "hasSharedLink": result.get("hasSharedLink", False),
            "createdAt": result.get("createdAt", ""),
            "updatedAt": result.get("updatedAt", ""),
            "asset_ids": asset_ids,
        },
        default=str,
    )


@mcp.tool()
async def create_album(
    ctx: Context, name: str, description: str = "", asset_ids: list[str] | None = None
) -> str:
    """Create a new album.

    Args:
        name: Album name (e.g. 'Roma, Italia').
        description: Optional description.
        asset_ids: Optional list of asset IDs to add immediately.
    """
    result = await _client(ctx).create_album(
        name=name, description=description, asset_ids=asset_ids
    )
    return json.dumps(
        {
            "id": result["id"],
            "albumName": result.get("albumName", ""),
            "assetCount": result.get("assetCount", 0),
        },
        default=str,
    )


@mcp.tool()
async def update_album(
    ctx: Context, album_id: str, name: str = "", description: str = ""
) -> str:
    """Update an album's name or description.

    Args:
        album_id: The album's unique ID.
        name: New name (empty = don't change).
        description: New description (empty = don't change).
    """
    result = await _client(ctx).update_album(
        album_id=album_id,
        name=name or None,
        description=description if description else None,
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def delete_album(ctx: Context, album_id: str) -> str:
    """Delete an album. Photos are NOT deleted, only the album container.

    Args:
        album_id: The album's unique ID.
    """
    await _client(ctx).delete_album(album_id)
    return json.dumps({"deleted": True, "album_id": album_id})


@mcp.tool()
async def add_assets_to_album(ctx: Context, album_id: str, asset_ids: list[str]) -> str:
    """Add photos/videos to an album.

    Args:
        album_id: Target album ID.
        asset_ids: List of asset IDs to add.
    """
    result = await _client(ctx).add_assets_to_album(album_id, asset_ids)
    return json.dumps({"album_id": album_id, "added": len(asset_ids), "result": result}, default=str)


@mcp.tool()
async def remove_assets_from_album(ctx: Context, album_id: str, asset_ids: list[str]) -> str:
    """Remove photos/videos from an album. The photos themselves are NOT deleted.

    Args:
        album_id: Target album ID.
        asset_ids: List of asset IDs to remove.
    """
    result = await _client(ctx).remove_assets_from_album(album_id, asset_ids)
    return json.dumps({"album_id": album_id, "removed": len(asset_ids), "result": result}, default=str)


# ── Thumbnails ──────────────────────────────────────────────


@mcp.tool()
async def get_asset_thumbnail(ctx: Context, asset_id: str, size: str = "thumbnail") -> str:
    """Get a base64-encoded thumbnail for a single asset.
    Returns JSON with 'data' (base64 string) and 'type' (mime type).
    Size can be 'thumbnail' (250px, fast) or 'preview' (1440px, larger).

    Args:
        asset_id: The unique ID of the asset.
        size: 'thumbnail' (250px) or 'preview' (1440px). Default: thumbnail.
    """
    result = await _client(ctx).get_asset_thumbnail(asset_id, size)
    return json.dumps(result)


@mcp.tool()
async def get_album_thumbnails(
    ctx: Context, album_id: str, size: str = "thumbnail", limit: int = 20
) -> str:
    """Get base64-encoded thumbnails for all photos in an album (up to limit).
    Returns album info and a list of thumbnail entries with asset IDs, base64 data,
    filenames, and dates. Used for generating visual HTML galleries.

    Args:
        album_id: The album's unique ID.
        size: 'thumbnail' (250px) or 'preview' (1440px). Default: thumbnail.
        limit: Maximum number of thumbnails to fetch (default 20, max 50).
    """
    result = await _client(ctx).get_album_thumbnails(
        album_id, size, min(limit, 50)
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def get_thumbnails_batch(
    ctx: Context, asset_ids: list[str], size: str = "thumbnail", limit: int = 20
) -> str:
    """Get base64-encoded thumbnails for a list of asset IDs WITHOUT needing an album.
    Use this when you have search results (asset IDs) and want to display them visually
    without creating a temporary album. Returns thumbnail entries with asset IDs, base64 data,
    filenames, and dates.

    Args:
        asset_ids: List of asset IDs to fetch thumbnails for.
        size: 'thumbnail' (250px) or 'preview' (1440px). Default: thumbnail.
        limit: Maximum number of thumbnails to fetch (default 20, max 50).
    """
    result = await _client(ctx).get_thumbnails_batch(
        asset_ids, size, min(limit, 50)
    )
    return json.dumps(result, default=str)


# ── Shared Links ────────────────────────────────────────────


@mcp.tool()
async def list_shared_links(ctx: Context) -> str:
    """List all shared links (public URLs for albums/assets)."""
    result = await _client(ctx).list_shared_links()
    links = [
        {
            "id": link["id"],
            "key": link.get("key", ""),
            "type": link.get("type", ""),
            "description": link.get("description", ""),
            "album_id": link.get("album", {}).get("id", "") if link.get("album") else "",
            "album_name": link.get("album", {}).get("albumName", "") if link.get("album") else "",
        }
        for link in result
    ]
    return json.dumps({"total": len(links), "links": links}, default=str)


@mcp.tool()
async def create_shared_link(
    ctx: Context,
    album_id: str,
    allow_download: bool = True,
    show_metadata: bool = True,
    description: str = "",
) -> str:
    """Create a public shared link for an album. This makes the album visible
    in the Immich Gallery frontend.

    Args:
        album_id: The album to share.
        allow_download: Allow visitors to download photos.
        show_metadata: Show EXIF metadata to visitors.
        description: Optional link description.
    """
    result = await _client(ctx).create_shared_link(
        album_id=album_id,
        allow_download=allow_download,
        show_metadata=show_metadata,
        description=description,
    )
    return json.dumps(
        {
            "id": result.get("id", ""),
            "key": result.get("key", ""),
            "album_id": album_id,
            "url": f"{_client(ctx).base_url}/share/{result.get('key', '')}",
        },
        default=str,
    )


@mcp.tool()
async def get_shared_link(ctx: Context, link_id: str) -> str:
    """Get full details of a shared link including permissions and assets.

    Args:
        link_id: The shared link's unique ID (from list_shared_links).
    """
    try:
        result = await _client(ctx).get_shared_link(link_id)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def update_shared_link(
    ctx: Context,
    link_id: str,
    allow_download: bool | None = None,
    show_metadata: bool | None = None,
    allow_upload: bool | None = None,
    description: str | None = None,
    expiry_at: str | None = None,
) -> str:
    """Update a shared link's permissions or expiry.

    Args:
        link_id: The shared link's unique ID.
        allow_download: Allow visitors to download photos.
        show_metadata: Show EXIF metadata to visitors.
        allow_upload: Allow visitors to upload photos.
        description: Link description. Pass empty string to clear.
        expiry_at: Expiry date (ISO 8601). Pass empty string to remove expiry.
    """
    fields: dict = {}
    if allow_download is not None:
        fields["allowDownload"] = allow_download
    if show_metadata is not None:
        fields["showMetadata"] = show_metadata
    if allow_upload is not None:
        fields["allowUpload"] = allow_upload
    if description is not None:
        fields["description"] = description  # empty string clears it
    if expiry_at is not None:
        fields["expiresAt"] = expiry_at if expiry_at else None  # empty string removes expiry
    if not fields:
        return json.dumps({"error": "No fields to update."})
    try:
        result = await _client(ctx).update_shared_link(link_id, **fields)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def delete_shared_link(ctx: Context, link_id: str) -> str:
    """Delete (revoke) a shared link. The link will no longer be accessible.

    Args:
        link_id: The shared link's unique ID.
    """
    try:
        await _client(ctx).delete_shared_link(link_id)
        return json.dumps({"deleted": True, "link_id": link_id})
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def get_connection_info(ctx: Context) -> str:
    """Return the Immich base URL and a masked API key.  Used by skills to
    populate the {{IMMICH_URL}} placeholder in gallery templates.  The API
    key is intentionally masked — thumbnails are delivered as base64 data
    URIs, so the plaintext key is never needed in generated HTML.
    """
    client = _client(ctx)
    key = client.api_key
    masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    return json.dumps(
        {"base_url": client.base_url, "api_key_masked": masked},
        default=str,
    )


# ── People & Faces ─────────────────────────────────────────


@mcp.tool()
async def list_people(
    ctx: Context, page: int = 1, size: int = 50, with_hidden: bool = False
) -> str:
    """List all recognized people in the library (paginated).

    Args:
        page: Page number (default 1).
        size: Results per page (default 50).
        with_hidden: Include hidden people (default False).
    """
    result = await _client(ctx).list_people(page=page, size=size, with_hidden=with_hidden)
    people = result.get("people", [])
    total = result.get("total", len(people))
    return json.dumps({"total": total, "page": page, "people": people}, default=str)


@mcp.tool()
async def get_person(ctx: Context, person_id: str) -> str:
    """Get full details for a specific person.

    Args:
        person_id: The person's unique ID.
    """
    result = await _client(ctx).get_person(person_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def update_person(
    ctx: Context,
    person_id: str,
    name: str = "",
    birth_date: str = "",
    is_hidden: bool | None = None,
    is_favorite: bool | None = None,
    feature_face_asset_id: str = "",
    color: str = "",
) -> str:
    """Update a person's details. Only provided fields are changed.

    Args:
        person_id: The person's unique ID.
        name: Display name for this person.
        birth_date: Birth date in ISO format (e.g. '1990-05-15').
        is_hidden: Hide this person from the People view.
        is_favorite: Mark this person as a favorite.
        feature_face_asset_id: Asset ID to use as the person's feature face.
        color: Color label for this person.
    """
    fields: dict = {}
    if name:
        fields["name"] = name
    if birth_date:
        fields["birthDate"] = birth_date
    if is_hidden is not None:
        fields["isHidden"] = is_hidden
    if is_favorite is not None:
        fields["isFavorite"] = is_favorite
    if feature_face_asset_id:
        fields["featureFaceAssetId"] = feature_face_asset_id
    if color:
        fields["color"] = color
    if not fields:
        return json.dumps({"error": "No fields to update. Provide at least one field."})
    result = await _client(ctx).update_person(person_id, **fields)
    return json.dumps(result, default=str)


@mcp.tool()
async def merge_people(ctx: Context, person_id: str, merge_ids: list[str]) -> str:
    """Merge multiple people into one. DESTRUCTIVE: the people in merge_ids
    are permanently absorbed into person_id. All their face assignments are
    transferred to the target person. This cannot be undone.

    Args:
        person_id: The target person to keep (all faces merge into this person).
        merge_ids: List of person IDs to merge into the target. These people will cease to exist.
    """
    result = await _client(ctx).merge_people(person_id, merge_ids)
    return json.dumps(result, default=str)


@mcp.tool()
async def search_people(ctx: Context, name: str, with_hidden: bool = False) -> str:
    """Search for people by name.

    Args:
        name: Name or partial name to search for.
        with_hidden: Include hidden people in results (default False).
    """
    result = await _client(ctx).search_people(name, with_hidden=with_hidden)
    return json.dumps(result, default=str)


@mcp.tool()
async def get_person_thumbnail(ctx: Context, person_id: str) -> str:
    """Get a base64-encoded face thumbnail for a person.
    Returns JSON with 'data' (base64 string) and 'type' (mime type).

    Args:
        person_id: The person's unique ID.
    """
    result = await _client(ctx).get_person_thumbnail(person_id)
    return json.dumps(result)


@mcp.tool()
async def get_asset_faces(ctx: Context, asset_id: str) -> str:
    """Get all detected faces in a specific asset, with their person assignments.

    Args:
        asset_id: The asset's unique ID.
    """
    result = await _client(ctx).get_asset_faces(asset_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def reassign_face(ctx: Context, face_id: str, person_id: str) -> str:
    """Reassign a detected face to a different person. Use this to correct
    face recognition mistakes.

    Args:
        face_id: The face detection ID (from get_asset_faces).
        person_id: The person to assign this face to.
    """
    result = await _client(ctx).reassign_face(face_id, person_id)
    return json.dumps(result, default=str)


# ── Trash ──────────────────────────────────────────────────


@mcp.tool()
async def delete_assets(ctx: Context, asset_ids: list[str], force: bool = False) -> str:
    """Delete assets by moving them to trash, or permanently delete them.

    By default (force=False), assets are moved to trash and can be restored.
    With force=True, assets are PERMANENTLY DELETED and cannot be recovered.

    Args:
        asset_ids: List of asset IDs to delete.
        force: If True, permanently delete. If False (default), move to trash.
    """
    await _client(ctx).delete_assets(asset_ids, force=force)
    return json.dumps({
        "deleted": len(asset_ids),
        "force": force,
        "warning": "Assets permanently deleted." if force else "Assets moved to trash. Use restore_assets to undo.",
    })


@mcp.tool()
async def empty_trash(ctx: Context) -> str:
    """Permanently delete ALL assets currently in the trash.
    WARNING: This is IRREVERSIBLE. All trashed assets will be permanently destroyed.
    """
    await _client(ctx).empty_trash()
    return json.dumps({"success": True, "warning": "All trashed assets have been permanently deleted."})


@mcp.tool()
async def restore_trash(ctx: Context) -> str:
    """Restore ALL trashed assets back to the library."""
    await _client(ctx).restore_trash()
    return json.dumps({"success": True, "message": "All trashed assets have been restored."})


@mcp.tool()
async def restore_assets(ctx: Context, asset_ids: list[str]) -> str:
    """Restore specific assets from trash back to the library.

    Args:
        asset_ids: List of asset IDs to restore from trash.
    """
    await _client(ctx).restore_assets(asset_ids)
    return json.dumps({"restored": len(asset_ids)})


# ── Duplicates ─────────────────────────────────────────────


@mcp.tool()
async def get_duplicates(ctx: Context) -> str:
    """Get all ML-detected duplicate asset groups. Immich uses machine learning
    to identify visually similar photos. Returns groups of duplicate assets
    with similarity scores.
    """
    result = await _client(ctx).get_duplicates()
    return json.dumps(result, default=str)


@mcp.tool()
async def resolve_duplicates(ctx: Context, groups: list[dict]) -> str:
    """Resolve duplicate groups by specifying which assets to keep and which to trash.

    Each group dict must contain:
    - duplicateId: The duplicate group ID (from get_duplicates)
    - assetIds: List of asset IDs to KEEP
    - trashIds: List of asset IDs to move to TRASH

    Args:
        groups: List of resolution decisions, each with duplicateId, assetIds (keep), and trashIds (trash).
    """
    await _client(ctx).resolve_duplicates(groups)
    return json.dumps({
        "resolved": len(groups),
        "message": "Duplicate groups resolved. Trashed assets can be restored from trash.",
    })


# ── Tags ──────────────────────────────────────────────────


@mcp.tool()
async def list_tags(ctx: Context) -> str:
    """List all tags with their IDs, names, and colors."""
    try:
        result = await _client(ctx).list_tags()
        return json.dumps({"total": len(result), "tags": result}, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def get_tag(ctx: Context, tag_id: str) -> str:
    """Get details for a specific tag.

    Args:
        tag_id: The tag's unique ID.
    """
    try:
        result = await _client(ctx).get_tag(tag_id)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def create_tag(ctx: Context, name: str, color: str = "") -> str:
    """Create a new tag.

    Args:
        name: Tag name (e.g. 'Vacation', 'Family', 'Work').
        color: Optional hex color (e.g. '#FF5733').
    """
    try:
        result = await _client(ctx).create_tag(name, color=color or None)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def update_tag(ctx: Context, tag_id: str, name: str | None = None, color: str | None = None) -> str:
    """Update a tag's name or color.

    Args:
        tag_id: The tag's unique ID.
        name: New name. Omit to leave unchanged.
        color: New hex color. Omit to leave unchanged.
    """
    fields: dict = {}
    if name is not None:
        fields["name"] = name
    if color is not None:
        fields["color"] = color
    if not fields:
        return json.dumps({"error": "No fields to update. Provide name or color."})
    try:
        result = await _client(ctx).update_tag(tag_id, **fields)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def delete_tag(ctx: Context, tag_id: str) -> str:
    """Delete a tag. The tag is removed from all assets.

    Args:
        tag_id: The tag's unique ID.
    """
    try:
        await _client(ctx).delete_tag(tag_id)
        return json.dumps({"deleted": True, "tag_id": tag_id})
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def tag_assets(ctx: Context, tag_id: str, asset_ids: list[str]) -> str:
    """Add a tag to multiple assets.

    Args:
        tag_id: The tag to apply.
        asset_ids: List of asset IDs to tag.
    """
    if not asset_ids:
        return json.dumps({"error": "asset_ids cannot be empty."})
    try:
        result = await _client(ctx).tag_assets(tag_id, asset_ids)
        return json.dumps({"tag_id": tag_id, "tagged": len(asset_ids), "result": result}, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def untag_assets(ctx: Context, tag_id: str, asset_ids: list[str]) -> str:
    """Remove a tag from multiple assets.

    Args:
        tag_id: The tag to remove.
        asset_ids: List of asset IDs to untag.
    """
    if not asset_ids:
        return json.dumps({"error": "asset_ids cannot be empty."})
    try:
        result = await _client(ctx).untag_assets(tag_id, asset_ids)
        return json.dumps({"tag_id": tag_id, "untagged": len(asset_ids), "result": result}, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


# ── Upload ─────────────────────────────────────────────────


ALLOWED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".mp4", ".mov", ".gif", ".webp"}
MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25MB


@mcp.tool()
async def upload_asset(ctx: Context, file_path: str, album_id: str = "") -> str:
    """Upload a photo or video to Immich from a local file.

    Limits: 25MB max, media files only (jpg, png, heic, mp4, mov, gif, webp).
    The original file is not modified or deleted.

    Args:
        file_path: Absolute path to the file to upload.
        album_id: Optional album ID to add the asset to after upload.
    """
    import os

    if not os.path.isfile(file_path):
        return json.dumps({"error": f"File not found: {file_path}"})

    # Resolve symlinks and verify real path
    real_path = os.path.realpath(file_path)
    if real_path != file_path and os.path.islink(file_path):
        return json.dumps({"error": "Symlinks are not allowed for security."})
    file_path = real_path

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return json.dumps({"error": f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}"})

    size = os.path.getsize(file_path)
    if size > MAX_UPLOAD_SIZE:
        return json.dumps({"error": f"File too large: {size / 1024 / 1024:.1f}MB. Max: 25MB."})

    client = _client(ctx)
    try:
        result = await client.upload_asset(file_path)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})

    if album_id and result.get("id"):
        try:
            await client.add_assets_to_album(album_id, [result["id"]])
            result["added_to_album"] = album_id
        except Exception as e:
            result["album_error"] = str(e)

    result["uploaded_file"] = os.path.basename(file_path)
    result["size_mb"] = round(size / 1024 / 1024, 2)
    return json.dumps(result, default=str)


# ── Asset List ─────────────────────────────────────────────


@mcp.tool()
async def list_assets(
    ctx: Context,
    is_favorite: bool | None = None,
    is_archived: bool | None = None,
    is_trashed: bool | None = None,
    asset_type: str = "",
    page: int = 1,
    size: int = 50,
) -> str:
    """List assets with optional filters. Unlike search, this returns all assets
    matching the filter criteria without a search query.

    Args:
        is_favorite: Filter by favorites only.
        is_archived: Filter by archived status.
        is_trashed: Filter by trashed status.
        asset_type: 'IMAGE' or 'VIDEO'.
        page: Page number (default 1).
        size: Results per page (default 50, max 200).
    """
    try:
        result = await _client(ctx).list_assets(
            is_favorite=is_favorite,
            is_archived=is_archived,
            is_trashed=is_trashed,
            asset_type=asset_type or None,
            page=page,
            size=min(size, 200),
        )
        assets = result.get("assets", {}).get("items", [])
        total = result.get("assets", {}).get("total", 0)
        return json.dumps({"total": total, "page": page, "assets": assets}, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


# ── HTTP App (for Streamable HTTP transport) ────────────────

app = mcp.streamable_http_app()
