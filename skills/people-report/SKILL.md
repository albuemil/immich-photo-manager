---
name: people-report
description: >
  Generate a report on people in your Immich photo library — unique faces detected, photos per person,
  unnamed faces, people appearing together, and face recognition quality.
  Use when the user says "people report", "faces report", "who's in my library",
  "unnamed faces", "face recognition", "how many people", "people stats",
  "who appears most", "tag my faces", "face cleanup", "person report",
  or any variation of wanting to understand the people in their photo library.
version: 1.2.0
---

# People Report

## ⚠️ Connection Required — ALWAYS CHECK FIRST

**Before doing ANYTHING else in this skill, call `ping` on the Immich MCP server.**

- If `ping` succeeds → proceed with the skill normally.
- If `ping` fails or the MCP tools are not available → **STOP. Do not continue.** Tell the user:

> ❌ **Immich is not connected.** This plugin needs a running Immich MCP server to work.
>
> Run **/setup-immich-photo-manager** to configure your Immich connection. You'll need:
> 1. Your Immich server URL (e.g., `http://192.168.1.100:2283`)
> 2. An Immich API key ([how to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key))
> 3. The MCP server configured (see **/setup-immich-photo-manager**)
>
> Nothing in this plugin will work until the connection is configured.

**Do NOT skip this check. Do NOT try to run any other tool first. Always ping, always block if it fails.**

Analyze Immich's face recognition data to generate a report on people in the library — who appears most, unnamed face clusters, co-occurrence patterns, and recognition quality.

## Prerequisites

- Immich's face detection and recognition must be enabled (Machine Learning container running)
- Face detection job should have completed at least once
- For best results, some people should already be named in Immich

## Analysis Workflow

### Step 1: Face Recognition Overview

Use the `list_people` MCP tool to get all people with pagination:

```
# Get all people (including hidden clusters)
result = list_people(page=1, size=200, with_hidden=true)
# Repeat with page=2, 3, … until result.hasNextPage is false

# Named: people where name is not empty
named = [p for p in result.people if p.name]
# Unnamed: people where name is empty
unnamed = [p for p in result.people if not p.name]

# Top named people by face count (result includes a faceCount field)
top_named = sorted(named, key=lambda p: p.faceCount, reverse=True)[:20]

# Unnamed clusters worth naming (more than 5 faces)
big_unnamed = [p for p in unnamed if p.faceCount > 5]
big_unnamed.sort(key=lambda p: p.faceCount, reverse=True)
```

### Step 2: Co-Occurrence Analysis

Find people who appear together most often using `get_asset_faces`:

```
# For a sample of assets (e.g. from search_metadata), call get_asset_faces
# to find which people appear in the same photo
co_occurrence = {}  # (person_a_id, person_b_id) → count

for asset_id in sample_asset_ids:
    faces = get_asset_faces(asset_id=asset_id)
    person_ids = [f.personId for f in faces if f.personId]
    for i, a in enumerate(person_ids):
        for b in person_ids[i+1:]:
            key = tuple(sorted([a, b]))
            co_occurrence[key] = co_occurrence.get(key, 0) + 1

# Sort and present top 15 pairs
top_pairs = sorted(co_occurrence.items(), key=lambda x: x[1], reverse=True)[:15]
```

### Step 3: Timeline Per Person

Iterate named people from `list_people` and use `get_person` for details:

```
# For each named person, get_person returns birthDate and other metadata
# Use search_metadata with personIds to find their date range
timelines = []
for person in named:
    details = get_person(person_id=person.id)
    # Use search_metadata(person_ids=[person.id], order="asc", size=1) for first appearance
    # Use search_metadata(person_ids=[person.id], order="desc", size=1) for last appearance
    first = search_metadata(person_ids=[person.id], order="asc", size=1)
    last  = search_metadata(person_ids=[person.id], order="desc", size=1)
    timelines.append({
        "name": person.name,
        "first": first.assets[0].localDateTime if first.assets else None,
        "last":  last.assets[0].localDateTime  if last.assets  else None,
        "face_count": person.faceCount,
    })
```

### Step 4: Recognition Quality

Use `list_people` with `with_hidden=True` to surface hidden clusters, and `get_person_thumbnail` to visually inspect unnamed ones:

```
# Hidden clusters — often low-confidence or suppressed by Immich
all_people = list_people(page=1, size=500, with_hidden=True)
hidden = [p for p in all_people.people if p.isHidden]

# For each unnamed cluster worth reviewing, fetch a thumbnail to show the user
for cluster in big_unnamed[:10]:
    thumb = get_person_thumbnail(person_id=cluster.id)
    # Present thumbnail so user can decide whether to name or merge
    display(thumb)

# Report recognition quality tiers based on faceCount
large_clusters  = [p for p in unnamed if p.faceCount > 50]   # almost certainly real people
medium_clusters = [p for p in unnamed if 10 < p.faceCount <= 50]
small_clusters  = [p for p in unnamed if p.faceCount <= 10]   # may be noise
```

### Step 5: Generate Report

```
PEOPLE REPORT
═══════════════════════════════════════

OVERVIEW
  Total face clusters:    287
  Named people:            42
  Unnamed clusters:       245 (85%)
  Total faces detected:  18,432

TOP PEOPLE (by photo count)
  1. María          2,341 photos (2014-2026)
  2. Juan           1,892 photos (2014-2026)
  3. Carlos           634 photos (2018-2025)
  4. Ana              412 photos (2016-2024)
  5. Pedro            287 photos (2019-2023)
  ...

UNNAMED CLUSTERS WORTH NAMING
  Cluster #45:  189 faces (appears 2019-2024) — likely a real person
  Cluster #112:  87 faces (appears 2020-2023)
  Cluster #78:   64 faces (appears 2021-2025)
  ...12 more clusters with >20 faces

  → Naming these 15 clusters would increase named coverage from 58% to 82%

CO-OCCURRENCE (people appearing together)
  María & Juan:       1,204 photos together
  María & Carlos:       287 photos together
  Juan & Pedro:         156 photos together
  ...

RECOGNITION GAPS
  Photos with faces but no person assigned: 2,341
  Very small faces (<100px): 4,521 (may have lower accuracy)

RECOMMENDATIONS
  1. Name the top 15 unnamed clusters → big coverage improvement
  2. Review 2,341 unassigned faces in Immich UI
  3. Consider merging similar unnamed clusters
  4. 4,521 small faces may produce false matches — review if face groups seem wrong
```

## Actions Available

- **Export people list** — CSV with name, photo count, date range
- **Flag unnamed clusters** — use `get_person_thumbnail` to show faces and ask user to name them
- **Co-occurrence graph** — HTML visualization showing people connections (optional)
- **Name a cluster** — use `update_person(person_id, name="...")` to name an unnamed cluster directly via MCP
- **Merge duplicates** — use `merge_people(source_person_id, target_person_id)` to combine similar unnamed clusters
- **Fix misidentified faces** — use `reassign_face(face_id, person_id)` to correct wrong assignments

## Important Notes

- **This skill can now name people, merge duplicates, and reassign faces using MCP tools — always confirm with user before modifying.**
- Co-occurrence analysis can be slow on libraries with many faces (>50K) — sample assets rather than scanning all
- Privacy consideration: face data is sensitive — reports should not be shared without consent
