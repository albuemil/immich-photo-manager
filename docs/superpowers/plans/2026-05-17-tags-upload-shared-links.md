# Tags, Upload, Asset List & Shared Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 12 new MCP tools to immich-photo-manager (38 → 50 tools): Tags CRUD + bulk tagging, asset upload, asset list, shared link management.

**Architecture:** All tools follow the existing two-layer pattern: client methods in `immich_client.py` (HTTP calls) + MCP tool wrappers in `server.py` (parameter handling + JSON serialization). No new files, no new dependencies.

**Tech Stack:** Python 3.10+, mcp SDK, httpx, Immich REST API v2.7+

---

### Task 1: Tags — Client Methods

**Files:**
- Modify: `src/immich_mcp_server/immich_client.py` (append after Duplicates section, line 512)

- [ ] **Step 1: Add 7 tag methods to ImmichClient**

Add after the `resolve_duplicates` method at line 512:

```python
    # ── Tags ──────────────────────────────────────────────

    async def list_tags(self) -> list[dict]:
        """List all tags."""
        return await self._request("GET", "/tags")

    async def get_tag(self, tag_id: str) -> dict:
        """Get tag details."""
        return await self._request("GET", f"/tags/{tag_id}")

    async def create_tag(self, name: str, color: str | None = None) -> dict:
        """Create a new tag."""
        body: dict = {"name": name}
        if color:
            body["color"] = color
        return await self._request("POST", "/tags", json=body)

    async def update_tag(self, tag_id: str, **fields) -> dict:
        """Update a tag (name, color)."""
        return await self._request("PUT", f"/tags/{tag_id}", json=fields)

    async def delete_tag(self, tag_id: str) -> None:
        """Delete a tag."""
        await self._request("DELETE", f"/tags/{tag_id}")

    async def tag_assets(self, tag_id: str, asset_ids: list[str]) -> list[dict]:
        """Add a tag to multiple assets."""
        return await self._request(
            "PUT", f"/tags/{tag_id}/assets", json={"ids": asset_ids}
        )

    async def untag_assets(self, tag_id: str, asset_ids: list[str]) -> list[dict]:
        """Remove a tag from multiple assets."""
        return await self._request(
            "DELETE", f"/tags/{tag_id}/assets", json={"ids": asset_ids}
        )
```

- [ ] **Step 2: Verify import works**

Run: `python3 -c "from src.immich_mcp_server.immich_client import ImmichClient; print([m for m in dir(ImmichClient) if 'tag' in m])"`

Expected: `['create_tag', 'delete_tag', 'get_tag', 'list_tags', 'tag_assets', 'untag_assets', 'update_tag']`

- [ ] **Step 3: Commit**

```bash
git add src/immich_mcp_server/immich_client.py
git commit -m "feat: add tag client methods (7 methods)"
```

---

### Task 2: Tags — MCP Tools

**Files:**
- Modify: `src/immich_mcp_server/server.py` (add before the HTTP App section at line 928)

- [ ] **Step 1: Add 7 tag MCP tools**

Insert before the `# ── HTTP App` comment:

```python
# ── Tags ──────────────────────────────────────────────────


@mcp.tool()
async def list_tags(ctx: Context) -> str:
    """List all tags with their IDs, names, and colors."""
    result = await _client(ctx).list_tags()
    return json.dumps({"total": len(result), "tags": result}, default=str)


@mcp.tool()
async def get_tag(ctx: Context, tag_id: str) -> str:
    """Get details for a specific tag.

    Args:
        tag_id: The tag's unique ID.
    """
    result = await _client(ctx).get_tag(tag_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def create_tag(ctx: Context, name: str, color: str = "") -> str:
    """Create a new tag.

    Args:
        name: Tag name (e.g. 'Vacation', 'Family', 'Work').
        color: Optional hex color (e.g. '#FF5733').
    """
    result = await _client(ctx).create_tag(name, color=color or None)
    return json.dumps(result, default=str)


@mcp.tool()
async def update_tag(ctx: Context, tag_id: str, name: str = "", color: str = "") -> str:
    """Update a tag's name or color.

    Args:
        tag_id: The tag's unique ID.
        name: New name (empty = don't change).
        color: New hex color (empty = don't change).
    """
    fields: dict = {}
    if name:
        fields["name"] = name
    if color:
        fields["color"] = color
    if not fields:
        return json.dumps({"error": "No fields to update. Provide name or color."})
    result = await _client(ctx).update_tag(tag_id, **fields)
    return json.dumps(result, default=str)


@mcp.tool()
async def delete_tag(ctx: Context, tag_id: str) -> str:
    """Delete a tag. The tag is removed from all assets.

    Args:
        tag_id: The tag's unique ID.
    """
    await _client(ctx).delete_tag(tag_id)
    return json.dumps({"deleted": True, "tag_id": tag_id})


@mcp.tool()
async def tag_assets(ctx: Context, tag_id: str, asset_ids: list[str]) -> str:
    """Add a tag to multiple assets.

    Args:
        tag_id: The tag to apply.
        asset_ids: List of asset IDs to tag.
    """
    result = await _client(ctx).tag_assets(tag_id, asset_ids)
    return json.dumps({"tag_id": tag_id, "tagged": len(asset_ids), "result": result}, default=str)


@mcp.tool()
async def untag_assets(ctx: Context, tag_id: str, asset_ids: list[str]) -> str:
    """Remove a tag from multiple assets.

    Args:
        tag_id: The tag to remove.
        asset_ids: List of asset IDs to untag.
    """
    result = await _client(ctx).untag_assets(tag_id, asset_ids)
    return json.dumps({"tag_id": tag_id, "untagged": len(asset_ids), "result": result}, default=str)
```

