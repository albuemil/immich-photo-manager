#!/usr/bin/env python3
"""
Update people albums in Immich:
1. List all recognized people from face recognition
2. Match each people album by name
3. Add new photos tagged with the matched person(s)
4. Set a description on albums that lack one
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

PEOPLE_PREFIXES = ("👤", "👥")


def strip_prefix(album_name: str) -> str:
    for prefix in PEOPLE_PREFIXES:
        if album_name.startswith(prefix):
            return album_name[len(prefix):].strip()
    return album_name


async def get_all_people(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(f"{BASE_URL}/api/people", params={"withHidden": "false"})
    resp.raise_for_status()
    return resp.json().get("people", [])


async def get_album_asset_ids(client: httpx.AsyncClient, album_id: str) -> set[str]:
    resp = await client.get(f"{BASE_URL}/api/albums/{album_id}")
    resp.raise_for_status()
    return {a["id"] for a in resp.json().get("assets", [])}


async def get_person_asset_ids(client: httpx.AsyncClient, person_ids: list[str]) -> set[str]:
    all_ids: set[str] = set()
    page = 1
    while True:
        resp = await client.post(
            f"{BASE_URL}/api/search/metadata",
            json={"personIds": person_ids, "page": page, "size": 200},
        )
        resp.raise_for_status()
        data = resp.json()
        assets = data.get("assets", {})
        items = assets.get("items", [])
        for item in items:
            all_ids.add(item["id"])
        if not assets.get("nextPage"):
            break
        page += 1
    return all_ids


async def add_assets(client: httpx.AsyncClient, album_id: str, asset_ids: list[str]) -> int:
    added = 0
    for i in range(0, len(asset_ids), 100):
        batch = asset_ids[i : i + 100]
        resp = await client.put(
            f"{BASE_URL}/api/albums/{album_id}/assets", json={"ids": batch}
        )
        resp.raise_for_status()
        added += sum(1 for r in resp.json() if r.get("success"))
    return added


async def set_description(client: httpx.AsyncClient, album_id: str, desc: str) -> None:
    resp = await client.patch(
        f"{BASE_URL}/api/albums/{album_id}", json={"description": desc}
    )
    resp.raise_for_status()


async def main() -> None:
    async with httpx.AsyncClient(timeout=60.0, headers=HEADERS) as client:
        print("Fetching face-recognition people...")
        people = await get_all_people(client)
        named = {p["name"].strip(): p for p in people if p.get("name")}
        print(f"  {len(named)} named people: {list(named.keys())}\n")

        resp = await client.get(f"{BASE_URL}/api/albums")
        resp.raise_for_status()
        albums = [
            a for a in resp.json()
            if any(a["albumName"].startswith(px) for px in PEOPLE_PREFIXES)
        ]
        print(f"Found {len(albums)} people albums\n")

        for album in albums:
            album_id = album["id"]
            album_name = album["albumName"]
            display = strip_prefix(album_name)
            print(f"{'─'*50}\n{album_name}")

            # Support "Name A & Name B" style albums
            names = [n.strip() for n in display.split("&")]
            person_ids = []
            for name in names:
                if name in named:
                    person_ids.append(named[name]["id"])
                    print(f"  matched face: {name}")
                else:
                    print(f"  no face match: '{name}'")

            if not person_ids:
                print("  skipped (no match)")
                continue

            current = await get_album_asset_ids(client, album_id)
            tagged = await get_person_asset_ids(client, person_ids)
            new_ids = list(tagged - current)

            print(f"  current: {len(current)}  tagged: {len(tagged)}  new: {len(new_ids)}")

            if new_ids:
                added = await add_assets(client, album_id, new_ids)
                print(f"  added {added} assets")

            if not album.get("description"):
                desc = f"Photos featuring {display}."
                await set_description(client, album_id, desc)
                print(f"  description set: '{desc}'")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
