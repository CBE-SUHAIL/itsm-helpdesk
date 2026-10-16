# IT Helpdesk and Service Management System

An internship project built by Suhail and Kavin. The planned system follows the
ITSM architecture workbook: a React web app, FastAPI services, SQLAlchemy, and
PostgreSQL, all running locally.

Start with the [current handoff](docs/HANDOFF.md), [team workflow](docs/WORKFLOW.md),
[requirements](docs/REQUIREMENTS.md), and [API contract](docs/API_CONTRACT.md).
The implementation checklist and mentor update log are maintained separately.

## Quick start

From a fresh clone, with Docker running and Python 3.12+ and Node.js 20+
installed. Each step is the detailed one later in this file.

```bash
# 1. Configuration. Local values only; .env is gitignored and never committed.
cp .env.example .env                            # Windows: Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into JWT_SECRET

# 2. Database
docker compose up -d
docker compose ps                               # wait for "(healthy)"

# 3. Backend. Leave it running in this terminal.
cd backend
python -m venv .venv
source .venv/bin/activate                       # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m app.seed_demo                         # optional demo accounts; prompts for a password
uvicorn app.main:app --reload

# 4. Frontend, in a second terminal from the repository root
cd frontend
npm install
npm run dev
```

Sign in at http://localhost:5173 with a seeded account, or open
http://localhost:8000/docs for the API. If something does not work, the checks
under [Verify it works](#verify-it-works) and the
[Troubleshooting](#troubleshooting) notes say what to look at first.

## Current status

F03 and F04 are scaffolded: the React app, the FastAPI backend, and a local
PostgreSQL container all start from the commands below. F05 adds the Alembic
migration chain. D01 adds the `roles` and `users` tables, D02 adds
`categories` and `tickets`, D03 adds `comments` and `ticket_history`, D04 adds
`attachments` and `audit_logs`, and D05 adds `notifications` and
`system_settings` plus the seeded settings row. D06 adds `knowledge_articles`;
A02 adds `refresh_tokens`. D08 adds an opt-in demo seed. Schema
decisions and the table-to-task map are in
[docs/DATA_MODEL.md](docs/DATA_MODEL.md). D07 adds no table: it wires up the ORM
relationships between the original eleven and the session handling in `app/core/db.py`.
The implemented API routes are health; login, refresh, logout, and current user;
admin user management (A01–A07); the ticket core — create, read, assignment,
status, priority, category change, comments, and history (T01–T04, T06);
category management (T05); attachment upload, listing, and download (T07);
notification listing, mark-read, and dismiss (S01); and the admin-only audit-log
read (G01). Articles, dashboards, reports, and settings arrive with later tasks,
so those contract routes are still planned. React has login, a protected
workspace, and an admin user screen; ticket pages are still future work.

## Stack

| Piece | Technology | Default address |
| --- | --- | --- |
| Frontend | React + TypeScript (Vite) | http://localhost:5173 |
| Backend | FastAPI + Uvicorn | http://localhost:8000 |
| Database | PostgreSQL 16 (Docker) | localhost:5432 |

The frontend and backend run natively so hot reload works; only the database is
containerised. The React app calls relative `/api/v1/...` paths, which the Vite
development server proxies to the backend, so no backend host is hardcoded.

## Prerequisites

- Python 3.12 or newer
- Node.js 20 LTS or newer
- Docker, either Docker Desktop or Docker Engine inside WSL2 on Windows

## Setup

### 1. Environment file

```bash
cp .env.example .env            # macOS, Linux, WSL
```

```powershell
Copy-Item .env.example .env     # Windows PowerShell
```

`.env` is gitignored and holds local development values only. Never commit real
secrets or real user data.

Before using login, generate a unique local JWT signing key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy that output into your own `.env` as `JWT_SECRET=...`. Kavin must generate
his own key on his computer. Never share or commit either key. The API health
check works without it, but login returns a setup error until it is set.

### 2. Database

```bash
docker compose up -d
docker compose ps               # wait for "healthy"
```

### 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # macOS, Linux, WSL
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

On Windows PowerShell, activate with `.\.venv\Scripts\Activate.ps1`.
Interactive API documentation is then at http://localhost:8000/docs.

### Optional local demo data (D08)

After `alembic upgrade head`, run from `backend/`:

```bash
python -m app.seed_demo
```

Enter and confirm a password when prompted. The seed creates one synthetic
employee, support agent, and admin, three `[demo]` categories, and five tickets
covering the ticket statuses. Their emails are `demo.employee@example.test`,
`demo.agent@example.test`, and `demo.admin@example.test`. No password is stored
in the repository or echoed in the terminal. They use a salted PBKDF2-SHA256
hash; A01's login code verifies it with `app.core.passwords.verify_password`.
Rerunning the command adds missing demo rows but does not duplicate or reset
existing ones, including passwords or ticket edits. The same entered password
applies only to *newly created* demo users. Use this only in a local demo
database, never with real employee data. Demo tickets are synthetic snapshots;
their direct insertion does not simulate API history or audit actions.
There is no password-reset route in v1; keep the local demo password available
to the teammate using that database.

### Authentication and user administration (A01–A07)

Sign in at the frontend with a seeded account. Access tokens expire after 30
minutes; refresh tokens last seven days, rotate on use, are stored hashed in
PostgreSQL, and are revoked on logout. React keeps the access token in memory
and the refresh token in this browser's local storage to restore a session
after a reload. This is for the local internship demo, not a production
deployment handling real employee data. Signing out revokes the stored refresh
token; an already-issued access token can remain valid until its 30-minute
expiry. Role changes invalidate old access tokens immediately.

Only admins can open **Users** to create an account, filter the user list,
change a name or role, and deactivate/reactivate a user. Users are not deleted.
There is no public registration, password reset, or password-change screen in
this phase. The backend enforces admin access even if someone enters the URL
or calls the API directly.

### Attachments on disk (T07)

Uploaded files have their metadata in PostgreSQL and their bytes in a local
directory: `var/uploads` beside the repository root by default, which is
gitignored and created on the first upload. Set `UPLOAD_DIR` in `.env` to move
it; a relative value is resolved against the repository root, so the same `.env`
works from any shell. No static route serves that directory, so the bytes are
reachable only through `GET /tickets/{id}/attachments/{attachment_id}`, which
checks ticket access first and returns the original file name rather than any
storage path.

The allowed types and the size limit come from the seeded `system_settings` row:
PDF, PNG, JPEG, and TXT up to 10 MB by default. The type is the one the client
declares in the multipart part, matched against that list; the bytes are not
sniffed in v1. Nothing is deleted in v1, so clearing the directory by hand leaves
rows whose file is gone; those downloads answer `404` rather than failing.

### 4. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Verify it works

| Check | Command | Expected |
| --- | --- | --- |
| Database is running | `docker compose ps` | `... (healthy)` |
| Migration chain is at head | `cd backend && alembic current` | `20261015_a02_refresh_tokens (head)` |
| API reaches the database | `curl http://localhost:8000/api/v1/health` | `{"status":"ok","database":"ok"}` |
| Backend tests | `cd backend && pytest -q` | All tests pass |
| API documentation is complete | open http://localhost:8000/docs | Every route has a summary, a tag, and a bearer padlock |
| Frontend reaches the API | open http://localhost:5173 | Sign-in screen; a seeded account can log in |

`GET /api/v1/health` answers `503` with
`{"status":"degraded","database":"unavailable"}` when PostgreSQL is
unreachable, so a broken dependency is visible rather than hidden behind a 200.
The pytest test is an integration test: start the database first.

## Project structure

```
backend/                FastAPI application
  app/main.py           application entry point, CORS, router mounting
  app/core/config.py    settings, read from the repository-root .env
  app/core/db.py        database connectivity check
  app/core/storage.py   T07 attachment bytes, with server-generated file names
  app/core/passwords.py demo-compatible password hashing and verification
  app/seed_demo.py      opt-in, repeatable local demo data
  app/models/           SQLAlchemy Base, Roles, Users, Categories, Tickets,
                        Comments, Ticket History, Attachments, Audit Logs,
                        Notifications, System Settings, Refresh Tokens, and naming convention
  app/api/v1/           versioned routes (health, auth, users, categories,
                        tickets, attachments, notifications, audit logs)
  alembic/              migration environment and revisions
  alembic.ini           Alembic config; the database URL lives in .env instead
  tests/                pytest suite
frontend/               React + TypeScript app (Vite)
var/uploads/            T07 attachment bytes (gitignored, created on first upload)
compose.yaml            PostgreSQL service
.env.example            committed sample configuration, no secrets
docs/                   requirements, API contract, data model, workflow, handoff
```

## Troubleshooting

**The health check reports `database: unavailable`, or pytest fails with a
connection timeout.** The container is not running or not reachable. Check
`docker compose ps`, then start it with `docker compose up -d`. On Windows with
Docker Engine inside WSL2, the WSL virtual machine shuts down roughly a minute
after the last WSL command, which stops Docker and the database with it. Keep a
WSL terminal open while you work, or run `docker compose up -d` again before
starting the backend.

**`uvicorn: command not found`.** The virtual environment is not active;
activate it as shown in step 3.

**`alembic` reports a connection timeout.** The database is down; see the
previous item. `alembic` reads the same repository-root `.env` the backend does,
so anything that fixes one fixes the other. Run it from `backend/`, because
`alembic.ini` is there.

**A port is already in use.** Change `POSTGRES_PORT` in `.env` for the database,
or pass `--port` to `uvicorn`. If the backend moves off 8000, update the proxy
target in `frontend/vite.config.ts`.

## Repository documentation

- [docs/HANDOFF.md](docs/HANDOFF.md) - current state, owner, and next action
- [docs/WORKFLOW.md](docs/WORKFLOW.md) - the two-person relay workflow
- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) - feature rules and decisions
- [docs/API_CONTRACT.md](docs/API_CONTRACT.md) - route and payload contract
- [docs/postman/](docs/postman/) - G04 Postman collection and how to run it
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md) - schema, naming conventions, and table ownership
