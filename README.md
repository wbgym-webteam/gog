# Subdomain for _wbgym.de_

This is the repository, where the Weinberg Secondary School develops a subdomain for their website wbgym.de.

# Installation Guide

1. Clone the repository using git.
2. Install the required packages using [command].
3. Create a DB-File called `src/wbgym,.db`.
4. Run the script `main.py` to start the server.

# Deployment Guide

- Pull the latest commits from the repository.
- Make the following changes to `main.py`:
  - Set debug to False
  - Set host to '0.0.0.0'

And run the `main.py`-file!

# initialize migration repository, if it has not been initialized yet
 
  - change directory to src
  - type in the terminal
    - flask db init

  ## apply migrations

  - change directory to src
  - type in terminal
    - flask db upgrade

# Admin login accessible through

- /gog/admin/login

# PostgreSQL RPO <= 5 minutes

- See `docs/documentations/postgres_rpo_5m.md` for production setup (WAL archiving + base backups + systemd timers).
- See `docs/documentations/postgres_rpo_5m_verified_steps.md` for exact verified command order (copy/paste runbook).
- See `docs/documentations/production_deploy_rpo_soft_delete.md` for full deployment runbook (RPO backups + soft delete rollout).
- See `docs/documentations/incident_accidental_delete_recovery.md` for emergency recovery after accidental `DELETE FROM ...` in prod.
- See `docs/documentations/postgres_temp_recovery_5433.md` for exact commands to run temporary PITR recovery instance on port `5433`.
- See `docs/documentations/postgres_temp_recovery_5433_fish.md` for the same temporary recovery process in Fish shell syntax.








  # Deployment Guide:


1.	Clone the Game of Grapes repo:
•	Create new file called gog
  - mkdir gog

•	Clone the GitHub repository
  - Git Clone link/to/the/gameofgrapes/repo


2.	Create the Virtual Environment:
•	Change directory to src
  - Cd gog/gog/src

•	Create the Virtual Environment
  	Python3 -m venv .venv

•	Activate the Virtual Environment
  - Source .venv/bin/activate


3.	Install necessary Dependencies:
•	Create the service file 
  - Sudo nano /etc/systemd/system/flaskapp.service

•	Add the following configuration to the file and if necessary adapt some of the Statements:

[Unit]
Description=Game of Grapes Flask App with SocketIO
After=network.target

[Service]
User=webteam
Group=www-data
WorkingDirectory=/gog/gog/src
Environment="PATH=/gog/gog/src/.venv/bin"
ExecStart=/gog/gog/src/.venv/bin/python -m gunicorn -w 4 -k eventlet -b 0.0.0.0:8000 main:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target


4.	Start and Enable the Service:
•	Reload system and start the Flask service
	Sudo systemctl daemon-reload
	Sudo systemctl start flaskapp
	Sudo systemctl enable flaskapp

•	Check Status
•	Sudo systemctl status flaskapp


5.	Customize the Firewalls inside the Serverhosters terminal (copied from Digital ocean hosting platform)
•	Add these specific inbound firewall settings
  - Type: SSH; Protocol: TCP; Port Range: 22; Sources: All IPv4 and All IPv6
  - Type: Custom; Protocol: TCP; Port Range: 8000; Sources: All IPv4 and All IPv6

•	Add these specific outbound firewall setting:
  - Type: ICMP; Protocol: ICMP; Destinations: All IPv4 and All IPv6
  - Type: All TCP; Protocol: TCP; Port Range: All ports; Destinations: All IPv4 and All IPv6
  - Type: All UDP; Protocol: TCT; Port Range: All ports; Destinations: All IPv4 and All IPv6


6.	Test the deployment:
•	Verify that the application if running (adapt the local host to the servers ipv4)
  - Curl http://localhost:8000
