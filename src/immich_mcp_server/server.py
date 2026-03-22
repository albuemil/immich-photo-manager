"""
Immich MCP Server — Photo management tools for Claude.

Part of the immich-photo-manager plugin.
License: MIT
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

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


def _client(ctx) -> ImmichClient:
    """Get the Immich client from the request context."""
    return ctx.request_context.lifespan_context["immich"]


# ── Health & Stats ──────────────────────────────────────────


@mcp.tool()
async def ping(ctx) -> str:
    """Check Immich server connectivity. Returns 'pong' if connected."""
    result = await _client(ctx).ping()
    return json.dumps(result)


@mcp.tool()
async def get_server_version(ctx) -> str:
    """Get the Immich server version."""
    result = await _client(ctx).get_server_version()
    return json.dumps(result)


@mcp.tool()
async def get_statistics(ctx) -> str:
    """Get library statistics: total photos, videos, and storage usage."""
    result = await _client(ctx).get_statistics()
    return json.dumps(result)


# ── Asset Info ──────────────────────────────────────────────


@mcp.tool()
async def get_asset_info(ctx, asset_id: str) -> str:
    """Get full metadata for a specific asset (EXIF, GPS, dates, camera, etc).

    Args:
        asset_id: The unique ID of the asset.
    """
    result = await _client(ctx).get_asset(asset_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def get_map_markers(
    ctx,
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
    ctx,
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
    ctx,
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
    assets = result.get("assets", {}).get("items", [])
    total = result.get("assets", {}).get("total", 0)
    return json.dumps({"total": total, "page": page, "assets": assets}, default=str)


# ── Albums ──────────────────────────────────────────────────


@mcp.tool()
async def list_albums(ctx, shared: bool | None = None) -> str:
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
async def get_album(ctx, album_id: str) -> str:
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
    ctx, name: str, description: str = "", asset_ids: list[str] | None = None
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
    ctx, album_id: str, name: str = "", description: str = ""
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
async def delete_album(ctx, album_id: str) -> str:
    """Delete an album. Photos are NOT deleted, only the album container.

    Args:
        album_id: The album's unique ID.
    """
    await _client(ctx).delete_album(album_id)
    return json.dumps({"deleted": True, "album_id": album_id})


@mcp.tool()
async def add_assets_to_album(ctx, album_id: str, asset_ids: list[str]) -> str:
    """Add photos/videos to an album.

    Args:
        album_id: Target album ID.
        asset_ids: List of asset IDs to add.
    """
    result = await _client(ctx).add_assets_to_album(album_id, asset_ids)
    return json.dumps({"album_id": album_id, "added": len(asset_ids), "result": result}, default=str)


@mcp.tool()
async def remove_assets_from_album(ctx, album_id: str, asset_ids: list[str]) -> str:
    """Remove photos/videos from an album. The photos themselves are NOT deleted.

    Args:
        album_id: Target album ID.
        asset_ids: List of asset IDs to remove.
    """
    result = await _client(ctx).remove_assets_from_album(album_id, asset_ids)
    return json.dumps({"album_id": album_id, "removed": len(asset_ids), "result": result}, default=str)


# ── Shared Links ────────────────────────────────────────────


@mcp.tool()
async def list_shared_links(ctx) -> str:
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
    ctx,
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


# ── HTTP App (for Streamable HTTP transport) ────────────────

app = mcp.streamable_http_app()
