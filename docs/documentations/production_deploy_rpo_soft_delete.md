# Production Deployment Runbook

This guide explains how to deploy the new PostgreSQL backup setup (`RPO <= 5 minutes`) and the new soft-delete feature.

## Scope

- Feature 1: Soft delete (records are marked with `deleted_at`, not physically removed)
- Feature 2: PostgreSQL PITR backups with WAL archiving + base backups

## Repository paths used

- App code: `gog/src`
- Soft-delete migration: `gog/src/migrations/versions/1b7c2f0d9c1a_add_soft_delete_columns.py`
- Backup scripts:
  - `gog/ops/postgres/rpo5m/archive_wal.sh`
  - `gog/ops/postgres/rpo5m/base_backup.sh`
  - `gog/ops/postgres/rpo5m/verify_rpo.sh`
- PostgreSQL config snippet: `gog/ops/postgres/rpo5m/postgresql-rpo5m.conf`
- systemd units: `gog/ops/postgres/rpo5m/systemd/*`

## 1. Deploy application changes

On the production server:

```bash
cd /opt/gog
git pull
```

If you run from virtualenv:
```bash
cd /opt/gog/gog/src
source .venv/bin/activate
pip install -e ..
```

If you run with `uv`:
```bash
cd /opt/gog/gog
uv sync
```

## 2. Configure production `.env` for PostgreSQL

Edit `gog/.env` (or your deployed env file):

```env
SECRET_KEY=replace-with-long-random-secret
DB_BACKEND=postgresql
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=gog
DB_USER=gog_app
DB_PASSWORD=replace-me
```

Optional alternative:
```env
DATABASE_URL=postgresql://gog_app:replace-me@127.0.0.1:5432/gog
```

## 3. Apply database migration (soft delete columns)

Run once in production:

```bash
cd /opt/gog/gog/src
source .venv/bin/activate
flask db upgrade
```

What this adds:
- `deleted_at` columns + indexes on users/admins/teams/games/game_points/logs/conversations/messages.

## 4. Restart app service

```bash
sudo systemctl restart flaskapp
sudo systemctl status flaskapp --no-pager
```

## 5. Install backup scripts for RPO <= 5m

Copy scripts/config:

```bash
sudo mkdir -p /opt/gog/ops/postgres/rpo5m/systemd
sudo cp -r /opt/gog/gog/ops/postgres/rpo5m/* /opt/gog/ops/postgres/rpo5m/
sudo chmod +x /opt/gog/ops/postgres/rpo5m/*.sh
```

Create backup env file:

```bash
sudo mkdir -p /etc/gog
sudo cp /opt/gog/ops/postgres/rpo5m/postgres-backup.env.example /etc/gog/postgres-backup.env
sudo nano /etc/gog/postgres-backup.env
```

Recommended `/etc/gog/postgres-backup.env` values:

```env
PGHOST=127.0.0.1
PGPORT=5432
PGUSER=postgres
PGPASSWORD=replace-me
GOG_WAL_ARCHIVE_DIR=/var/backups/gog/postgres/wal
GOG_BASEBACKUP_DIR=/var/backups/gog/postgres/base
GOG_WAL_COMPRESS=1
GOG_BASEBACKUP_RETENTION_DAYS=14
GOG_RPO_SECONDS=300
```

Prepare backup directories:

```bash
sudo mkdir -p /var/backups/gog/postgres/wal
sudo mkdir -p /var/backups/gog/postgres/base
sudo chown -R postgres:postgres /var/backups/gog/postgres
```

## 6. Enable PostgreSQL WAL archiving

Install config snippet:

```bash
sudo mkdir -p /etc/postgresql/rpo5m
sudo cp /opt/gog/ops/postgres/rpo5m/postgresql-rpo5m.conf /etc/postgresql/rpo5m/postgresql-rpo5m.conf
```

Ensure your active `postgresql.conf` contains:

```conf
include_if_exists = '/etc/postgresql/rpo5m/postgresql-rpo5m.conf'
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql
sudo systemctl status postgresql --no-pager
```

## 7. Enable systemd timers (automatic backups/checks)

```bash
sudo cp /opt/gog/ops/postgres/rpo5m/systemd/gog-pg-basebackup.service /etc/systemd/system/
sudo cp /opt/gog/ops/postgres/rpo5m/systemd/gog-pg-basebackup.timer /etc/systemd/system/
sudo cp /opt/gog/ops/postgres/rpo5m/systemd/gog-pg-rpo-check.service /etc/systemd/system/
sudo cp /opt/gog/ops/postgres/rpo5m/systemd/gog-pg-rpo-check.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now gog-pg-basebackup.timer
sudo systemctl enable --now gog-pg-rpo-check.timer
```

Check timers:

```bash
systemctl list-timers --all | grep gog-pg
```

## 8. Manual checks (first deployment)

Run one base backup immediately:

```bash
sudo systemctl start gog-pg-basebackup.service
sudo systemctl status gog-pg-basebackup.service --no-pager
```

Run RPO freshness check:

```bash
sudo systemctl start gog-pg-rpo-check.service
sudo systemctl status gog-pg-rpo-check.service --no-pager
```

Expected:
- `OK: latest archived WAL age ... (<= 300s)`

## 9. Soft delete behavior after deployment

Admin deletes now mark rows with `deleted_at` instead of removing rows.

Affected entities include:
- users
- teams
- games
- logs
- game_points
- conversations/messages (when related user is soft-deleted)

By default, app queries hide soft-deleted rows.

## 10. Optional recovery of soft-deleted rows

Example SQL (manual):

```sql
UPDATE users SET deleted_at = NULL WHERE id = 123;
UPDATE teams SET deleted_at = NULL WHERE id = 'a3';
UPDATE games SET deleted_at = NULL WHERE id = 7;
```

If user conversation was deleted:

```sql
UPDATE conversations SET deleted_at = NULL WHERE user_id = 123;
UPDATE messages
SET deleted_at = NULL
WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id = 123);
```

## 11. PITR restore outline (disaster recovery)

1. Stop app writes:
```bash
sudo systemctl stop flaskapp
```

2. Stop PostgreSQL:
```bash
sudo systemctl stop postgresql
```

3. Restore latest base backup into PGDATA (or new instance), then configure recovery to replay WAL from `GOG_WAL_ARCHIVE_DIR`.

4. Start PostgreSQL and validate data.

5. Start app:
```bash
sudo systemctl start flaskapp
```

Important: test this full restore flow in staging before relying on it in production.

## 12. Minimum monitoring you should enable

- Alert on failed `gog-pg-rpo-check.service`
- Alert on failed `gog-pg-basebackup.service`
- Alert when latest file in `/var/backups/gog/postgres/wal` is older than 300 seconds
- Alert on low disk space in backup directories

## 13. Incident runbook

For accidental destructive SQL commands (for example `DELETE FROM games;`), use:

- `docs/documentations/incident_accidental_delete_recovery.md`
