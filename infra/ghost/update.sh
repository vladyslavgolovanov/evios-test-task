#!/usr/bin/env bash
# Run on the VPS with the private upload directory as the first argument.
set -euo pipefail
umask 077
cd /opt/ghost
exec 9>/run/ghost-bootstrap.lock
flock -w 300 9
stage=${1:?Expected an uploaded configuration directory}
cp .env "$stage/.env"
docker compose --project-directory "$stage" config --quiet
docker compose --project-directory "$stage" pull
docker compose --project-directory "$stage" run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile
install -m 600 "$stage/compose.yml" compose.yml
install -m 600 "$stage/Caddyfile" Caddyfile
docker compose up -d --wait --wait-timeout 360
# Recreate the proxy to load the newly mounted Caddyfile even if its image is unchanged.
docker compose up -d --no-deps --force-recreate caddy
docker compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile
