# Ghost on AWS

One GitHub Actions run creates an Ubuntu 24.04 EC2 instance; Docker Compose runs Ghost, MySQL and Caddy. Updates reuse the VPS and preserve database/content volumes. It uses an existing public subnet (for example, in the default VPC); no new VPC is created. The `*.ts.net` address is free; EC2, its disk and public IPv4 can incur charges.

## 1. Set up accounts

- **AWS:** select a region and copy an existing public subnet ID from **VPC → Subnets**. It must have an active route to an Internet Gateway. Choose an x86 instance type with at least 2 vCPU / 4 GB RAM (e.g. `t3.medium`) and check its price. The script creates the instance and an inbound-closed security group.
- **AWS IAM:** add an OpenID Connect identity provider with URL `https://token.actions.githubusercontent.com` and audience `sts.amazonaws.com` (reuse it if already present). Create a role named `github-ghost` using the [trust policy](aws-trust-policy.json), replacing `ACCOUNT_ID` with your AWS account ID. Add [this inline permissions policy](aws-permissions.json), replacing `ACCOUNT_ID` and `REGION`. Copy the role ARN. The trust policy targets this repository's `ghost` environment; adjust the repository name if deploying a different fork. [OIDC setup](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).
- **Tailscale:** connect your computer, enable **MagicDNS** and **HTTPS certificates**, and apply the policy below with your email. Remove conflicting allow-all rules if this is an existing tailnet. Create a one-off, non-ephemeral auth key with `tag:ghost` (pre-approved if device approval is enabled), plus an OAuth client with `auth_keys` write scope limited to `tag:ghost-ci`.

```json
{
  "groups": {"group:ghost-admins": ["you@example.com"]},
  "tagOwners": {"tag:ghost": ["group:ghost-admins"], "tag:ghost-ci": ["group:ghost-admins"]},
  "grants": [
    {"src": ["group:ghost-admins"], "dst": ["tag:ghost"], "ip": ["tcp:22", "tcp:443", "tcp:8443"]},
    {"src": ["tag:ghost-ci"], "dst": ["tag:ghost"], "ip": ["tcp:22"]}
  ],
  "ssh": [
    {"action": "check", "src": ["group:ghost-admins"], "dst": ["tag:ghost"], "users": ["root"]},
    {"action": "accept", "src": ["tag:ghost-ci"], "dst": ["tag:ghost"], "users": ["root"]}
  ],
  "nodeAttrs": [
    {"target": ["tag:ghost"], "attr": ["funnel"]}
  ]
}
```

## 2. Configure GitHub

In **Settings → Environments**, create `ghost`, allow deployments from `development`, and add:

| Secret | Value |
|---|---|
| `TS_AUTHKEY` | Tailscale VPS auth key (`tag:ghost`) |
| `TS_OAUTH_CLIENT_ID` | Tailscale CI OAuth client ID |
| `TS_OAUTH_SECRET` | Tailscale CI OAuth client secret |

| Variable | Value |
|---|---|
| `GHOST_NAME` | Unique server name, e.g. `ghost-demo` |
| `GHOST_INSTANCE_TYPE` | x86 EC2 type, e.g. `t3.medium` |
| `AWS_REGION` | Selected region, e.g. `eu-central-1` |
| `AWS_SUBNET_ID` | Existing public subnet ID in that region |
| `AWS_ROLE_ARN` | ARN of the `github-ghost` IAM role |

AWS uses temporary OIDC credentials; no AWS access-key secrets are needed. Keep Tailscale tokens in GitHub secrets. The one-off Tailscale key is sent in cloud-init user-data; use a short expiry. No domain purchase or DNS records are needed.

## 3. Deploy

1. Publish the reviewed changes to the default `development` branch.
2. Open **Actions → Ghost infrastructure → Run workflow**, select `development` and run it. This creates paid resources and prints the blog and admin URLs when ready.
3. Open the public blog. While connected to Tailscale, open `https://<hostname>.ts.net:8443/ghost/` and create the owner account.

SSH and admin access require Tailscale; public SSH is closed. Keep port 8443 private: do not enable Funnel for it. Check that public `/ghost/` returns 403 and the admin URL is inaccessible outside Tailscale.

## 4. Update

Publish changes to the image versions or Compose/Caddy configuration, then run the same workflow. The script finds the existing EC2 instance by its `managed-by=evios-ghost` tag and updates containers, retaining data. Keep the same AWS account/region, name, instance type, subnet and tags. Use one deployment per account/region; do not run the script concurrently outside GitHub Actions. `TS_AUTHKEY` is needed only on first creation. OS/bootstrap changes require separate maintenance.

Back up MySQL and content before upgrades; database migrations do not automatically roll back. Never use `docker compose down --volumes` on the deployed server.

For a local Linux launch, connect to Tailscale, authenticate AWS CLI v2 with your deployment identity, set the same region/subnet/name/type and Tailscale auth key in your environment and run `bash infra/ghost/deploy.sh` (AWS CLI v2, Python 3 and the Tailscale CLI required; the IAM role ARN and CI OAuth secrets are only needed by GitHub).

For deployment errors, connect through Tailscale and run:

```sh
tailscale ssh root@ghost-demo 'cloud-init status --long'
tailscale ssh root@ghost-demo 'cd /opt/ghost && docker compose logs --tail=100'
```

Failed deployments can leave billable resources. Check EC2 Console before retrying; the script never deletes or rebuilds a server. If Tailscale enrollment failed, inspect the EC2 system log; recovery may require offline repair of the root volume. Do not open public SSH.

Checks run automatically before deployment; live cloud deployment remains unverified. Configure [Ghost mail](https://docs.ghost.org/config#mail) before using email-dependent features. [Tailscale Funnel](https://tailscale.com/docs/features/tailscale-funnel) provides the public address and has bandwidth limits.

The EC2 instance has termination protection; its encrypted 30 GiB root disk is retained even after intentional termination. After the exercise, back up data, disable protection, terminate the instance and explicitly delete the retained EBS volume to stop its charges. No cleanup runs automatically.
