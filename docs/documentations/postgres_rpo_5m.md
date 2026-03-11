# PostgreSQL Production Setup for RPO <= 5 Minutes

This setup gives you point-in-time recovery with a worst-case data loss target of 5 minutes.

## What this implements

- Continuous WAL archiving
- Forced WAL switch every 5 minutes (`archive_timeout = 300`)
- Daily base backups
- 5-minute freshness checks for archived WAL

## Files added

- `ops/postgres/rpo5m/postgresql-rpo5m.conf`
- `ops/postgres/rpo5m/archive_wal.sh`
- `ops/postgres/rpo5m/base_backup.sh`
- `ops/postgres/rpo5m/verify_rpo.sh`
- `ops/postgres/rpo5m/postgres-backup.env.example`
- `ops/postgres/rpo5m/systemd/*.service`
- `ops/postgres/rpo5m/systemd/*.timer`

## Server install steps (Linux)

1. Copy files to server:
```bash
sudo mkdir -p /opt/gog/ops/postgres/rpo5m/systemd
sudo cp -r ops/postgres/rpo5m/* /opt/gog/ops/postgres/rpo5m/
sudo chmod +x /opt/gog/ops/postgres/rpo5m/*.sh
```

2. Configure backup env:
```bash
sudo mkdir -p /etc/gog
sudo cp /opt/gog/ops/postgres/rpo5m/postgres-backup.env.example /etc/gog/postgres-backup.env
sudo nano /etc/gog/postgres-backup.env
```

3. Prepare backup directories:
```bash
sudo mkdir -p /var/backups/gog/postgres/wal
sudo mkdir -p /var/backups/gog/postgres/base
sudo chown -R postgres:postgres /var/backups/gog/postgres
```

4. Enable PostgreSQL PITR config:
```bash
sudo mkdir -p /etc/postgresql/rpo5m
sudo cp /opt/gog/ops/postgres/rpo5m/postgresql-rpo5m.conf /etc/postgresql/rpo5m/postgresql-rpo5m.conf
```

Add this line into your active `postgresql.conf`:
```conf
include_if_exists = '/etc/postgresql/rpo5m/postgresql-rpo5m.conf'
```

Reload PostgreSQL:
```bash
sudo systemctl restart postgresql
```

5. Install timers:
```bash
sudo cp /opt/gog/ops/postgres/rpo5m/systemd/gog-pg-basebackup.service /etc/systemd/system/
sudo cp /opt/gog/ops/postgres/rpo5m/systemd/gog-pg-basebackup.timer /etc/systemd/system/
sudo cp /opt/gog/ops/postgres/rpo5m/systemd/gog-pg-rpo-check.service /etc/systemd/system/
sudo cp /opt/gog/ops/postgres/rpo5m/systemd/gog-pg-rpo-check.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now gog-pg-basebackup.timer
sudo systemctl enable --now gog-pg-rpo-check.timer
```

## Verify

Manual RPO check:
```bash
sudo systemctl start gog-pg-rpo-check.service
sudo systemctl status gog-pg-rpo-check.service --no-pager
```

Expected output should include:
- `OK: latest archived WAL age ... (<= 300s)`

## Notes

- This is the backup/recovery side of RPO.  
  For high availability (fast failover), you still need a standby/replica setup.
- Ensure backup storage is on a different disk/server than the primary database.
- Test restores regularly in staging.
