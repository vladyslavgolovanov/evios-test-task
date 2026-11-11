# Ghost demo on Railway

Ghost and MySQL run as two services with persistent volumes and a Railway HTTPS address. This managed demo does not demonstrate the original VPS/tunnel requirement; obtain the reviewer's agreement before substituting it for that deliverable. The [AWS/Tailscale implementation](../README.md) remains available.

Live demo: https://ghost-production-3cf8ea87.up.railway.app · [Admin login](https://ghost-production-3cf8ea87.up.railway.app/ghost/)

## Deploy

1. Sign in to [Railway](https://railway.com/login). Check the available trial credit and resource limits; a trial is not permanent free hosting. Do not upgrade a paid plan automatically.
2. Create an empty project. Add a Docker image service named **MySQL** with the image below and a volume mounted at `/var/lib/mysql`. Keep the database on private networking, without a public domain or TCP proxy.

   ```text
   mysql:8.0@sha256:7dcddc01f13bab2f15cde676d44d01f61fc9f99fe7785e86196dfc07d358ae2b
   ```

   In MySQL Variables set `MYSQL_DATABASE=ghost`, `MYSQL_USER=ghost`, and generate two different strong passwords for `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD`. Keep their values only in Railway. Wait for MySQL to start.
3. Add **Ghost** using this directory's Dockerfile. For GitHub deployment, select branch `development` and set Root Directory to `/infra/ghost/railway` and Config File Path to `/infra/ghost/railway/railway.json`. Publish reviewed code before selecting this source. Alternatively, use Railway CLI from this directory to upload only these deployment files.
4. Attach a Ghost volume at `/var/lib/ghost/content`. Set these Ghost Variables:

   ```dotenv
   PORT=2368
   NODE_ENV=production
   security__staffDeviceVerification=false
   database__client=mysql
   database__connection__host=${{MySQL.RAILWAY_PRIVATE_DOMAIN}}
   database__connection__port=3306
   database__connection__user=${{MySQL.MYSQL_USER}}
   database__connection__password=${{MySQL.MYSQL_PASSWORD}}
   database__connection__database=${{MySQL.MYSQL_DATABASE}}
   ```

5. In Ghost **Settings → Networking**, generate a domain targeting port **2368**. Set Ghost `url` to `https://` followed by that exact hostname, then deploy. No custom domain or Tailscale account is needed for this demo.
6. Immediately open `https://<hostname>/ghost/` and create the owner account before sharing the URL. The admin login is public in this variant; use a unique strong password. This demo disables email verification for new staff devices because SMTP is not configured. Configure [Ghost mail](https://docs.ghost.org/config#mail) and remove `security__staffDeviceVerification=false` before production use; password recovery and email features require working mail.

Do not configure `/` as a Railway healthcheck: Ghost may redirect HTTP requests to its canonical HTTPS URL. Verify the public HTTPS site and `/ghost/` after the deployment completes. If startup fails while MySQL initializes, wait for the database and redeploy Ghost.

## Update and verify

Redeploy the existing Ghost service after a reviewed image/configuration change. GitHub-connected services deploy from the selected branch; CLI-only uploads require another `railway up` from this directory. Keep both services and their volumes; do not recreate the project for updates. Back up the database and content before image upgrades; rolling back an image does not undo database migrations.

Acceptance: create an owner, publish a post with an uploaded image, redeploy Ghost, then verify the post/image and owner login still work. Check the database has no public endpoint. Verified on Railway on 2026-11-11: HTTPS blog/admin, owner login, anonymous Admin API denial, temporary post/image persistence after redeployment, and no public MySQL endpoints. Verification content was removed. The current demo was uploaded through CLI; GitHub autodeploy is not connected. Trial credit is finite; check Railway usage before sharing the demo for an extended period.

[Railway Docker deployment](https://railway.com/guides/docker-compose) · [Persistent volumes](https://docs.railway.com/volumes) · [Trial limits](https://docs.railway.com/pricing/free-trial)
