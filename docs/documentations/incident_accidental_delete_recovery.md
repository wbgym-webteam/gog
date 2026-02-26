# Incident Runbook: Accidental SQL Delete

Use this when someone runs a destructive SQL command in production, for example:

```sql
DELETE FROM games;
```

This runbook assumes your `RPO <= 5 minutes` backup setup is active (base backups + WAL archiving).

## Severity and goal

- Incident type: data loss (human error)
- Goal: restore deleted data with minimum downtime and minimum additional data loss

## First 5 minutes checklist

1. Stop application writes immediately:
```bash
sudo systemctl stop flaskapp
```

2. Preserve evidence:
- Record exact SQL command.
- Record who ran it and when.
- Record DB name/host.

3. Capture current time in UTC:
```bash
date -u
```

4. Do not run ad-hoc fixes directly on production yet.

## Decide recovery mode

Choose one:

- Mode A: Table-level restore (recommended first)
  - Recover deleted table(s) from a PITR recovery instance.
  - Import only required data back to production.
  - Lower downtime.

- Mode B: Full database PITR
  - Roll full DB back to pre-incident time.
  - Use when many tables are affected and partial restore is too risky.

## Inputs you must know

- `INCIDENT_TIME_UTC` (when delete happened)
- `TARGET_TIME_UTC` (a few seconds before incident)
- Production DB connection (`PROD_HOST`, `PROD_DB`, `PROD_USER`)
- Backup paths:
  - `GOG_BASEBACKUP_DIR`
  - `GOG_WAL_ARCHIVE_DIR`

Example target time:
- Incident at `2026-02-26 14:22:15 UTC`
- Set `TARGET_TIME_UTC=2026-02-26 14:22:10 UTC`

## Mode A: Table-level restore (recommended)

### A1. Create temporary recovery PostgreSQL instance

1. Stop temp instance if running:
```bash
sudo systemctl stop postgresql-recovery || true
```

2. Prepare empty recovery data dir:
```bash
sudo rm -rf /var/lib/postgresql/recovery-data
sudo mkdir -p /var/lib/postgresql/recovery-data
sudo chown -R postgres:postgres /var/lib/postgresql/recovery-data
```

3. Restore latest base backup into recovery dir (example, adapt filename):
```bash
sudo -u postgres tar -xzf /var/backups/gog/postgres/base/<LATEST_BACKUP>/base.tar.gz -C /var/lib/postgresql/recovery-data
```

4. Configure PITR in recovery `postgresql.auto.conf`:
```conf
restore_command = 'cp /var/backups/gog/postgres/wal/%f %p'
recovery_target_time = '2026-02-26 14:22:10 UTC'
recovery_target_action = 'promote'
```

5. Ensure recovery signal file exists:
```bash
sudo -u postgres touch /var/lib/postgresql/recovery-data/recovery.signal
```

6. Start recovery instance (port different from prod, e.g. `5433`).

Note:
- Instance-specific start command depends on distro/service layout.
- Use your existing PostgreSQL cluster tooling.

### A2. Validate recovered data

Connect to recovery DB and verify rows exist:
```sql
SELECT count(*) FROM games;
```

### A3. Export needed data from recovery DB

Example for `games` only:
```bash
pg_dump -h 127.0.0.1 -p 5433 -U <user> -d gog --data-only --table=games > /tmp/games_restore.sql
```

If related tables were affected too, also export:
- `game_points`
- `logs`

### A4. Import recovered data into production

1. Ensure app is still stopped.
2. Load restore script:
```bash
psql -h <PROD_HOST> -U <PROD_USER> -d <PROD_DB> -f /tmp/games_restore.sql
```

3. Sanity-check production:
```sql
SELECT count(*) FROM games;
```

4. Start app:
```bash
sudo systemctl start flaskapp
sudo systemctl status flaskapp --no-pager
```

### A5. Cleanup temp recovery

After verification:
```bash
sudo systemctl stop postgresql-recovery || true
```

## Mode B: Full database PITR

Use this when many tables were changed/deleted and partial import is unsafe.

1. Stop app:
```bash
sudo systemctl stop flaskapp
```

2. Stop production PostgreSQL:
```bash
sudo systemctl stop postgresql
```

3. Restore base backup into production PGDATA.
4. Configure:
```conf
restore_command = 'cp /var/backups/gog/postgres/wal/%f %p'
recovery_target_time = '<TARGET_TIME_UTC>'
recovery_target_action = 'promote'
```
5. Start PostgreSQL, wait for recovery complete, validate key tables.
6. Start app.

## Post-incident validation

Run at minimum:

```sql
SELECT count(*) FROM games;
SELECT count(*) FROM game_points;
SELECT count(*) FROM logs;
```

Also verify:
- Admin dashboard loads
- Rankings page loads
- No migration/version mismatch

## Important caveats

- Soft delete does **not** protect against raw SQL hard deletes (`DELETE FROM ...`) run manually.
- Soft delete only applies to application code paths that call model `soft_delete()`.
- RPO 5 minutes means you may still lose up to ~5 minutes of newest writes.

## Prevention controls (recommended)

1. Remove `DELETE` privilege from app users.
2. Create a separate restricted DB role for routine admin access.
3. Require approvals for manual production SQL.
4. Log all SQL statements for privileged roles.
5. Practice this runbook quarterly in staging.
