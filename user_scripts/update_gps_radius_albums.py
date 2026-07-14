#!/usr/bin/env python3
"""
Update landmark albums using GPS radius search.
Finds all GPS-tagged photos within a configured radius of each city center
and adds them to the corresponding album.

Complements update_location_albums.py for cities where GeoNames doesn't tag
photos reliably (small villages, suburbs, missing GPS coverage).
"""

import asyncio
import math
import os
import sys
import httpx

BASE_URL = os.environ.get("IMMICH_BASE_URL", "http://localhost:2283")
API_KEY = os.environ.get("IMMICH_API_KEY", "")

if not API_KEY:
    print("Error: IMMICH_API_KEY environment variable required")
    sys.exit(1)

HEADERS = {
    "x-api-key": API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# city label → (album_id, center_lat, center_lon, radius_km)
CITIES = {
    "🏛️ RO/Timișoara":   ("e8909a30-2bf2-48a3-bace-e2532f68fe55", 45.754284, 21.196426, 12),
    "🏛️ RO/Târgu Mureș": ("145d261e-dd2d-4ddb-99ca-321f46789d9a", 46.544438, 24.562016, 8),
    "🏛️ RO/Răstolița":   ("67aeb3ce-2f35-4c6d-9877-845c0b801f23", 46.973407, 24.973931, 10),
    "🏛️ RO/Ocna de Fier":("47471ded-640e-4f50-b26a-ca13a7a616bc", 45.341249, 21.773167, 10),
}


def bounding_box(lat: float, lon: float, radius_km: float):
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


async def get_map_markers(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(f"{BASE_URL}/api/map/markers", params={"withPartners": "false"})
    resp.raise_for_status()
    return resp.json()


async def get_album_asset_ids(client: httpx.AsyncClient, album_id: str) -> set[str]:
    buckets_resp = await client.get(f"{BASE_URL}/api/timeline/buckets",
        params={"albumId": album_id, "size": "MONTH"})
    buckets_resp.raise_for_status()
    ids: set[str] = set()
    for bucket in buckets_resp.json():
        b_resp = await client.get(f"{BASE_URL}/api/timeline/bucket", params={
            "albumId": album_id, "size": "MONTH", "timeBucket": bucket["timeBucket"]
        })
        b_resp.raise_for_status()
        ids.update(b_resp.json().get("id", []))
    return ids


async def add_assets(client: httpx.AsyncClient, album_id: str, asset_ids: list[str]) -> int:
    added = 0
    for i in range(0, len(asset_ids), 100):
        batch = asset_ids[i:i + 100]
        resp = await client.put(f"{BASE_URL}/api/albums/{album_id}/assets", json={"ids": batch})
        resp.raise_for_status()
        added += sum(1 for r in resp.json() if r.get("success"))
    return added


async def main() -> None:
    async with httpx.AsyncClient(timeout=120.0, headers=HEADERS) as client:
        print("Fetching all GPS markers...")
        markers = await get_map_markers(client)
        print(f"  {len(markers)} GPS-tagged photos\n")

        for label, (album_id, lat, lon, radius_km) in CITIES.items():
            print(f"{'─' * 50}\n{label}  (radius: {radius_km}km)")
            lat_min, lat_max, lon_min, lon_max = bounding_box(lat, lon, radius_km)

            nearby_ids = {
                m["id"] for m in markers
                if lat_min <= m["lat"] <= lat_max and lon_min <= m["lon"] <= lon_max
            }
            print(f"  GPS matches: {len(nearby_ids)}")

            current = await get_album_asset_ids(client, album_id)
            new_ids = list(nearby_ids - current)
            print(f"  current: {len(current)}  new: {len(new_ids)}")

            if new_ids:
                added = await add_assets(client, album_id, new_ids)
                print(f"  added {added} assets")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
