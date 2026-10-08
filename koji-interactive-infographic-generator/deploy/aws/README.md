# AWS CPU backend hosting

The API and persistent worker run on one Ubuntu EC2 instance. GPU models remain on Modal; history and private assets remain in the existing Supabase project. Docker is optional; this setup uses Python virtual environments and systemd.

AWS credits are a temporary billing balance, not permanent free hosting. Check the account's plan, credit expiry, eligible services and chosen region before launching anything. Instance, EBS, public IPv4 and traffic may all consume credits or incur charges after credits expire. A 2 GiB instance is a practical starting point; benchmark actual concurrent asset processing before increasing worker count. This repository does not create AWS resources automatically.

## One-time server setup

Use Ubuntu 24.04, SSH restricted to your IP (or the deployment runner's permitted source), and HTTPS ports 80/443. Do not expose port 8000 or PostgreSQL. Use a domain pointing to the instance and install Caddy from its official package instructions.

As the instance administrator:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip curl
sudo useradd --system --create-home --shell /bin/bash koji
sudo install -d -o koji -g koji /opt/koji/releases
sudo chown koji:koji /opt/koji
sudo install -d -m 750 -o root -g koji /etc/koji
sudo install -m 640 -o root -g koji /dev/null /etc/koji/studio.env
```

Populate `/etc/koji/studio.env` privately using the backend [environment example](../../backend/studio/.env.example). It is a systemd EnvironmentFile: use `KEY=value` entries; quote values with spaces. Do not use shell `export`. Set CORS_ORIGINS to the frontend HTTPS origin.

Install the two service files from this directory into `/etc/systemd/system/`. Use `sudo visudo -f /etc/sudoers.d/koji-deploy` to grant only:

```text
koji ALL=(root) NOPASSWD: /usr/bin/systemctl restart koji-api.service koji-worker.service
```

Configure the `koji` user's `~/.ssh/authorized_keys` with a dedicated deployment public key. Keep its private key in GitHub's `koji-production` environment secrets; verify the server SSH host fingerprint independently and save the pinned known_hosts entry. The workflow refuses unknown or changed host keys.

Copy/adapt [Caddyfile.example](Caddyfile.example) into Caddy's configuration, validate it and reload Caddy. Enable the services once the first release is installed:

```bash
sudo systemctl daemon-reload
sudo systemctl enable koji-api.service koji-worker.service
```

## Deployment

Repository variables:
- `KOJI_BACKEND_HOST=aws`
- `KOJI_EC2_HOST`: instance hostname/IP, without username
- `KOJI_STUDIO_API_URL`: API HTTPS domain
- existing Supabase and Vercel public build variables
- `KOJI_DEPLOY_ENABLED=true` only when setup is complete

GitHub environment secrets:
- `KOJI_EC2_SSH_KEY`: dedicated koji deployment private key
- `KOJI_EC2_KNOWN_HOSTS`: independently verified SSH host entry
- existing Vercel/optional Modal credentials

[deploy_ec2.py](../../ci/deploy_ec2.py) uploads only tracked component backend files at the tested commit. It installs dependencies in a release virtual environment, switches the current symlink, restarts both services and checks API readiness plus worker process liveness. A failed readiness check restores the previous release when one exists. No Supabase credentials enter the frontend or build artifact.

Before the first production start, apply the additive database migrations with `python -m studio.migrate` from the backend using the protected backend environment. Apply later migrations deliberately before deployment; CI never migrates the production database. Readiness fails until required settings and tables exist.

Check `journalctl -u koji-api -u koji-worker`, API `/ready`, job failures, disk capacity and AWS budgets. Retain the current and one known good release; manually remove older release directories only after checking which symlink is active. A domain, AWS instance and CI credentials are still required to activate this prepared configuration.
