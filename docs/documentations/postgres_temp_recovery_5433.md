# Temporary PostgreSQL Recovery Instance on Port 5433 (Ubuntu 24.04, PostgreSQL 16)

Use this to recover deleted data from backups without touching your live DB on `5432`.

Live DB:
- Cluster: `16/main`
- Port: `5432`

Temporary recovery DB:
- Cluster: `16/recovery`
- Port: `5433`

## 1. Pick target recovery time

Set a UTC time just before the bad SQL command:

```bash
TARGET_TIME_UTC="2026-02-26 19:02:50 UTC"
```

## 2. Find latest base backup folder

```bash
LATEST_BACKUP_DIR="$(ls -1dt /var/backups/gog/postgres/base/* | head -n1)"
echo "$LATEST_BACKUP_DIR"
ls -lah "$LATEST_BACKUP_DIR"
```

You should see files like:
- `base.tar.gz`
- `backup_manifest`
- optionally `pg_wal.tar.gz`

## 2.1 Preflight: validate backup window continuity

Before recovery, confirm:
- The chosen base backup was created after archiving was fully enabled.
- WAL files exist for the time window you want to recover.

Quick checks:

```bash
sudo ls -lah /var/backups/gog/postgres/wal | tail
```

If you recently enabled archiving, create a fresh base backup first and use that one:

```bash
sudo systemctl start gog-pg-basebackup.service
sudo systemctl status gog-pg-basebackup.service --no-pager
```

## 3. Create or recreate recovery cluster

If a previous recovery cluster exists, remove it:

```bash
sudo pg_dropcluster --stop 16 recovery || true
```

Create a fresh one on `5433`:

```bash
sudo pg_createcluster 16 recovery --port 5433 --start-conf manual
```

## 4. Stop recovery cluster and load base backup into its data directory

```bash
sudo pg_ctlcluster 16 recovery stop || true
RECOVERY_DATA_DIR="/var/lib/postgresql/16/recovery"
sudo rm -rf "${RECOVERY_DATA_DIR:?}"/*
sudo tar -xzf "$LATEST_BACKUP_DIR/base.tar.gz" -C "$RECOVERY_DATA_DIR"
if [ -f "$LATEST_BACKUP_DIR/pg_wal.tar.gz" ]; then
  sudo tar -xzf "$LATEST_BACKUP_DIR/pg_wal.tar.gz" -C "$RECOVERY_DATA_DIR"
fi
sudo chown -R postgres:postgres "$RECOVERY_DATA_DIR"
```

## 5. Configure PITR for compressed WAL archive

Create recovery signal:

```bash
sudo -u postgres touch "$RECOVERY_DATA_DIR/recovery.signal"
```

Append recovery settings:

```bash
sudo -u postgres bash -c "cat >> '$RECOVERY_DATA_DIR/postgresql.auto.conf' <<EOF
restore_command = 'gzip -dc /var/backups/gog/postgres/wal/%f.gz > %p'
recovery_target_time = '${TARGET_TIME_UTC}'
recovery_target_action = 'promote'
recovery_target_timeline = 'latest'
EOF"
```

Ensure cluster config uses port `5433` (usually already set by `pg_createcluster`):

```bash
sudo grep -n '^port' /etc/postgresql/16/recovery/postgresql.conf
```

## 6. Start recovery cluster

```bash
sudo pg_ctlcluster 16 recovery start
sudo pg_lsclusters
```

Check it responds:

```bash
psql -h 127.0.0.1 -p 5433 -U gog_app -d gog -c "select now();"
```

## 7. Dump only the affected table(s) from recovery cluster

Example for `game_points`:

```bash
pg_dump -h 127.0.0.1 -p 5433 -U gog_app -d gog --data-only --table=game_points > ~/game_points_restore.sql
ls -lah ~/game_points_restore.sql
```

## 8. Import into live production DB (5432)

```bash
psql "postgresql://gog_app:YOUR_APP_PASSWORD@localhost/gog" -f ~/game_points_restore.sql
psql "postgresql://gog_app:YOUR_APP_PASSWORD@localhost/gog" -c "select count(*) from game_points;"
```

Then restart app writes:

```bash
sudo systemctl start flaskapp
```

## 9. Cleanup temporary recovery cluster

```bash
sudo pg_dropcluster --stop 16 recovery
rm -f ~/game_points_restore.sql
```

## Troubleshooting

1. `connection refused` on `5433`
- Recovery cluster is not started: `sudo pg_ctlcluster 16 recovery start`

2. `pg_dump` output file is `0 bytes`
- Dump failed before writing (check stderr and connection first).

3. Recovery fails to find WAL files
- Confirm WAL files exist:
```bash
sudo ls -lah /var/backups/gog/postgres/wal
```
- Confirm `restore_command` uses `.gz` path:
```conf
restore_command = 'gzip -dc /var/backups/gog/postgres/wal/%f.gz > %p'
```

5. `FATAL: could not locate required checkpoint record`
- Selected base backup is too old for available WAL files.
- Use a newer base backup with continuous WAL coverage to `TARGET_TIME_UTC`.

4. Permission issues
- Ensure recovery data dir ownership is `postgres:postgres`.
