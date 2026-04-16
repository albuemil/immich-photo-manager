---
name: people-report
description: >
  Generate a report on people in your Immich photo library — unique faces detected, photos per person,
  unnamed faces, people appearing together, and face recognition quality.
  Use when the user says "people report", "faces report", "who's in my library",
  "unnamed faces", "face recognition", "how many people", "people stats",
  "who appears most", "tag my faces", "face cleanup", "person report",
  or any variation of wanting to understand the people in their photo library.
version: 1.1.0
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

Query Immich's person and face data:

```sql
-- Named vs unnamed people
SELECT
  count(*) FILTER (WHERE name IS NOT NULL AND name != '') as named,
  count(*) FILTER (WHERE name IS NULL OR name = '') as unnamed,
  count(*) as total_clusters
FROM person;

-- Photos per person (top 20)
SELECT p.name, p.id, count(af."assetId") as photo_count
FROM person p
JOIN asset_faces af ON p.id = af."personId"
JOIN asset a ON af."assetId" = a.id
WHERE a."deletedAt" IS NULL
  AND p.name IS NOT NULL AND p.name != ''
GROUP BY p.id, p.name
ORDER BY photo_count DESC
LIMIT 20;

-- Unnamed clusters with most faces (likely real people worth naming)
SELECT p.id, count(af."assetId") as face_count
FROM person p
JOIN asset_faces af ON p.id = af."personId"
JOIN asset a ON af."assetId" = a.id
WHERE a."deletedAt" IS NULL
  AND (p.name IS NULL OR p.name = '')
GROUP BY p.id
HAVING count(af."assetId") > 5
ORDER BY face_count DESC
LIMIT 20;
```

### Step 2: Co-Occurrence Analysis

Find people who appear together most often:

```sql
-- People appearing in the same photo
SELECT
  p1.name as person_a,
  p2.name as person_b,
  count(DISTINCT af1."assetId") as photos_together
FROM asset_faces af1
JOIN asset_faces af2 ON af1."assetId" = af2."assetId" AND af1."personId" != af2."personId"
JOIN person p1 ON af1."personId" = p1.id
JOIN person p2 ON af2."personId" = p2.id
WHERE p1.name IS NOT NULL AND p1.name != ''
  AND p2.name IS NOT NULL AND p2.name != ''
  AND p1.name < p2.name  -- avoid duplicates
GROUP BY p1.name, p2.name
ORDER BY photos_together DESC
LIMIT 15;
```

### Step 3: Timeline Per Person

When each person appears in the library:

```sql
SELECT p.name,
  min(a."localDateTime") as first_appearance,
  max(a."localDateTime") as last_appearance,
  count(DISTINCT date_trunc('year', a."localDateTime")) as years_span
FROM person p
JOIN asset_faces af ON p.id = af."personId"
JOIN asset a ON af."assetId" = a.id
WHERE a."deletedAt" IS NULL AND p.name IS NOT NULL AND p.name != ''
GROUP BY p.name
ORDER BY count(*) DESC;
```

### Step 4: Recognition Quality

```sql
-- Face confidence distribution
SELECT
  CASE
    WHEN af."imageWidth" * af."imageHeight" > 40000 THEN 'Large (>200x200)'
    WHEN af."imageWidth" * af."imageHeight" > 10000 THEN 'Medium (100-200)'
    ELSE 'Small (<100x100)'
  END as face_size,
  count(*) as faces
FROM asset_faces af
GROUP BY 1;

-- Potential merge candidates (unnamed clusters that might be the same person)
-- This is heuristic — check if unnamed clusters have similar face embeddings
-- Best done through the Immich UI, but we can flag the biggest unnamed clusters
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
- **Flag unnamed clusters** — mark the most important ones for the user to name in Immich UI
- **Co-occurrence graph** — HTML visualization showing people connections (optional)

## Important Notes

- **Read-only** — this skill doesn't modify face assignments or person names
- Face naming must be done in the Immich UI (or API) — this skill only reports
- Person table structure may vary between Immich versions — verify column names
- Co-occurrence analysis can be slow on libraries with many faces (>50K) — use LIMIT
- Privacy consideration: face data is sensitive — reports should not be shared without consent
- The face database schema depends on Immich version — queries may need adjustment for different releases
