#!/usr/bin/env python3
"""
Batch GPS fix script for Immich library.
Finds photos missing GPS that have same-day neighbors with GPS,
then proposes and applies fixes via neighbor inference.
"""
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import httpx

BASE_URL = "http://10.198.5.100:2283"
API_KEY = "Kmz91MB87HCAUiALgS4QSic0QBbdQA7TJ0ONsKslVKY"
HEADERS = {"x-api-key": API_KEY, "Accept": "application/json"}
MAX_TIME_GAP_HOURS = 2  # Only infer GPS if nearest anchor is within 2h


def api_get(path: str, params: dict = None) -> any:
    url = f"{BASE_URL}/api{path}"
    r = httpx.get(url, headers=HEADERS, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def api_post(path: str, body: dict) -> any:
    url = f"{BASE_URL}/api{path}"
    r = httpx.post(url, headers=HEADERS, json=body, timeout=60)
    r.raise_for_status()
    return r.json()


def api_put(path: str, body: dict) -> any:
    url = f"{BASE_URL}/api{path}"
    r = httpx.put(url, headers=HEADERS, json=body, timeout=60)
    r.raise_for_status()
    return r.json()


def get_all_gps_markers() -> dict[str, dict]:
    """Returns {asset_id: {lat, lon, city, state, country}}"""
    print("Fetching all GPS markers...", flush=True)
    data = api_get("/map/markers", {"isArchived": "false"})
    result = {}
    for m in data:
        result[m["id"]] = {
            "lat": m["lat"], "lon": m["lon"],
            "city": m.get("city"), "state": m.get("state"), "country": m.get("country")
        }
    print(f"  Got {len(result)} GPS-tagged photos", flush=True)
    return result


def search_window(taken_after: str, taken_before: str) -> list[dict]:
    """Fetch all assets in a time window, splitting if cap (1000) is hit."""
    body = {"takenAfter": taken_after, "takenBefore": taken_before, "page": 1, "size": 1000}
    resp = api_post("/search/metadata", body)
    items = resp.get("assets", {}).get("items", [])

    if len(items) < 1000:
        return items

    # Hit the cap — split the window in half
    start = datetime.fromisoformat(taken_after.replace("Z", "+00:00"))
    end = datetime.fromisoformat(taken_before.replace("Z", "+00:00"))
    mid = start + (end - start) / 2
    mid_str = mid.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return search_window(taken_after, mid_str) + search_window(mid_str, taken_before)


def get_all_assets() -> list[dict]:
    """Fetch all assets by iterating month-by-month to avoid the 1000-result cap."""
    print("Fetching all assets (month by month)...", flush=True)
    assets = []
    seen_ids: set[str] = set()

    # Library spans roughly 2015-2026
    for year in range(2015, 2027):
        for month in range(1, 13):
            # Build ISO date boundaries
            start = f"{year:04d}-{month:02d}-01T00:00:00.000Z"
            if month == 12:
                end = f"{year+1:04d}-01-01T00:00:00.000Z"
            else:
                end = f"{year:04d}-{month+1:02d}-01T00:00:00.000Z"

            batch = search_window(start, end)
            new = [a for a in batch if a["id"] not in seen_ids]
            for a in new:
                seen_ids.add(a["id"])
            assets.extend(new)
            if new:
                print(f"  {year}-{month:02d}: {len(new)} assets", flush=True)
            time.sleep(0.02)

    print(f"  Fetched {len(assets)} assets total", flush=True)
    return assets


def parse_dt(dt_str: str) -> datetime | None:
    if not dt_str:
        return None
    # Handle ISO format with Z or +offset
    dt_str = dt_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def find_fixable(
    all_assets: list[dict],
    gps_ids: dict[str, dict],
    max_gap_hours: float = MAX_TIME_GAP_HOURS
) -> list[dict]:
    """
    Find no-GPS assets where a GPS-tagged photo exists on the same day
    within max_gap_hours. Returns list of proposed fixes.
    """
    # Group assets by calendar day (using localDateTime)
    by_day: dict[str, list[dict]] = defaultdict(list)
    for a in all_assets:
        dt_str = a.get("localDateTime", "")
        if dt_str:
            day = dt_str[:10]  # YYYY-MM-DD
            by_day[day].append(a)

    fixes = []
    days_with_mixed = 0

    for day, day_assets in sorted(by_day.items()):
        # Separate GPS vs no-GPS
        with_gps = [a for a in day_assets if a["id"] in gps_ids]
        without_gps = [a for a in day_assets if a["id"] not in gps_ids]

        if not without_gps or not with_gps:
            continue  # nothing to fix on this day

        days_with_mixed += 1

        # For each no-GPS asset, find the nearest GPS anchor by time
        for no_gps in without_gps:
            no_gps_dt = parse_dt(no_gps.get("localDateTime", ""))
            if not no_gps_dt:
                continue

            best_anchor = None
            best_gap = float("inf")
            for anchor in with_gps:
                anchor_dt = parse_dt(anchor.get("localDateTime", ""))
                if not anchor_dt:
                    continue
                # Make both timezone-aware or both naive for comparison
                if no_gps_dt.tzinfo is None and anchor_dt.tzinfo is not None:
                    anchor_dt = anchor_dt.replace(tzinfo=None)
                elif no_gps_dt.tzinfo is not None and anchor_dt.tzinfo is None:
                    no_gps_dt = no_gps_dt.replace(tzinfo=None)
                gap = abs((no_gps_dt - anchor_dt).total_seconds()) / 3600
                if gap < best_gap:
                    best_gap = gap
                    best_anchor = anchor

            if best_anchor and best_gap <= max_gap_hours:
                gps = gps_ids[best_anchor["id"]]
                fixes.append({
                    "asset_id": no_gps["id"],
                    "asset_path": no_gps.get("originalPath", ""),
                    "asset_time": no_gps.get("localDateTime", ""),
                    "anchor_id": best_anchor["id"],
                    "anchor_path": best_anchor.get("originalPath", ""),
                    "anchor_time": best_anchor.get("localDateTime", ""),
                    "gap_hours": round(best_gap, 2),
                    "lat": gps["lat"],
                    "lon": gps["lon"],
                    "city": gps.get("city"),
                    "country": gps.get("country"),
                })

    print(f"  Days with mixed GPS/no-GPS: {days_with_mixed}", flush=True)
    return fixes


def apply_fix(fix: dict) -> bool:
    try:
        body = {"latitude": fix["lat"], "longitude": fix["lon"]}
        api_put(f"/assets/{fix['asset_id']}", body)
        return True
    except Exception as e:
        print(f"    ERROR fixing {fix['asset_id']}: {e}", flush=True)
        return False


def main():
    dry_run = "--apply" not in sys.argv

    # Step 1: get all GPS markers
    gps_ids = get_all_gps_markers()

    # Step 2: get all assets
    all_assets = get_all_assets()

    # Step 3: find fixable photos
    print("Analyzing GPS gaps...", flush=True)
    fixes = find_fixable(all_assets, gps_ids)

    print(f"\n{'='*60}", flush=True)
    print(f"FIXABLE PHOTOS: {len(fixes)}", flush=True)

    if not fixes:
        print("No fixable photos found.", flush=True)
        return

    # Show summary by year
    by_year: dict[str, int] = defaultdict(int)
    for f in fixes:
        year = f["asset_time"][:4] if f["asset_time"] else "unknown"
        by_year[year] += 1

    print("\nBreakdown by year:", flush=True)
    for yr in sorted(by_year):
        print(f"  {yr}: {by_year[yr]} photos", flush=True)

    # Show sample fixes
    print("\nSample fixes (first 10):", flush=True)
    for f in fixes[:10]:
        print(f"  {f['asset_path']}", flush=True)
        print(f"    → {f['lat']:.4f}, {f['lon']:.4f} ({f['city']}, {f['country']})", flush=True)
        print(f"    anchor: {f['anchor_path']} (gap: {f['gap_hours']}h)", flush=True)

    # Save full fix log
    log_path = "/mnt/d/Work/Claude/immich-photo-manager/gps_fix_log.json"
    with open(log_path, "w") as out:
        json.dump(fixes, out, indent=2)
    print(f"\nFull fix log saved to: {log_path}", flush=True)

    if dry_run:
        print("\nDRY RUN — pass --apply to write GPS to all photos above.", flush=True)
        return

    # Apply fixes
    print(f"\nApplying {len(fixes)} GPS fixes...", flush=True)
    ok = 0
    for i, fix in enumerate(fixes, 1):
        if apply_fix(fix):
            ok += 1
        if i % 50 == 0:
            print(f"  {i}/{len(fixes)} done ({ok} ok)", flush=True)
        time.sleep(0.02)

    print(f"\nDone: {ok}/{len(fixes)} fixes applied.", flush=True)


if __name__ == "__main__":
    main()
