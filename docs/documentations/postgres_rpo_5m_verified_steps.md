# PostgreSQL RPO <= 5m: Verified Command Order (Copy/Paste Runbook)

This is the exact command flow (in working order) to set up the backup system correctly.

Use on Ubuntu server where repo is in `~/gog`.

## 0. Preconditions

- PostgreSQL installed and running
- Repo pulled with `ops/postgres/rpo5m/*`
- You already have app DB/user (`gog`, `gog_app`) configured

## 1. Install backup scripts on server

```bash
sudo mkdir -p /usr/local/lib/gog-rpo5m/systemd
sudo cp -r ~/gog/ops/postgres/rpo5m/* /usr/local/lib/gog-rpo5m/
sudo chmod +x /usr/local/lib/gog-rpo5m/*.sh
```

## 2. Install systemd units/timers

```bash
sudo cp /usr/local/lib/gog-rpo5m/systemd/gog-pg-*.service /etc/systemd/system/
sudo cp /usr/local/lib/gog-rpo5m/systemd/gog-pg-*.timer /etc/systemd/system/
sudo sed -i "s|/opt/gog/ops/postgres/rpo5m|/usr/local/lib/gog-rpo5m|g" /etc/systemd/system/gog-pg-*.service
sudo systemctl daemon-reload
```

## 3. Create backup env file

```bash
sudo mkdir -p /etc/gog
sudo cp /usr/local/lib/gog-rpo5m/postgres-backup.env.example /etc/gog/postgres-backup.env
sudo nano /etc/gog/postgres-backup.env
```

Set:

```env
PGHOST=127.0.0.1
PGPORT=5432
PGUSER=gog_backup
PGPASSWORD=YOUR_BACKUP_USER_PASSWORD
GOG_WAL_ARCHIVE_DIR=/var/backups/gog/postgres/wal
GOG_BASEBACKUP_DIR=/var/backups/gog/postgres/base
GOG_WAL_COMPRESS=1
GOG_BASEBACKUP_RETENTION_DAYS=14
GOG_RPO_SECONDS=300
```

## 4. Ensure backup DB user exists (recommended separate user)

```bash
sudo -u postgres psql
```

Run in psql:

```sql
CREATE USER gog_backup WITH ENCRYPTED PASSWORD 'CHANGE_ME_TO_32_CHAR_PASSWORD';
ALTER ROLE gog_backup WITH REPLICATION;
GRANT CONNECT ON DATABASE gog TO gog_backup;
\q
```

If user exists already:

```sql
ALTER USER gog_backup WITH ENCRYPTED PASSWORD 'CHANGE_ME_TO_32_CHAR_PASSWORD';
ALTER ROLE gog_backup WITH REPLICATION;
```

## 5. Create backup directories + permissions

```bash
sudo mkdir -p /var/backups/gog/postgres/wal
sudo mkdir -p /var/backups/gog/postgres/base
sudo chown -R postgres:postgres /var/backups/gog/postgres
```

## 6. Install PostgreSQL RPO config file

```bash
sudo mkdir -p /etc/postgresql/rpo5m
sudo cp /usr/local/lib/gog-rpo5m/postgresql-rpo5m.conf /etc/postgresql/rpo5m/postgresql-rpo5m.conf
```

Edit the file:

```bash
sudo nano /etc/postgresql/rpo5m/postgresql-rpo5m.conf
```

Important: this line must be exactly:

```conf
archive_command = 'GOG_WAL_ARCHIVE_DIR=/var/backups/gog/postgres/wal GOG_WAL_COMPRESS=1 bash /usr/local/lib/gog-rpo5m/archive_wal.sh %p %f'
```

## 7. Include the RPO config in active PostgreSQL config

Find active config:

```bash
sudo -u postgres psql -tAc "show config_file;"
```

Append include line:

```bash
echo "include_if_exists = '/etc/postgresql/rpo5m/postgresql-rpo5m.conf'" | sudo tee -a /etc/postgresql/16/main/postgresql.conf
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

## 8. Verify PostgreSQL archiving settings are active

```bash
sudo -u postgres psql -tAc "show archive_mode;"
sudo -u postgres psql -tAc "show archive_timeout;"
sudo -u postgres psql -tAc "show archive_command;"
```

Expected:
- `archive_mode = on`
- `archive_timeout = 5min` (or `300`)
- `archive_command` points to `/usr/local/lib/gog-rpo5m/archive_wal.sh`

## 9. Run first base backup test

```bash
sudo systemctl start gog-pg-basebackup.service
sudo systemctl status gog-pg-basebackup.service --no-pager
```

Expected in logs: `pg_basebackup: base backup completed`

## 10. Force WAL archive + verify RPO check

```bash
sudo -u postgres psql -c "SELECT pg_switch_wal();"
sleep 2
sudo ls -lah /var/backups/gog/postgres/wal
sudo systemctl start gog-pg-rpo-check.service
sudo systemctl status gog-pg-rpo-check.service --no-pager
```

Expected:
- WAL files exist in `/var/backups/gog/postgres/wal`
- `verify_rpo.sh` prints: `OK: latest archived WAL age ... (<= 300s)`

## 11. Enable automation (timers)

```bash
sudo systemctl enable --now gog-pg-basebackup.timer gog-pg-rpo-check.timer
sudo systemctl status gog-pg-basebackup.timer --no-pager
sudo systemctl status gog-pg-rpo-check.timer --no-pager
```

## 12. Troubleshooting learned from real setup

1. `Unit gog-pg-... not found`
- You did not copy `.service/.timer` files to `/etc/systemd/system` or forgot `daemon-reload`.

2. `CRITICAL: archive directory does not exist`
- Missing `/var/backups/gog/postgres/wal` directory.

3. `CRITICAL: no archived WAL files found`
- Archiving not active or no WAL switch yet.
- Fix config include + restart PostgreSQL + run `SELECT pg_switch_wal();`.

4. `archive_mode=off`, `archive_command=(disabled)`
- Include line missing from active `postgresql.conf`.
- RPO config file missing at `/etc/postgresql/rpo5m/postgresql-rpo5m.conf`.

5. Wrong path in `archive_command`
- Must match actual installed script path (`/usr/local/lib/gog-rpo5m/archive_wal.sh`).

## 13. Daily health checks

```bash
sudo systemctl status gog-pg-basebackup.timer --no-pager
sudo systemctl status gog-pg-rpo-check.timer --no-pager
sudo systemctl start gog-pg-rpo-check.service
sudo systemctl status gog-pg-rpo-check.service --no-pager
```

