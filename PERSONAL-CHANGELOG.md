# Personal Fork Changelog

Personal additions on top of [drolosoft/immich-photo-manager](https://github.com/drolosoft/immich-photo-manager).

Versioning: `personal-vMAJOR.MINOR.PATCH` (independent from upstream plugin version).

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