- [ ] **Step 2: Verify tools register**

Run: `IMMICH_BASE_URL=http://fake IMMICH_API_KEY=fake python3 -c "from src.immich_mcp_server.server import mcp; tools=[t.name for t in mcp._tool_manager.list_tools()]; print(f'{len(tools)} tools'); print([t for t in tools if 'tag' in t])"`

Expected: `45 tools` and `['list_tags', 'get_tag', 'create_tag', 'update_tag', 'delete_tag', 'tag_assets', 'untag_assets']`

- [ ] **Step 3: Commit**

```bash
git add src/immich_mcp_server/server.py
git commit -m "feat: add tag MCP tools (7 tools — list, get, create, update, delete, tag/untag assets)"
```

---

### Task 3: Upload — Client Method + MCP Tool

**Files:**
- Modify: `src/immich_mcp_server/immich_client.py` (add after Tags section)
- Modify: `src/immich_mcp_server/server.py` (add after Tags tools)

- [ ] **Step 1: Add upload client method**

Add to `immich_client.py` after the Tags section:

```python
    # ── Upload ─────────────────────────────────────────────

    async def upload_asset(self, file_path: str) -> dict:
        """Upload a file to Immich."""
        import os
        from datetime import datetime, timezone

        stat = os.stat(file_path)
        filename = os.path.basename(file_path)
        created = datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc).isoformat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        url = f"{self.base_url}/api/assets"
        with open(file_path, "rb") as f:
            files = {"assetData": (filename, f, "application/octet-stream")}
            data = {
                "deviceAssetId": filename,
                "deviceId": "MCP Upload",
                "fileCreatedAt": created,
                "fileModifiedAt": modified,
                "isFavorite": "false",
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url, headers={"x-api-key": self.api_key},
                    files=files, data=data,
                )
                response.raise_for_status()
                return response.json()
```

- [ ] **Step 2: Add upload MCP tool**

Add to `server.py` after the tag tools:

```python
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

    # Validate file exists
    if not os.path.isfile(file_path):
        return json.dumps({"error": f"File not found: {file_path}"})

    # Validate extension
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return json.dumps({"error": f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}"})

    # Validate size
    size = os.path.getsize(file_path)
    if size > MAX_UPLOAD_SIZE:
        return json.dumps({"error": f"File too large: {size / 1024 / 1024:.1f}MB. Max: 25MB."})

    client = _client(ctx)
    result = await client.upload_asset(file_path)

    # Add to album if requested
    if album_id and result.get("id"):
        try:
            await client.add_assets_to_album(album_id, [result["id"]])
            result["added_to_album"] = album_id
        except Exception as e:
            result["album_error"] = str(e)

    result["uploaded_file"] = os.path.basename(file_path)
    result["size_mb"] = round(size / 1024 / 1024, 2)
    return json.dumps(result, default=str)
```

- [ ] **Step 3: Verify**

Run: `IMMICH_BASE_URL=http://fake IMMICH_API_KEY=fake python3 -c "from src.immich_mcp_server.server import mcp; tools=[t.name for t in mcp._tool_manager.list_tools()]; print(f'{len(tools)} tools'); print('upload_asset' in [t.name for t in mcp._tool_manager.list_tools()])"`

