#!/usr/bin/env python3
"""
Create (or update) an Immich album from a date/time range search.

Examples:
  # Travel album — full days, exclude cities
  python3 scripts/create_date_album.py \
      --name "✈️ 🇷🇴 RO 2018 Bucharest" \
      --description "Bucharest, Romania — November 2018." \
      --after 2018-11-22 \
      --before 2018-11-25 \
      --exclude-city Arad \
      --exclude-city "Timișoara"

  # Event album — specific UTC time window
  python3 scripts/create_date_album.py \
      --name "🎉 2018 Havasi" \
      --description "Havasi concert, Bucharest — November 24, 2018." \
      --after "2018-11-24T16:00:00Z" \
      --before "2018-11-24T21:00:00Z"

  # Dry run — just count, no changes
  python3 scripts/create_date_album.py --name "..." --after ... --before ... --dry-run
"""
import argparse
import json
import sys
import urllib.request

BASE_URL = "http://10.198.5.100:2283"
API_KEY = "Kmz91MB87HCAUiALgS4QSic0QBbdQA7TJ0ONsKslVKY"
HEADERS = {
    "x-api-key": API_KEY,
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read())


def search_all(payload):
    ids = []
    page = 1
    while True:
        data = req("POST", "/api/search/metadata", {**payload, "page": page, "size": 200})
        items = data.get("assets", {}).get("items", [])
        ids.extend(i["id"] for i in items)
        if not data.get("assets", {}).get("nextPage"):
            break
        page += 1
    return ids


def find_album(name):
    for a in req("GET", "/api/albums"):
        if a["albumName"] == name:
            return a["id"]
    return None


def add_to_album(album_id, ids):
    added = 0
    for i in range(0, len(ids), 100):
        results = req("PUT", f"/api/albums/{album_id}/assets", {"ids": ids[i:i + 100]})
        added += sum(1 for r in results if r.get("success"))
    return added


def parse_after(s):
    if "T" not in s and len(s) == 10:
        return s + "T00:00:00.000Z"
    return s if s.endswith("Z") else s + "Z"


def parse_before(s):
    if "T" not in s and len(s) == 10:
        return s + "T23:59:59.000Z"
    return s if s.endswith("Z") else s + "Z"


def main():
    p = argparse.ArgumentParser(description="Create an Immich album from a date/time range.")
    p.add_argument("--name", required=True, help="Album name")
    p.add_argument("--description", default="", help="Album description")
    p.add_argument("--after", required=True, help="Start: YYYY-MM-DD or ISO datetime (UTC)")
    p.add_argument("--before", required=True, help="End:   YYYY-MM-DD or ISO datetime (UTC)")
    p.add_argument("--exclude-city", action="append", default=[], metavar="CITY",
                   help="Exclude photos tagged with this city (repeatable)")
    p.add_argument("--dry-run", action="store_true", help="Count photos only, make no changes")
    args = p.parse_args()

    after = parse_after(args.after)
    before = parse_before(args.before)

    print(f"Searching {after} → {before}")
    all_ids = search_all({"takenAfter": after, "takenBefore": before})
    print(f"  {len(all_ids)} photos in range")

    exclude = set()
    for city in args.exclude_city:
        city_ids = search_all({"city": city, "takenAfter": after, "takenBefore": before})
        exclude.update(city_ids)
        print(f"  -{len(city_ids)} from {city}")

    keep = [i for i in all_ids if i not in exclude]
    print(f"  {len(keep)} photos to add")

    if args.dry_run:
        print("\nDry run — use without --dry-run to create the album.")
        return

    if not keep:
        print("Nothing to add.")
        sys.exit(1)

    album_id = find_album(args.name)
    if album_id:
        print(f"\nUpdating existing album: {args.name}")
    else:
        result = req("POST", "/api/albums", {"albumName": args.name, "description": args.description})
        album_id = result["id"]
        print(f"\nCreated album: {args.name}")

    added = add_to_album(album_id, keep)
    print(f"Added {added}/{len(keep)} photos.")


if __name__ == "__main__":
    main()
