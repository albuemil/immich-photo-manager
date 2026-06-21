#!/usr/bin/env python3
"""
Update landmark location albums in Immich.

Albums prefixed with 🏛️ are permanent location collections.
For each album, finds all photos tagged with the matching city/country
and adds any missing ones. No new albums are created.

Album name format: 🏛️ ISO/City  (e.g. 🏛️ RO/Timișoara)
Multi-city format: 🏛️ ISO/City1 & City2
"""

import asyncio
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

LANDMARK_PREFIX = "🏛️"

ISO_TO_COUNTRY = {
    "AT": "Austria",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "CH": "Switzerland",
    "CZ": "Czech Republic",
    "DE": "Germany",
    "ES": "Spain",
    "FR": "France",
    "GB": "United Kingdom",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "IT": "Italy",
    "MD": "Moldova",
    "MK": "North Macedonia",
    "NL": "Netherlands",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "RS": "Serbia",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "TR": "Turkey",
    "UA": "Ukraine",
}


def normalize_for_search(text: str) -> str:
    """Map proper Romanian comma-below diacritics to legacy cedilla variants,
    which is what Immich's reverse geocoder stores (GeoNames uses cedilla)."""
    return text.replace("ș", "ş").replace("Ș", "Ş").replace("ț", "ţ").replace("Ț", "Ţ")


def parse_album_name(name: str) -> tuple[str, list[str]]:
    """Return (iso_code, [city, ...]) from a landmark album name."""
    body = name[len(LANDMARK_PREFIX):].strip()
    if "/" in body:
        iso, cities_str = body.split("/", 1)
        cities = [c.strip() for c in cities_str.split("&") if c.strip()]
        return iso.strip(), cities
    return body.strip(), []


async def get_album_asset_ids(client: httpx.AsyncClient, album_id: str) -> set[str]:
    resp = await client.get(f"{BASE_URL}/api/albums/{album_id}")
    resp.raise_for_status()
    return {a["id"] for a in resp.json().get("assets", [])}


async def search_by_city(client: httpx.AsyncClient, city: str, country: str) -> set[str]:
    """Return all asset IDs tagged with city+country, handling pagination."""
    ids: set[str] = set()
    page = 1
    while True:
        resp = await client.post(
            f"{BASE_URL}/api/search/metadata",
            json={"city": city, "country": country, "page": page, "size": 200},
        )
        resp.raise_for_status()
        data = resp.json()
        assets = data.get("assets", {})
        for item in assets.get("items", []):
            ids.add(item["id"])
        if not assets.get("nextPage"):
            break
        page += 1
    return ids


async def add_assets(client: httpx.AsyncClient, album_id: str, asset_ids: list[str]) -> int:
    added = 0
    for i in range(0, len(asset_ids), 100):
        batch = asset_ids[i: i + 100]
        resp = await client.put(
            f"{BASE_URL}/api/albums/{album_id}/assets", json={"ids": batch}
        )
        resp.raise_for_status()
        added += sum(1 for r in resp.json() if r.get("success"))
    return added


async def main() -> None:
    async with httpx.AsyncClient(timeout=60.0, headers=HEADERS) as client:
        resp = await client.get(f"{BASE_URL}/api/albums")
        resp.raise_for_status()
        albums = [
            a for a in resp.json()
            if a["albumName"].startswith(LANDMARK_PREFIX)
        ]
        print(f"Found {len(albums)} landmark albums\n")

        total_added = 0

        for album in albums:
            album_id = album["id"]
            album_name = album["albumName"]
            print(f"{'─' * 50}\n{album_name}")

            iso, cities = parse_album_name(album_name)
            country = ISO_TO_COUNTRY.get(iso)
            if not country:
                print(f"  unknown ISO '{iso}' — skipped")
                continue
            if not cities:
                print(f"  no city in album name — skipped")
                continue

            print(f"  country: {country}  cities: {cities}")

            current = await get_album_asset_ids(client, album_id)
            tagged: set[str] = set()

            for city in cities:
                found = await search_by_city(client, normalize_for_search(city), country)
                print(f"  {city}: {len(found)} tagged")
                tagged.update(found)

            new_ids = list(tagged - current)
            print(f"  current: {len(current)}  total tagged: {len(tagged)}  new: {len(new_ids)}")

            if new_ids:
                added = await add_assets(client, album_id, new_ids)
                print(f"  added {added} assets")
                total_added += added

    print(f"\nDone. Total added: {total_added}")


if __name__ == "__main__":
    asyncio.run(main())