Expected: `46 tools` and `True`

- [ ] **Step 4: Commit**

```bash
git add src/immich_mcp_server/immich_client.py src/immich_mcp_server/server.py
git commit -m "feat: add upload_asset tool — 25MB limit, extension filter, optional album"
```

---

### Task 4: Asset List — Client Method + MCP Tool

**Files:**
- Modify: `src/immich_mcp_server/immich_client.py` (add to Assets section after `update_asset`)
- Modify: `src/immich_mcp_server/server.py` (add after upload tool)

- [ ] **Step 1: Add list_assets client method**

Add to `immich_client.py` after `update_asset` method (around line 145):

```python
    async def list_assets(
        self,
        is_favorite: bool | None = None,
        is_archived: bool | None = None,
        is_trashed: bool | None = None,
        asset_type: str | None = None,
        page: int = 1,
        size: int = 100,
    ) -> dict:
        """List assets with optional filters."""
        params: dict = {"page": str(page), "size": str(size)}
        if is_favorite is not None:
            params["isFavorite"] = str(is_favorite).lower()
        if is_archived is not None:
            params["isArchived"] = str(is_archived).lower()
        if is_trashed is not None:
            params["isTrashed"] = str(is_trashed).lower()
        if asset_type:
            params["type"] = asset_type
        return await self._request("GET", "/assets", params=params)
```

- [ ] **Step 2: Add list_assets MCP tool**

Add to `server.py`:

```python
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
    result = await _client(ctx).list_assets(
        is_favorite=is_favorite,
        is_archived=is_archived,
        is_trashed=is_trashed,
        asset_type=asset_type or None,
        page=page,
        size=min(size, 200),
    )
    if isinstance(result, list):
        return json.dumps({"total": len(result), "page": page, "assets": result}, default=str)
    return json.dumps(result, default=str)
```

- [ ] **Step 3: Verify**

Run: `IMMICH_BASE_URL=http://fake IMMICH_API_KEY=fake python3 -c "from src.immich_mcp_server.server import mcp; tools=[t.name for t in mcp._tool_manager.list_tools()]; print(f'{len(tools)} tools')"`

Expected: `47 tools`

- [ ] **Step 4: Commit**

```bash
git add src/immich_mcp_server/immich_client.py src/immich_mcp_server/server.py
git commit -m "feat: add list_assets tool — filter by favorites, archived, trashed, type"
```

---

### Task 5: Shared Links — Client Methods + MCP Tools

**Files:**
- Modify: `src/immich_mcp_server/immich_client.py` (expand Shared Links section, after `delete_shared_link` at line 418)
- Modify: `src/immich_mcp_server/server.py` (add after existing shared link tools)

- [ ] **Step 1: Add 2 new client methods**

