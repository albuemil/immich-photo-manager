# Personal Setup & Claude Session Reference

This file documents personal customizations, setup decisions, and findings from Claude-assisted sessions.

---

## Repository Setup

This is a **personal fork** of [drolosoft/immich-photo-manager](https://github.com/drolosoft/immich-photo-manager).

| Remote | URL | Purpose |
|--------|-----|---------|
| `origin` | `https://github.com/albuemil/immich-photo-manager` | Personal fork — push here |
| `upstream` | `https://github.com/drolosoft/immich-photo-manager` | Original repo — pull updates from here |

**Sync with upstream:**
```bash
./sync-upstream.sh
# or manually:
git fetch upstream && git merge upstream/main && git push origin main
```

**Versioning:** personal changes are tagged `personal-vX.Y.Z` (independent of upstream plugin version). See `PERSONAL-CHANGELOG.md`.

---

## WSL Environment

Credentials and shortcuts set in `~/.bashrc`:

```bash
export IMMICH_API_KEY="..."
export IMMICH_BASE_URL="http://10.198.5.100:2283"
alias cd_claude="cd /mnt/d/Work/Claude"
```

All scripts in `user_scripts/` read these env vars automatically — no hardcoding needed.

---

## Personal Scripts (`user_scripts/`)

### `update_people_albums.py`
Syncs 👤/👥 people albums from Immich face recognition.
- Matches album names (stripping prefix) to recognized people
- Supports `Name A & Name B` multi-person albums
- Adds missing photos; sets description if empty
- **Skill:** `/photos-update-people`

### `update_location_albums.py`
Syncs 🏛️ landmark albums from GPS city/country metadata.
- Parses `ISO/City` from album name (e.g. `🏛️ RO/Timișoara` → Romania / Timișoara)
- Handles multi-city albums: `🏛️ RO/City1 & City2`
- Paginates metadata search results
- **Skill:** `/photos-update-locations`

> **Romanian diacritics quirk:** Immich's geocoder (GeoNames) stores city names with legacy
> cedilla characters (`ş` U+015F, `ţ` U+0163) instead of the correct comma-below variants
> (`ș` U+0219, `ț` U+021B). The script normalizes before searching so album names can use
> proper Romanian spelling.

---

## Album Naming Convention

| Type | Format | Example |
|------|--------|---------|
| Travel | `✈️ YYYY/MM 🏳️ ISO/Location` | `✈️ 2023/04 🇪🇸 ES/Tenerife` |
| Landmark | `🏛️ ISO/Location` | `🏛️ RO/Timișoara` |
| People | `👤 Name` or `👥 Name1 & Name2` | `👤 Ina` |
| Events | `🎉 YYYY/MM Title` | `🎉 2025/10 Nuntă Simo` |
| dōTERRA | `ō YYYY/MM ISO/City Title` | `ō 2026/05 PL/Katowice Me` |
| Pets | `🐾 Name` | `🐾 Palika` |
| Home/project | `🏗️ Location/Project` | `🏗️ Amzei/Gradina` |

---

## Claude Skills (`.claude/commands/`)

| Skill | Command file | What it does |
|-------|-------------|--------------|
| `/photos-update-people` | `photos-update-people.md` | Runs `update_people_albums.py` |
| `/photos-update-locations` | `photos-update-locations.md` | Runs `update_location_albums.py` |
| `/photos-rotate` | `photos-rotate.md` | Processes rotate LEFT / rotate RIGHT albums via MCP |

---

## Session Log

### 2026-07-08
- Immich v3.0.1 upgrade failed — postgres data directory was deleted by a cleanup script
- Recovered from daily SQL dump (`immich-db-backup-20260707T020000-v3.0.1-pg14.19.sql.gz`) synced via rclone to `/root/!!!!Sync_with_jotta/Immich/backups/`
- Dump restored into `postgres` database instead of `immich`; fixed by piping pg_dump between databases
- Full recovery with <24h data loss; all 60k assets, 107 albums, 1243 people intact
- Added `user_docs/postgres-recovery.md` with exact recovery steps

### 2026-06-21
- Added `update_location_albums.py` — discovered Romanian cedilla diacritic mismatch in GeoNames
- Updated both skills to read env vars from environment (removed hardcoded credential extraction)
- Fixed WSL env vars: added `export` keyword to `IMMICH_API_KEY` / `IMMICH_BASE_URL` in `~/.bashrc`
- Added `cd_claude` alias to `~/.bashrc`
- Set up GitHub fork (`albuemil/immich-photo-manager`) with upstream remote
- Added `sync-upstream.sh` and `PERSONAL-CHANGELOG.md` with `personal-vX.Y.Z` tagging
