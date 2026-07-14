#!/usr/bin/env python3
"""
Process "Rotate Left" and "Rotate Right" queue albums in Immich.

For each album:
  1. Rotate every asset (non-destructive display transform, accumulates).
  2. Remove the assets from the queue album so it empties itself.

Usage:
    export IMMICH_BASE_URL="http://your-immich-server:2283"
    export IMMICH_API_KEY="YOUR-API-KEY-HERE"
    python3 rotate_queue_albums.py
"""

import asyncio
import os
import sys
import httpx

BASE_URL = os.environ.get("IMMICH_BASE_URL", "http://localhost:2283").rstrip("/")
API_KEY = os.environ.get("IMMICH_API_KEY", "")

if not API_KEY:
    print("Error: IMMICH_API_KEY environment variable required")
    sys.exit(1)

HEADERS = {
    "x-api-key": API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# Album name → clockwise degrees
QUEUE_ALBUMS = {
    "Rotate Right": 90,
    "Rotate Left": 270,
}


async def list_albums(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(f"{BASE_URL}/api/albums")
    resp.raise_for_status()
    return resp.json()


async def get_album_assets(client: httpx.AsyncClient, album_id: str) -> list[str]:
    buckets_resp = await client.get(f"{BASE_URL}/api/timeline/buckets", params={"albumId": album_id, "size": "MONTH"})
    buckets_resp.raise_for_status()
    ids: list[str] = []
    for bucket in buckets_resp.json():
        b_resp = await client.get(f"{BASE_URL}/api/timeline/bucket", params={
            "albumId": album_id, "size": "MONTH", "timeBucket": bucket["timeBucket"]
        })
        b_resp.raise_for_status()
        ids.extend(b_resp.json().get("id", []))
    return ids


async def get_current_rotation(client: httpx.AsyncClient, asset_id: str) -> int:
    try:
        resp = await client.get(f"{BASE_URL}/api/assets/{asset_id}/edits")
        resp.raise_for_status()
        for edit in resp.json().get("edits", []):
            if edit.get("action") == "rotate":
                return edit["parameters"].get("angle", 0)
    except Exception:
        pass
    return 0


async def apply_rotation(client: httpx.AsyncClient, asset_id: str, new_angle: int) -> None:
    if new_angle == 0:
        await client.delete(f"{BASE_URL}/api/assets/{asset_id}/edits")
    else:
        resp = await client.put(
            f"{BASE_URL}/api/assets/{asset_id}/edits",
            json={"edits": [{"action": "rotate", "parameters": {"angle": new_angle}}]},
        )
        resp.raise_for_status()


async def remove_from_album(client: httpx.AsyncClient, album_id: str, asset_ids: list[str]) -> int:
    removed = 0
    for i in range(0, len(asset_ids), 100):
        batch = asset_ids[i : i + 100]
        resp = await client.delete(
            f"{BASE_URL}/api/albums/{album_id}/assets",
            json={"ids": batch},
        )
        resp.raise_for_status()
        removed += sum(1 for r in resp.json() if r.get("success"))
    return removed


async def process_album(client: httpx.AsyncClient, album: dict, angle: int) -> None:
    album_id = album["id"]
    name = album["albumName"]
    asset_ids = await get_album_assets(client, album_id)

    if not asset_ids:
        print(f"  '{name}' is empty — nothing to do.")
        return

    print(f"  {len(asset_ids)} assets to rotate {angle}° CW")

    rotated = failed = 0
    for asset_id in asset_ids:
        try:
            current = await get_current_rotation(client, asset_id)
            new_angle = (current + angle) % 360
            await apply_rotation(client, asset_id, new_angle)
            rotated += 1
        except Exception as e:
            print(f"    WARN: {asset_id} — {e}")
            failed += 1

    print(f"  Rotated: {rotated}  Failed: {failed}")

    removed = await remove_from_album(client, album_id, asset_ids)
    print(f"  Removed from album: {removed}/{len(asset_ids)}")


async def main() -> None:
    async with httpx.AsyncClient(timeout=60.0, headers=HEADERS) as client:
        all_albums = await list_albums(client)
        album_map = {a["albumName"]: a for a in all_albums}

        lower_map = {a["albumName"].lower(): a for a in all_albums}

        for name, angle in QUEUE_ALBUMS.items():
            match = lower_map.get(name.lower())
            actual_name = match["albumName"] if match else name
            print(f"\n{'─'*50}\n{actual_name} ({angle}° CW)")
            if not match:
                print(f"  Album not found — skipping.")
                continue
            await process_album(client, match, angle)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
