"""
Fix photos missing a date by inferring from filename patterns.
Common patterns: 20190630_143529, IMG-20190630-WA0001, Screenshot_20190630-143529, etc.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import httpx

BASE_URL = os.environ.get("IMMICH_BASE_URL", "http://localhost:2283")
API_KEY = os.environ.get("IMMICH_API_KEY", "")
if not API_KEY:
    print("Error: IMMICH_API_KEY environment variable required")
    sys.exit(1)
HEADERS = {"x-api-key": API_KEY, "Accept": "application/json"}

# Ordered list of filename date patterns (most specific first)
DATE_PATTERNS = [
    # 20190630_143529  or  VID_20190630_143529  or  IMG_20190630_143529
    (r"(?:^|[_\-])(\d{4})(\d{2})(\d{2})[_\-](\d{2})(\d{2})(\d{2})", "%Y%m%d%H%M%S"),
    # Screenshot_20190630-143529
    (r"(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", "%Y%m%d%H%M%S"),
    # 2019-06-30 14.35.29  or  2019-06-30_14.35.29
    (r"(\d{4})-(\d{2})-(\d{2})[ _](\d{2})\.(\d{2})\.(\d{2})", "%Y%m%d%H%M%S"),
    # IMG-20190630-WA0001  (date only)
    (r"(?:^|[_\-])(\d{4})(\d{2})(\d{2})(?:[_\-]|$)", "%Y%m%d"),
]


def api_get(path, params=None):
    r = httpx.get(f"{BASE_URL}/api{path}", headers=HEADERS, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def api_post(path, body):
    r = httpx.post(f"{BASE_URL}/api{path}", headers=HEADERS, json=body, timeout=60)
    r.raise_for_status()
    return r.json()


def api_put(path, body):
    r = httpx.put(f"{BASE_URL}/api{path}", headers=HEADERS, json=body, timeout=60)
    r.raise_for_status()
    return r.json()


def parse_date_from_filename(path: str) -> datetime | None:
    filename = path.split("/")[-1]
    name = filename.rsplit(".", 1)[0]  # strip extension

    for pattern, fmt in DATE_PATTERNS:
        m = re.search(pattern, name)
        if not m:
            continue
        groups = m.groups()
        date_str = "".join(groups)
        try:
            if len(fmt) == len("%Y%m%d"):
                dt = datetime.strptime(date_str, "%Y%m%d")
            else:
                dt = datetime.strptime(date_str, "%Y%m%d%H%M%S")
            # Sanity check: year between 2000 and 2030
            if 2000 <= dt.year <= 2030:
                return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def search_window(taken_after, taken_before):
    body = {"takenAfter": taken_after, "takenBefore": taken_before, "page": 1, "size": 1000}
    resp = api_post("/search/metadata", body)
    items = resp.get("assets", {}).get("items", [])
    if len(items) < 1000:
        return items
    start = datetime.fromisoformat(taken_after.replace("Z", "+00:00"))
    end = datetime.fromisoformat(taken_before.replace("Z", "+00:00"))
    mid = start + (end - start) / 2
    mid_str = mid.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return search_window(taken_after, mid_str) + search_window(mid_str, taken_before)


def get_all_assets():
    print("Fetching all assets (month by month)...", flush=True)
    assets = []
    seen = set()
    for year in range(2000, 2027):
        for month in range(1, 13):
            start = f"{year:04d}-{month:02d}-01T00:00:00.000Z"
            end = f"{year+1:04d}-01-01T00:00:00.000Z" if month == 12 else f"{year:04d}-{month+1:02d}-01T00:00:00.000Z"
            batch = search_window(start, end)
            new = [a for a in batch if a["id"] not in seen]
            for a in new:
                seen.add(a["id"])
            assets.extend(new)
            if new:
                print(f"  {year}-{month:02d}: {len(new)} assets", flush=True)
            time.sleep(0.02)
    print(f"  Total: {len(assets)} assets", flush=True)
    return assets


def find_undated(assets):
    """
    Find assets where localDateTime == fileCreatedAt (no EXIF date, fell back to
    import time) AND the filename contains a parseable date that differs by >1 day.
    """
    fixes = []
    for a in assets:
        local_dt = a.get("localDateTime", "")
        file_created = a.get("fileCreatedAt", "")
        # If localDateTime != fileCreatedAt, EXIF date was used — skip
        if local_dt != file_created:
            continue
        path = a.get("originalPath", "")
        dt = parse_date_from_filename(path)
        if not dt:
            continue
        # Compare parsed filename date vs localDateTime
        try:
            local = datetime.fromisoformat(local_dt.replace("Z", "+00:00"))
            gap_days = abs((dt - local).total_seconds()) / 86400
            if gap_days < 1:
                continue  # Already close enough
        except Exception:
            pass
        fixes.append({
            "asset_id": a["id"],
            "path": path,
            "current_date": local_dt,
            "inferred_date": dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        })
    return fixes


def main():
    dry_run = "--apply" not in sys.argv

    assets = get_all_assets()

    print("Scanning for photos with no EXIF date (localDateTime == fileCreatedAt)...", flush=True)
    no_exif = [a for a in assets if a.get("localDateTime") == a.get("fileCreatedAt")]
    print(f"  Photos using import date (no EXIF): {len(no_exif)}", flush=True)

    fixes = find_undated(assets)

    print(f"\n{'='*60}")
    print(f"FIXABLE: {len(fixes)} of {len(no_exif)} no-EXIF photos have parseable filenames")

    if not fixes:
        print("Nothing to fix.")
        return

    from collections import defaultdict
    by_year = defaultdict(int)
    for f in fixes:
        by_year[f["inferred_date"][:4]] += 1
    print("\nBreakdown by year:")
    for yr in sorted(by_year):
        print(f"  {yr}: {by_year[yr]}")

    print("\nSample fixes (first 10):")
    for f in fixes[:10]:
        print(f"  {f['path']}")
        print(f"    → {f['inferred_date']}")

    log_path = "/mnt/d/Work/Claude/apps-immich/date_fix_log.json"
    with open(log_path, "w") as out:
        json.dump(fixes, out, indent=2)
    print(f"\nFull log saved to: {log_path}")

    if dry_run:
        print(f"\nDRY RUN — pass --apply to write dates to Immich.")

        # Show unfixable filenames as a sample
        unfixable = [a for a in no_exif if not any(f["asset_id"] == a["id"] for f in fixes)]
        if unfixable:
            print(f"\nUnfixable ({len(unfixable)} photos, no parseable date in filename):")
            for a in unfixable[:10]:
                print(f"  {a.get('originalPath', '')}")
        return

    print(f"\nApplying {len(fixes)} date fixes...")
    ok = 0
    for i, fix in enumerate(fixes, 1):
        try:
            api_put(f"/assets/{fix['asset_id']}", {"dateTimeOriginal": fix["inferred_date"]})
            ok += 1
        except Exception as e:
            print(f"  ERROR {fix['asset_id']}: {e}")
        if i % 50 == 0:
            print(f"  {i}/{len(fixes)} done ({ok} ok)", flush=True)
        time.sleep(0.02)

    print(f"\nDone: {ok}/{len(fixes)} fixes applied.")


if __name__ == "__main__":
    main()
