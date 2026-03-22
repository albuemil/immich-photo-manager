"""
Immich REST API client.
Wraps the Immich API endpoints needed for photo management.
"""

import os
import httpx
from typing import Any


class ImmichClient:
    """Async HTTP client for the Immich REST API."""

    def __init__(self):
        self.base_url = os.environ.get("IMMICH_BASE_URL", "").rstrip("/")
        self.api_key = os.environ.get("IMMICH_API_KEY", "")
        if not self.base_url or not self.api_key:
            raise ValueError(
                "IMMICH_BASE_URL and IMMICH_API_KEY environment variables are required"
            )
        self._headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }

    async def _request(
        self, method: str, path: str, json: dict | None = None, params: dict | None = None
    ) -> Any:
        """Make an authenticated request to the Immich API."""
        url = f"{self.base_url}/api{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method, url, headers=self._headers, json=json, params=params
            )
            response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json()

    # ── Health ──────────────────────────────────────────────

    async def ping(self) -> dict:
        """Check server connectivity."""
        return await self._request("GET", "/server/ping")

    async def get_server_version(self) -> dict:
        """Get Immich server version."""
        return await self._request("GET", "/server/version")

    async def get_statistics(self) -> dict:
        """Get library statistics (photos, videos, storage)."""
        return await self._request("GET", "/server/statistics")

    # ── Assets ──────────────────────────────────────────────

    async def get_asset(self, asset_id: str) -> dict:
        """Get full metadata for a single asset."""
        return await self._request("GET", f"/assets/{asset_id}")

    async def get_map_markers(
        self,
        is_archived: bool = False,
        is_favorite: bool | None = None,
        file_created_after: str | None = None,
        file_created_before: str | None = None,
    ) -> list[dict]:
        """Get all GPS markers from the library (for geographic discovery)."""
        params: dict[str, Any] = {"isArchived": str(is_archived).lower()}
        if is_favorite is not None:
            params["isFavorite"] = str(is_favorite).lower()
        if file_created_after:
            params["fileCreatedAfter"] = file_created_after
        if file_created_before:
            params["fileCreatedBefore"] = file_created_before
        return await self._request("GET", "/map/markers", params=params)

    # ── Search ──────────────────────────────────────────────

    async def search_metadata(
        self,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        make: str | None = None,
        model: str | None = None,
        taken_after: str | None = None,
        taken_before: str | None = None,
        is_favorite: bool | None = None,
        is_archived: bool | None = None,
        asset_type: str | None = None,
        page: int = 1,
        size: int = 100,
    ) -> dict:
        """Search assets by EXIF metadata (location, camera, dates)."""
        body: dict[str, Any] = {"page": page, "size": size}
        if city:
            body["city"] = city
        if state:
            body["state"] = state
        if country:
            body["country"] = country
        if make:
            body["make"] = make
        if model:
            body["model"] = model
        if taken_after:
            body["takenAfter"] = taken_after
        if taken_before:
            body["takenBefore"] = taken_before
        if is_favorite is not None:
            body["isFavorite"] = is_favorite
        if is_archived is not None:
            body["isArchived"] = is_archived
        if asset_type:
            body["type"] = asset_type
        return await self._request("POST", "/search/metadata", json=body)

    async def search_smart(
        self,
        query: str,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        taken_after: str | None = None,
        taken_before: str | None = None,
        page: int = 1,
        size: int = 100,
    ) -> dict:
        """AI-powered semantic search using CLIP (e.g. 'sunset at the beach')."""
        body: dict[str, Any] = {"query": query, "page": page, "size": size}
        if city:
            body["city"] = city
        if state:
            body["state"] = state
        if country:
            body["country"] = country
        if taken_after:
            body["takenAfter"] = taken_after
        if taken_before:
            body["takenBefore"] = taken_before
        return await self._request("POST", "/search/smart", json=body)

    # ── Albums ──────────────────────────────────────────────

    async def list_albums(self, shared: bool | None = None) -> list[dict]:
        """List all albums."""
        params = {}
        if shared is not None:
            params["shared"] = str(shared).lower()
        return await self._request("GET", "/albums", params=params)

    async def get_album(self, album_id: str) -> dict:
        """Get album details including all assets."""
        return await self._request("GET", f"/albums/{album_id}")

    async def create_album(
        self, name: str, description: str = "", asset_ids: list[str] | None = None
    ) -> dict:
        """Create a new album."""
        body: dict[str, Any] = {"albumName": name, "description": description}
        if asset_ids:
            body["assetIds"] = asset_ids
        return await self._request("POST", "/albums", json=body)

    async def update_album(
        self, album_id: str, name: str | None = None, description: str | None = None
    ) -> dict:
        """Update album name or description."""
        body: dict[str, Any] = {}
        if name:
            body["albumName"] = name
        if description is not None:
            body["description"] = description
        return await self._request("PATCH", f"/albums/{album_id}", json=body)

    async def delete_album(self, album_id: str) -> None:
        """Delete an album (does NOT delete photos)."""
        await self._request("DELETE", f"/albums/{album_id}")

    async def add_assets_to_album(self, album_id: str, asset_ids: list[str]) -> list[dict]:
        """Add assets to an album."""
        return await self._request(
            "PUT", f"/albums/{album_id}/assets", json={"ids": asset_ids}
        )

    async def remove_assets_from_album(
        self, album_id: str, asset_ids: list[str]
    ) -> list[dict]:
        """Remove assets from an album."""
        return await self._request(
            "DELETE", f"/albums/{album_id}/assets", json={"ids": asset_ids}
        )

    # ── Shared Links ────────────────────────────────────────

    async def list_shared_links(self) -> list[dict]:
        """List all shared links."""
        return await self._request("GET", "/shared-links")

    async def create_shared_link(
        self,
        album_id: str,
        allow_download: bool = True,
        show_metadata: bool = True,
        allow_upload: bool = False,
        description: str = "",
    ) -> dict:
        """Create a shared link for an album (publishes to Gallery)."""
        body = {
            "type": "ALBUM",
            "albumId": album_id,
            "allowDownload": allow_download,
            "showMetadata": show_metadata,
            "allowUpload": allow_upload,
        }
        if description:
            body["description"] = description
        return await self._request("POST", "/shared-links", json=body)

    async def delete_shared_link(self, link_id: str) -> None:
        """Delete a shared link."""
        await self._request("DELETE", f"/shared-links/{link_id}")
