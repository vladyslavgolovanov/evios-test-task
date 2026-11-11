#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /opt/ghost
exec 9>/run/ghost-bootstrap.lock
flock -n 9 || { echo 'Ghost bootstrap is already running' >&2; exit 1; }
rm -f READY
# The cloud firewall is attached before boot; also disable the ordinary SSH daemon.
systemctl mask --now ssh.service ssh.socket
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y ca-certificates curl docker.io docker-compose-v2 python3
curl --fail --silent --show-error --retry 3 https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg -o /usr/share/keyrings/tailscale-archive-keyring.gpg
curl --fail --silent --show-error --retry 3 https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list -o /etc/apt/sources.list.d/tailscale.list
chmod 644 /usr/share/keyrings/tailscale-archive-keyring.gpg /etc/apt/sources.list.d/tailscale.list
apt-get update -qq
apt-get install -y tailscale
systemctl enable --now docker tailscaled
name=$(python3 -c 'import json; print(json.load(open("settings.json"))["name"])')
if [[ -f tailscale-authkey ]]; then
    tailscale up --auth-key=file:/opt/ghost/tailscale-authkey --hostname="$name" --advertise-tags=tag:ghost --ssh --accept-dns=false --timeout=120s
    rm tailscale-authkey
fi
# Credentials and settings are created once; a retry must not reset a populated MySQL volume.
if [[ ! -f .env ]]; then
    python3 - <<'PY'
import json
from pathlib import Path
import secrets
import subprocess

status = json.loads(subprocess.check_output(['tailscale', 'status', '--json']))
hostname = status['Self']['DNSName'].rstrip('.')
if not hostname.endswith('.ts.net'):
    raise SystemExit('Enable MagicDNS and HTTPS in the tailnet before deploying')
values = {'BLOG_DOMAIN': hostname, 'ADMIN_DOMAIN': f'{hostname}:8443',
          'MYSQL_PASSWORD': secrets.token_hex(32), 'MYSQL_ROOT_PASSWORD': secrets.token_hex(32)}
Path('.env.new').write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
Path('.env.new').replace('.env')
PY
fi
docker compose config --quiet
docker compose up -d --wait --wait-timeout 360
# Different external ports keep the admin UI private while publishing the blog.
timeout 120 tailscale serve --bg --https=8443 --yes http://127.0.0.1:2368
timeout 120 tailscale funnel --bg --https=443 --yes http://127.0.0.1:8080
python3 - <<'PY'
from pathlib import Path
values = dict(line.split('=', 1) for line in Path('.env').read_text().splitlines())
Path('READY').write_text(f"Blog: https://{values['BLOG_DOMAIN']}\nAdmin (tailnet): https://{values['ADMIN_DOMAIN']}/ghost/\n")
PY
cat READY
