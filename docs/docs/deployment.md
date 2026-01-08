# Deployment

There are many ways you can deploy Kloigos in Production.
Below is just a general guidance.
Given that Kloigos is a FastAPI app, you should also consult the guidance
given in the [official FastAPI deployment guide](https://fastapi.tiangolo.com/deployment/).

## 1. System & Environment Setup

Prepare the server and initialize the Python environment.

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv nginx git -y

# Clone the repository
git clone https://github.com/fabiog1901/kloigos
cd kloigos

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies from requirements.txt
pip install -r requirements.txt

# Install production-specific dependencies (not in requirements.txt)
pip install gunicorn uvicorn

```

---

## 2. Systemd Service Configuration

Create a service file to manage the Kloigos process.

**File Path:** `/etc/systemd/system/kloigos.service`

```ini
[Unit]
Description=Gunicorn instance to serve Kloigos
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/kloigos
Environment="PATH=/home/ubuntu/kloigos/venv/bin"
# Runs Gunicorn with 4 workers using the Uvicorn worker class
ExecStart=/home/ubuntu/kloigos/venv/bin/gunicorn \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    main:app \
    --bind unix:app.sock

[Install]
WantedBy=multi-user.target

```

**Activation:**

```bash
sudo systemctl start kloigos
sudo systemctl enable kloigos

```

---

## 3. Nginx Configuration

Configure Nginx as a reverse proxy to route external traffic to the Unix socket.

**File Path:** `/etc/nginx/sites-available/kloigos`

```nginx
server {
    listen 80;
    server_name your_domain_or_ip;

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/ubuntu/kloigos/app.sock;
    }
}

```

**Activation:**

```bash
# Link the config and restart Nginx
sudo ln -s /etc/nginx/sites-available/kloigos /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx

```

---

## 4. Maintenance & Monitoring

| Task | Command |
| --- | --- |
| **View Live Logs** | `journalctl -u kloigos -f` |
| **Restart Application** | `sudo systemctl restart kloigos` |
| **Apply Code Changes** | `git pull && sudo systemctl restart kloigos` |
| **Check App Status** | `systemctl status kloigos` |


To finalize your production setup, you should secure your API with **HTTPS**. This is essential for modern web applications and required if you plan to handle sensitive data or authentication.

The industry standard for this is **Certbot** from Let's Encrypt, which provides free, automated SSL certificates.

---

## 🔒 Securing your Kloigos with HTTPS

### 1. Install Certbot

Install Certbot and the Nginx plugin to automate the certificate challenge and configuration.

```bash
sudo apt install certbot python3-certbot-nginx -y

```

### 2. Obtain and Install the SSL Certificate

Run the following command. Certbot will automatically read your Nginx configuration, find your `server_name`, and request a certificate for it.

```bash
sudo certbot --nginx -d your_domain.com

```

> **Note:** Ensure your domain's **A Record** is already pointing to your server's IP address before running this, otherwise the validation will fail.

During the process, Certbot will ask if you want to **redirect all HTTP traffic to HTTPS**. You should choose **Yes (Option 2)**.

---

### 3. Automated Certificate Renewal

Let's Encrypt certificates expire every 90 days. Certbot installs a timer that automatically handles renewals. You can verify it is working with a dry run:

```bash
sudo certbot renew --dry-run

```

---

## 🏗️ The Complete Production Stack (Summary)

Now that you have the full guide, here is how the data flows through your production stack:

1. **Client:** Requests `https://your_domain.com`.
2. **Nginx:** Receives the encrypted request on port 443, decrypts it using the SSL certificate.
3. **Unix Socket:** Nginx forwards the plain request to `app.sock`.
4. **Gunicorn:** Picks up the request from the socket and assigns it to an available **Uvicorn Worker**.
5. **FastAPI:** Processes the logic and returns the response back up the chain.

---

### Final Check List before Launch

* ✅ **Firewall:** Ensure your firewall allows traffic on ports 80 (HTTP) and 443 (HTTPS) using `sudo ufw allow 'Nginx Full'`.
* ✅ **Environment Variables:** If your app uses `.env` files, ensure they are present in the `WorkingDirectory`.
* ✅ **Logs:** Keep an eye on `journalctl -u kloigos -f` during the first hour of traffic to catch any hidden bugs.
