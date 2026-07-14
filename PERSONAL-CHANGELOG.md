# Personal Fork Changelog

Personal additions on top of [drolosoft/immich-photo-manager](https://github.com/drolosoft/immich-photo-manager).

Versioning: `personal-vMAJOR.MINOR.PATCH` (independent from upstream plugin version).

---

## personal-v1.3.0 — 2026-07-14

### Added
- `user_scripts/update_gps_radius_albums.py` — syncs landmark albums by GPS bounding box radius; configured for Timișoara (12km), Târgu Mureș (8km), Răstolița (10km), Ocna de Fier (10km)
- `.claude/commands/photos-update-gps-radius.md` — `/photos-update-gps-radius` skill
- `user_docs/postgres-recovery.md` — step-by-step recovery procedure for lost postgres data directory

### Fixed
- All `user_scripts/` that read album asset IDs now use the timeline API (`/api/timeline/buckets` + `/api/timeline/bucket`) — Immich v3 removed the `assets` array from `GET /api/albums/{id}`

---

## personal-v1.2.0 — 2026-07-08

### Fixed
- Recovered from lost postgres data directory using daily SQL dump backup

---

## personal-v1.1.0 — 2026-06-21

### Added
- `sync-upstream.sh` — one-command script to fetch, merge, and push upstream changes

---

## personal-v1.0.0 — 2026-06-21

Based on upstream `v1.2.0`.

### Added
- `user_scripts/update_people_albums.py` — syncs 👤/👥 people albums from Immich face recognition; adds missing photos, handles `Name A & Name B` multi-person albums
- `user_scripts/update_location_albums.py` — syncs 🏛️ landmark albums from GPS city/country metadata; normalizes Romanian cedilla diacritics (GeoNames uses `ş`/`ţ` instead of proper `ș`/`ț`)
- `.claude/commands/photos-update-people.md` — `/photos-update-people` skill
- `.claude/commands/photos-update-locations.md` — `/photos-update-locations` skill
- `.claude/commands/photos-rotate.md` — `/photos-rotate` skill
