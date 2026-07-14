# Deployment

Kloigos is a FastAPI application distributed as a Python package with a built-in
CLI. A production deployment should run the packaged `kloigos` command, not import
the FastAPI app directly.

The examples below use systemd and Nginx. They are intended as practical guidance;
for larger deployments, also consult the
[official FastAPI deployment guide](https://fastapi.tiangolo.com/deployment/).

## 1. Install Kloigos

Install Kloigos into a virtual environment on the control-plane server.

```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx git -y

sudo mkdir -p /opt/kloigos
sudo chown "$USER":"$USER" /opt/kloigos
cd /opt/kloigos

python3 -m venv .venv
source .venv/bin/activate

pip install "kloigos @ git+https://github.com/fabiog1901/kloigos.git@main"
```

Kloigos is also published on PyPI, but while the project is moving quickly the
recommended install path is the latest committed GitHub `main` branch.

## 2. Configure Environment

Kloigos requires a PostgreSQL-compatible database URL and a stable master key.
The master key is used for encrypted application secrets and must remain the same
across restarts.

Create an environment file:

```bash
sudo install -d -m 0750 -o root -g root /etc/kloigos
sudo tee /etc/kloigos/kloigos.env >/dev/null <<'EOF'
KLOIGOS_DB_URL=postgresql://kloigos:change-me@db.example.com:5432/kloigos
KLOIGOS_MASTER_KEY=replace-with-a-32-byte-base64-key
EOF
sudo chmod 0600 /etc/kloigos/kloigos.env
```

Generate a suitable master key with:

```bash
openssl rand -base64 32
```

For a quick local trial instead of a production-style deployment, use the built-in
demo mode:

```bash
kloigos demo
```

Demo mode starts an embedded local Postgres instance, creates a master key if one
does not exist, initializes the database, and runs the application.

## 3. Initialize Database and Playbooks

Run initialization once after creating the database and whenever a package upgrade
adds new schema or playbook definitions.

```bash
set -a
. /etc/kloigos/kloigos.env
set +a

kloigos init
```

The `init` command initializes the database schema and the versioned Ansible
playbooks packaged with Kloigos. See [Playbooks](playbooks.md) for the built-in playbook list,
versioning model, and optional SSH credential hook settings.

## 4. Run Kloigos with systemd

Create a systemd service to run the packaged CLI.

**File path:** `/etc/systemd/system/kloigos.service`

```ini
[Unit]
Description=Kloigos control plane
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=kloigos
Group=kloigos
WorkingDirectory=/opt/kloigos
EnvironmentFile=/etc/kloigos/kloigos.env
ExecStart=/opt/kloigos/.venv/bin/kloigos serve --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Create the service account if needed, then enable the service:

```bash
sudo useradd --system --home /opt/kloigos --shell /usr/sbin/nologin kloigos
sudo chown -R kloigos:kloigos /opt/kloigos

sudo systemctl daemon-reload
sudo systemctl enable --now kloigos
```

Useful maintenance commands:

| Task | Command |
| --- | --- |
| View live logs | `journalctl -u kloigos -f` |
| Restart application | `sudo systemctl restart kloigos` |
| Check status | `systemctl status kloigos` |
| Upgrade package | `source /opt/kloigos/.venv/bin/activate && pip install --force-reinstall "kloigos @ git+https://github.com/fabiog1901/kloigos.git@main"` |
| Apply packaged schema/playbook updates | `set -a; . /etc/kloigos/kloigos.env; set +a; kloigos init` |

## 5. Configure Nginx

Use Nginx as a reverse proxy in front of the local Kloigos process.

**File path:** `/etc/nginx/sites-available/kloigos`

```nginx
server {
    listen 80;
    server_name your_domain_or_ip;

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/kloigos /etc/nginx/sites-enabled/kloigos
sudo nginx -t
sudo systemctl restart nginx
```

## 6. Enable HTTPS

Install Certbot and the Nginx plugin:

```bash
sudo apt install certbot python3-certbot-nginx -y
```

Request and install a certificate:

```bash
sudo certbot --nginx -d your_domain.com
```

Ensure the domain's DNS record points to the server before running Certbot.
Certbot installs a renewal timer automatically. You can test renewal with:

```bash
sudo certbot renew --dry-run
```

## Production Checklist

- Allow inbound HTTP and HTTPS traffic, for example with `sudo ufw allow 'Nginx Full'`.
- Keep `/etc/kloigos/kloigos.env` readable only by root.
- Keep `KLOIGOS_MASTER_KEY` stable; changing it can make encrypted secrets unreadable.
- Run `kloigos init` after installing or upgrading Kloigos.
- Monitor startup with `journalctl -u kloigos -f`.
