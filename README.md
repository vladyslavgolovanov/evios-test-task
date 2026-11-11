# Full Stack FastAPI Template

[![Test Docker Compose](../../actions/workflows/test-docker-compose.yml/badge.svg)](../../actions/workflows/test-docker-compose.yml)
[![Test Backend](../../actions/workflows/test-backend.yml/badge.svg)](../../actions/workflows/test-backend.yml)

## Evios exercise: role-aware access

### Run locally

Requires Docker with Compose v2. Run from the repository root. Keep the template `.env` unchanged; create a private configuration and replace `SECRET_KEY`, `POSTGRES_PASSWORD` and `FIRST_SUPERUSER_PASSWORD` with your own random values (for example, `openssl rand -hex 32`). Keep `FIRST_SUPERUSER=admin@example.com` for the examples below. Leave SMTP empty if you do not need local email delivery.

```sh
cp .env .env.local
# Edit .env.local before continuing. It is excluded from Git and Docker builds.
dc() { docker compose --env-file .env.local -p evios-exercise -f compose.yml "$@"; }
dc build backend
dc up -d --wait db
dc run --rm backend bash scripts/prestart.sh

# Enter an 8–128 character password for the two demo accounts:
read -r -s DEMO_USER_PASSWORD
export DEMO_USER_PASSWORD
dc run --rm -e DEMO_USER_PASSWORD backend python -m app.seed_demo

dc run --rm -p 127.0.0.1:8092:8000 -e FRONTEND_HOST=http://localhost:8092 backend fastapi run --host 0.0.0.0 --workers 1
```

Open **http://localhost:8092**. Admin uses `FIRST_SUPERUSER_PASSWORD`; `manager@example.com` and `member@example.com` use the supplied demo password. Seeding again preserves existing passwords and roles; a conflicting account fails instead of being promoted. Stop with Ctrl+C, then `dc down`; the named database volume is retained. The commands select the base Compose file explicitly, exposing only the application's loopback port and leaving proxy/admin tools unstarted.

`prestart.sh` applies Alembic migrations and seeds the administrator. For subsequent schema upgrades, back up your database first, then run `dc run --rm backend alembic upgrade head`. The role migration maps former superusers to `admin` and other users to `member`, preserving IDs, password hashes and item ownership. Downgrading returns to the old boolean model, where manager and member both become ordinary users.

### Permissions and approach

| Action | admin | manager | member |
|---|---|---|---|
| List users | Yes | Yes | No |
| Create, edit or delete other users | Yes | No | No |
| View metrics | Yes | Yes | No |
| Read/update own profile | Yes | Yes | Yes |
| Basic item features | All items | Own items | Own items |

`User.role` is the single persisted authority, constrained to `admin`, `manager` or `member`. The former `is_superuser` response field is computed from the role for compatibility with existing item/settings behavior; it is not an independently writable flag. Signup and own-profile inputs exclude privilege fields. Only administrator user-management operations accept a role.

FastAPI's `require_roles` dependency protects role-specific endpoints. Each authenticated request reads the current user from the database, so changing a role takes effect for existing tokens. Invalid authentication returns 401; insufficient permissions return 403. `GET /api/v1/metrics/` returns global user/item counts without personal data. No new global-settings feature is introduced.

The frontend learns the role from `/users/me`, uses a small permission map to show navigation/actions, and renders `Access Denied` for direct unauthorized navigation. Server checks remain authoritative. A 403 does not log the user out. Existing loading/error components and the generated OpenAPI client are reused.

### Verification

Backend tests delete their fixture records: use this **separate test project**, never the working database. The migration test additionally creates/removes a uniquely named database and verifies retained users, passwords and items.

```sh
dct() { docker compose --env-file .env.local -p evios-exercise-tests -f compose.yml "$@"; }
dct up -d --wait db
dct run --rm backend bash scripts/prestart.sh
dct run --rm -v "$PWD/backend/tests:/app/backend/tests:ro" backend bash scripts/test.sh
dct down --volumes
```

