# Immich PostgreSQL Recovery from SQL Dump

Procedure used on 2026-07-08 to recover from a lost postgres data directory.

---

## Symptoms

- `immich_postgres` container crash-looping with:
  ```
  initdb: error: directory "/var/lib/postgresql/data" exists but is not empty
  ```
- Postgres data directory exists but is missing `PG_VERSION` and config files (only skeleton dirs: `base/`, `global/`, `pg_wal/`)

## Prerequisites

- A `.sql.gz` dump file (Immich's built-in daily backup)
- The Immich version of the dump must match the running Immich version

---

## Recovery Steps

### 1. Clear the broken postgres data directory

```bash
rm -rf /mnt/user/appdata/immich/postgresql/data/*
```

### 2. Start only the postgres container

```bash
docker compose -f /root/docker-projects/immich/docker-compose.yml up -d database
sleep 10
docker compose -f /root/docker-projects/immich/docker-compose.yml ps database
```

Wait until the container is `healthy`.

### 3. Restore the SQL dump

```bash
gunzip -c "/path/to/immich-db-backup-TIMESTAMP-vX.Y.Z-pg14.19.sql.gz" | \
  docker compose -f /root/docker-projects/immich/docker-compose.yml exec -T database \
  psql -U postgres
```

> **Note:** Without `-d immich`, the dump restores into the `postgres` database by default.

### 4. Move data from `postgres` database to `immich` database

```bash
docker compose -f /root/docker-projects/immich/docker-compose.yml exec database \
  pg_dump -U postgres -d postgres | \
  docker compose -f /root/docker-projects/immich/docker-compose.yml exec -T database \
  psql -U postgres -d immich
```

### 5. Verify the restore

```bash
docker compose -f /root/docker-projects/immich/docker-compose.yml exec database \
  psql -U postgres -d immich -c "
SELECT 'assets' as table, COUNT(*) FROM asset
UNION ALL
SELECT 'albums', COUNT(*) FROM album
UNION ALL
SELECT 'people', COUNT(*) FROM person
UNION ALL
SELECT 'users', COUNT(*) FROM \"user\";
"
```

Confirm counts look correct before proceeding.

### 6. Clean up the accidentally populated `postgres` database

```bash
docker compose -f /root/docker-projects/immich/docker-compose.yml exec database \
  psql -U postgres -d postgres -c "
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
"
```

### 7. Start the full Immich stack

```bash
docker compose -f /root/docker-projects/immich/docker-compose.yml up -d
```

Open `http://10.198.5.100:2283` and verify login and albums.

---

## Backup location

Daily SQL dumps are synced via rclone to:
```
/root/!!!!Sync_with_jotta/Immich/backups/
```

Filename format: `immich-db-backup-YYYYMMDDTHHmmss-vX.Y.Z-pg14.19.sql.gz`

---

## Notes

- The actual photo/video files are stored separately from the database and are unaffected by postgres data loss
- Data lost = everything since the last backup (max ~24h with daily backups)
- Root cause this time: a cleanup script deleted `/mnt/user/appdata/immich/postgresql/data/`
