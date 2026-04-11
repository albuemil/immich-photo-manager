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
async def get_connection_info(ctx: Context) -> str:
    """Return the Immich base URL and API key. Used by gallery HTML generation
    to embed the API key so the browser can fetch thumbnails directly.
    """
    client = _client(ctx)
    return json.dumps(
        {"base_url": client.base_url, "api_key": client.api_key[:8] + "..." + client.api_key[-4:] if len(client.api_key) > 12 else "***", "api_key_full": client.api_key},
        default=str,
    )


# ── HTTP App (for Streamable HTTP transport) ────────────────

app = mcp.streamable_http_app()