For frontend development/checks, use Bun 1.3.12 and the existing lockfile: `bun install --frozen-lockfile --ignore-scripts`, then `cd frontend` and run `bunx tsc --noEmit`, `bunx biome check ./`, and `VITE_API_URL= bun run build`. Existing Playwright commands and Mailpit setup are described in [frontend/README.md](frontend/README.md). The added browser tests cover metrics navigation and direct access for all roles; backend tests cover permissions, attempted escalation, role changes, seeding and migration preservation.

### Scope and retained template behavior

The upstream development-only `/api/v1/private/users/` endpoint is intentionally retained. When `FASTAPI_ENV=development`, it can create ordinary users without authentication; never enable that mode on a public deployment. It is absent from the base-Compose launch above. Existing dependencies and CI workflows are retained; this work is not a full security audit of the template. The overall preparation/debugging time exceeded the suggested one-hour timebox. The separate Ghost/Hetzner task and redacted AI conversation delivery are still pending.

## Technology Stack and Features

- ⚡ [**FastAPI**](https://fastapi.tiangolo.com) for the Python backend API.
  - 🧰 [SQLModel](https://sqlmodel.tiangolo.com) for the Python SQL database interactions (ORM).
  - 🔍 [Pydantic](https://docs.pydantic.dev), used by FastAPI, for the data validation and settings management.
  - 💾 [PostgreSQL](https://www.postgresql.org) as the SQL database.
- 🚀 [React](https://react.dev) for the frontend.
  - 🧩 Built into the backend application and served by FastAPI on the same domain as the API.
  - 💃 Using TypeScript, hooks, [Vite](https://vitejs.dev), and other parts of a modern frontend stack.
  - 🎨 [Tailwind CSS](https://tailwindcss.com) and [shadcn/ui](https://ui.shadcn.com) for the frontend components.
  - 🤖 An automatically generated frontend client.
  - 🧪 [Playwright](https://playwright.dev) for end-to-end testing.
  - 🦇 Dark mode support.
- ☁️ [FastAPI Cloud](https://fastapicloud.com) for deployment.
- 🐋 [Docker Compose](https://www.docker.com) for local services and self-hosted deployment.
  - 📞 [Traefik](https://traefik.io) as a reverse proxy with automatic HTTPS.
- 🔒 Secure password hashing by default.
- 🔑 JWT (JSON Web Token) authentication.
- 📫 Email-based password recovery.
- ✉️ [React Email](https://react.email) for email templates.
- 📬 [Mailpit](https://mailpit.axllent.org) for local email testing during development.
- ✅ Tests with [Pytest](https://pytest.org).
- 🏭 CI (continuous integration) and CD (continuous deployment) based on GitHub Actions.

### Dashboard Login

![Dashboard login screenshot](img/login.png)

### Dashboard - Admin

![Admin dashboard screenshot](img/dashboard.png)

### Dashboard - Items

![Items dashboard screenshot](img/dashboard-items.png)

### Dashboard - Dark Mode

![Dark mode dashboard screenshot](img/dashboard-dark.png)

### React Email Templates

![Email templates screenshot](img/react-email.png)

### Mailpit - Local Email Testing

![Mailpit screenshot](img/mailpit.png)

### Interactive API Documentation

![API docs](img/docs.png)

## How to Use It

Click the **Use this template** button at the top of this page to create a new repository.

## Backend Development

Backend docs: [backend/README.md](./backend/README.md).

## Frontend Development

Frontend docs: [frontend/README.md](./frontend/README.md).

## Deployment

FastAPI Cloud deployment: [deployment.md](./deployment.md).

Self-hosted deployment with Docker Compose: [deployment-docker-compose.md](./deployment-docker-compose.md).

## Development

General development docs: [development.md](./development.md).

This includes the local FastAPI and Vite workflow, Docker Compose services, `.env` configuration, and more.

## Release Notes

Check the file [release-notes.md](./release-notes.md).

## License

The Full Stack FastAPI Template is licensed under the terms of the MIT license.
