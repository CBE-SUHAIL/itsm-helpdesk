# IT Helpdesk and Service Management System

An internship project built by Suhail and Kavin. The planned system follows the
ITSM architecture workbook: a React web app, FastAPI services, SQLAlchemy, and
PostgreSQL, all running locally.

Start with the [current handoff](docs/HANDOFF.md), [team workflow](docs/WORKFLOW.md),
[requirements](docs/REQUIREMENTS.md), and [API contract](docs/API_CONTRACT.md).
The implementation checklist and mentor update log are maintained separately.

## Current status

F03 and F04 are scaffolded: the React app, the FastAPI backend, and a local
PostgreSQL container all start from the commands below. F05 adds the Alembic
migration chain. Its baseline revision creates no tables on purpose, so the
schema itself arrives with checklist rows D01-D06 and `refresh_tokens` with
A01/A02; the schema and naming decisions are in
[docs/DATA_MODEL.md](docs/DATA_MODEL.md). The only API route is still the health
check.

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
| Migration chain is at head | `cd backend && alembic current` | `20261008_2150_baseline (head)` |
| API reaches the database | `curl http://localhost:8000/api/v1/health` | `{"status":"ok","database":"ok"}` |
| Backend tests | `cd backend && pytest -q` | `3 passed` |
| Frontend reaches the API | open http://localhost:5173 | `backend: ok` and `database: ok` |

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
  app/models/           SQLAlchemy Base and the shared naming convention
  app/api/v1/           versioned routes (health only so far)
  alembic/              migration environment and revisions
  alembic.ini           Alembic config; the database URL lives in .env instead
  tests/                pytest suite
frontend/               React + TypeScript app (Vite)
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
- [docs/DATA_MODEL.md](docs/DATA_MODEL.md) - schema, naming conventions, and table ownership
