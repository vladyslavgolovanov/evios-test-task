#!/usr/bin/env bash
# AWS EC2 credentials/target variables and Tailscale connectivity are supplied by CI.
set -euo pipefail
cd "$(dirname "$0")"
for command in aws python3 tailscale timeout tar; do
    command -v "$command" >/dev/null || { echo "Missing command: $command" >&2; exit 1; }
done
target=$(python3 -B provision.py)
read -r name instance_id <<< "$target"
printf 'Waiting for the private tunnel; Tailscale assigns the site address automatically.\n'
for attempt in $(seq 1 60); do
    if timeout 15 tailscale ssh "root@$name" true 2>/dev/null; then
        break
    fi
    if [[ "$attempt" == 60 ]]; then
        echo 'Tunnel unavailable. Inspect AWS EC2 Console/cloud-init; VPS was not deleted.' >&2
        exit 1
    fi
    sleep 10
done
# Reject stale/conflicting Tailscale hostnames before updating any files.
# shellcheck disable=SC2016
remote_id=$(tailscale ssh "root@$name" '
    token=$(curl --max-time 10 --fail --silent --show-error -X PUT -H "X-aws-ec2-metadata-token-ttl-seconds: 60" http://169.254.169.254/latest/api/token) &&
    curl --max-time 10 --fail --silent --show-error -H "X-aws-ec2-metadata-token: $token" http://169.254.169.254/latest/meta-data/instance-id
')
[[ "$remote_id" == "$instance_id" ]] || { echo 'Tunnel points to a different EC2 instance' >&2; exit 1; }
timeout 900 tailscale ssh "root@$name" 'cloud-init status --wait'
# Execute this revision's updater from its own directory, never overwrite a running script.
# shellcheck disable=SC2016
tar -cf - compose.yml Caddyfile update.sh | tailscale ssh "root@$name" '
    set -eu
    umask 077
    stage=$(mktemp -d /opt/ghost/upload.XXXXXX)
    trap "rm -rf -- \"$stage\"" EXIT
    tar -xf - -C "$stage" compose.yml Caddyfile update.sh
    bash "$stage/update.sh" "$stage"
'
tailscale ssh "root@$name" 'cat /opt/ghost/READY'
