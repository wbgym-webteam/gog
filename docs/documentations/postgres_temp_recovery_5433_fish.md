# Temporary PostgreSQL Recovery Instance on Port 5433 (Fish Shell Version)

Use this when your shell is `fish` (not bash).

Live DB:
- Cluster: `16/main`
- Port: `5432`

Temporary recovery DB:
- Cluster: `16/recovery`
- Port: `5433`

## 1. Pick target recovery time

```fish
set TARGET_TIME_UTC "2026-02-26 19:42:00 UTC"
echo $TARGET_TIME_UTC
```

## 2. Find latest base backup folder

```fish
set LATEST_BACKUP_DIR (ls -1dt /var/backups/gog/postgres/base/* | head -n1)
echo $LATEST_BACKUP_DIR
ls -lah $LATEST_BACKUP_DIR
```

## 2.1 Preflight: validate backup window continuity

Before recovery:
- Ensure chosen base backup is from after archiving was fully active.
- Ensure WAL files exist for the recovery time window.

```fish
sudo ls -lah /var/backups/gog/postgres/wal | tail
```

If archiving was enabled recently, create a fresh base backup first:

```fish
sudo systemctl start gog-pg-basebackup.service
sudo systemctl status gog-pg-basebackup.service --no-pager
```

## 3. Create or recreate recovery cluster

```fish
sudo pg_dropcluster --stop 16 recovery; or true
sudo pg_createcluster 16 recovery --port 5433 --start-conf manual
```

## 4. Load base backup into recovery data directory

```fish
sudo pg_ctlcluster 16 recovery stop; or true
set RECOVERY_DATA_DIR /var/lib/postgresql/16/recovery
sudo find $RECOVERY_DATA_DIR -mindepth 1 -delete
sudo tar -xzf $LATEST_BACKUP_DIR/base.tar.gz -C $RECOVERY_DATA_DIR
if test -f $LATEST_BACKUP_DIR/pg_wal.tar.gz
    sudo tar -xzf $LATEST_BACKUP_DIR/pg_wal.tar.gz -C $RECOVERY_DATA_DIR
end
sudo chown -R postgres:postgres $RECOVERY_DATA_DIR
```

## 5. Configure PITR (compressed WAL)

```fish
sudo -u postgres touch $RECOVERY_DATA_DIR/recovery.signal
```

Append recovery settings:

```fish
printf "restore_command = 'gzip -dc /var/backups/gog/postgres/wal/%%f.gz > %%p'\nrecovery_target_time = '%s'\nrecovery_target_action = 'promote'\nrecovery_target_timeline = 'latest'\n" $TARGET_TIME_UTC | sudo tee -a $RECOVERY_DATA_DIR/postgresql.auto.conf >/dev/null
```

Verify recovery cluster port:

```fish
sudo grep -n '^port' /etc/postgresql/16/recovery/postgresql.conf
```

## 6. Start recovery cluster

```fish
sudo pg_ctlcluster 16 recovery start
sudo pg_lsclusters
```

Connectivity check:

```fish
psql -h 127.0.0.1 -p 5433 -U gog_app -d gog -c "select now();"
```

## 7. Dump only needed table from recovery cluster

Example `game_points`:

```fish
pg_dump -h 127.0.0.1 -p 5433 -U gog_app -d gog --data-only --table=game_points > ~/game_points_restore.sql
ls -lah ~/game_points_restore.sql
```

## 8. Import into live DB (5432)

```fish
psql "postgresql://gog_app:YOUR_APP_PASSWORD@localhost/gog" -f ~/game_points_restore.sql
psql "postgresql://gog_app:YOUR_APP_PASSWORD@localhost/gog" -c "select count(*) from game_points;"
```

Restart app writes:

```fish
sudo systemctl start flaskapp
```

## 9. Cleanup temporary recovery cluster

```fish
sudo pg_dropcluster --stop 16 recovery
rm -f ~/game_points_restore.sql
```

## Troubleshooting

1. `connection refused` on `5433`
- Recovery cluster not started:
```fish
sudo pg_ctlcluster 16 recovery start
```

2. Dump file is `0 bytes`
- Connection/dump failed before writing.

3. WAL not found during recovery
- Check WAL archive:
```fish
sudo ls -lah /var/backups/gog/postgres/wal
```
- Ensure restore command in `postgresql.auto.conf` uses `.gz` files.

4. `FATAL: could not locate required checkpoint record`
- WAL chain gap for selected base backup.
- Use a newer base backup and retry.