Add after existing `delete_shared_link` method in `immich_client.py` (we already have `delete_shared_link` but it's not exposed as an MCP tool — and we need `get` and `update`):

```python
    async def get_shared_link(self, link_id: str) -> dict:
        """Get details of a shared link."""
        return await self._request("GET", f"/shared-links/{link_id}")

    async def update_shared_link(self, link_id: str, **fields) -> dict:
        """Update a shared link."""
        return await self._request("PATCH", f"/shared-links/{link_id}", json=fields)
```

- [ ] **Step 2: Add 3 MCP tools**

Add to `server.py` after the existing `create_shared_link` tool:

```python
@mcp.tool()
async def get_shared_link(ctx: Context, link_id: str) -> str:
    """Get full details of a shared link including permissions and assets.

    Args:
        link_id: The shared link's unique ID (from list_shared_links).
    """
    result = await _client(ctx).get_shared_link(link_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def update_shared_link(
    ctx: Context,
    link_id: str,
    allow_download: bool | None = None,
    show_metadata: bool | None = None,
    allow_upload: bool | None = None,
    description: str = "",
    expiry_at: str = "",
) -> str:
    """Update a shared link's permissions or expiry.

    Args:
        link_id: The shared link's unique ID.
        allow_download: Allow visitors to download photos.
        show_metadata: Show EXIF metadata to visitors.
        allow_upload: Allow visitors to upload photos.
        description: Link description.
        expiry_at: Expiry date (ISO 8601). Empty string to remove expiry.
    """
    fields: dict = {}
    if allow_download is not None:
        fields["allowDownload"] = allow_download
    if show_metadata is not None:
        fields["showMetadata"] = show_metadata
    if allow_upload is not None:
        fields["allowUpload"] = allow_upload
    if description:
        fields["description"] = description
    if expiry_at:
        fields["expiresAt"] = expiry_at
    if not fields:
        return json.dumps({"error": "No fields to update."})
    result = await _client(ctx).update_shared_link(link_id, **fields)
    return json.dumps(result, default=str)


@mcp.tool()
async def delete_shared_link(ctx: Context, link_id: str) -> str:
    """Delete (revoke) a shared link. The link will no longer be accessible.

    Args:
        link_id: The shared link's unique ID.
    """
    await _client(ctx).delete_shared_link(link_id)
    return json.dumps({"deleted": True, "link_id": link_id})
```

**Note:** This replaces the need for the existing `delete_shared_link` that might not be exposed as an MCP tool yet. Check if it already exists in server.py — if not, the above adds it. If it does, replace it with this version.

- [ ] **Step 3: Verify**

Run: `IMMICH_BASE_URL=http://fake IMMICH_API_KEY=fake python3 -c "from src.immich_mcp_server.server import mcp; tools=[t.name for t in mcp._tool_manager.list_tools()]; print(f'{len(tools)} tools'); print([t for t in [t.name for t in mcp._tool_manager.list_tools()] if 'shared' in t or 'link' in t])"`

Expected: `50 tools` and `['list_shared_links', 'create_shared_link', 'get_shared_link', 'update_shared_link', 'delete_shared_link']`

- [ ] **Step 4: Commit**

```bash
git add src/immich_mcp_server/immich_client.py src/immich_mcp_server/server.py
git commit -m "feat: add shared link get/update/delete tools — full CRUD"
```

---

### Task 6: Update Documentation

**Files:**
- Modify: `doc/MCP-TOOLS.md`
- Modify: `README.md`
- Modify: `doc/SKILLS.md`

- [ ] **Step 1: Update MCP-TOOLS.md**

Update the tool count from 38 to 50 in the header. Add new sections:

**Tags (7)** section after Duplicates:

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_tags` | List all tags with IDs, names, colors | No |
| `get_tag` | Get tag details | No |
| `create_tag` | Create a new tag | Yes |
| `update_tag` | Update tag name or color | Yes |
| `delete_tag` | Delete a tag (removed from all assets) | Yes |
| `tag_assets` | Add a tag to multiple assets | Yes |
| `untag_assets` | Remove a tag from multiple assets | Yes |

Add `upload_asset` and `list_assets` to Assets section (now 7 tools).
Add `get_shared_link`, `update_shared_link`, `delete_shared_link` to Sharing section (now 5 tools).

- [ ] **Step 2: Update README.md**

Update tool count from 38 to 50. Add "Tags & organization" to Highlights. Update comparison table rows.

- [ ] **Step 3: Update SKILLS.md**

Update tool count from 38 to 50.

- [ ] **Step 4: Commit**

```bash
git add doc/MCP-TOOLS.md README.md doc/SKILLS.md
git commit -m "docs: update tool count to 50, add tags/upload/shared link docs"
```

---

### Task 7: Copy Plugin Cache + Test Live

- [ ] **Step 1: Copy updated files to plugin cache**

```bash
/bin/cp src/immich_mcp_server/server.py ~/.claude/plugins/cache/immich-photo-manager-marketplace/immich-photo-manager/1.1.0/src/immich_mcp_server/server.py
/bin/cp src/immich_mcp_server/immich_client.py ~/.claude/plugins/cache/immich-photo-manager-marketplace/immich-photo-manager/1.1.0/src/immich_mcp_server/immich_client.py
```

- [ ] **Step 2: Restart MCP server**

Run `/mcp` in Claude Code to reconnect.

- [ ] **Step 3: Test tags**

```
list_tags → create_tag("Test Tag") → tag_assets(tag_id, [asset_id]) → untag_assets → delete_tag
```

- [ ] **Step 4: Test list_assets**

```
list_assets(is_favorite=true) → verify returns favorites
list_assets(asset_type="VIDEO") → verify returns videos
```

- [ ] **Step 5: Test shared links**

```
list_shared_links → get_shared_link(id) → update_shared_link(id, description="updated") → delete_shared_link(id)
```

- [ ] **Step 6: Push**

```bash
git push && git push drolosoft main
```
