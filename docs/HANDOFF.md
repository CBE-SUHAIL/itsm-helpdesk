# Current handoff

Updated: 8 October 2026
Checklist tasks: F03 and F04
Branch: `feat/F03-F04-scaffold`, off `docs/F02-closeout` at `814b62a`
Active owner: Kavin
Incoming owner: Suhail (reviewer for F03/F04)

## Where the project actually stands

F01 and F02 are done in substance: pull request #1 was merged into `main` as
commit `4503712`, and pull request #2 carries the four F02 review decisions but
is **still open and unmerged**. Those decisions are not on `main` yet, so this
branch was cut from the closeout tip `814b62a` rather than from `main`. If pull
request #2 is squash-merged, its commits get new hashes and this base goes
stale; because this branch still has no commits at that point, the fix is to
recreate it from the updated `main`.

## Done in this handoff

F03 and F04 are scaffolded on this branch. The repository now has an
application, where before it had only documentation:

- `compose.yaml` runs PostgreSQL 16 (`postgres:16-alpine`) with a named volume,
  a healthcheck, and `restart: unless-stopped`.
- `.env.example` is committed with local placeholders and no secrets. `config.py`
  builds the SQLAlchemy URL from `POSTGRES_*`, and `compose.yaml` creates the
  container from the same variables, so the two cannot drift apart.
- The FastAPI backend runs from documented commands and exposes exactly one
  route, `GET /api/v1/health`, which runs `SELECT 1` against PostgreSQL and
  answers 503 when the database is unreachable. No models, no migrations, and no
  session factory: those belong to F05, D01-D07, and A01-A02.
- The React app is a Vite + TypeScript project. It calls relative `/api/v1/...`
  paths, and the Vite dev server proxies them to the backend, so no backend host
  is hardcoded and CORS stays a fallback for a built frontend.
- `README.md` documents setup and a four-step verification, and records the WSL2
  idle-shutdown behaviour described under open items below.

## Checks run

- `docker compose ps` reports the container `(healthy)`.
- `curl http://localhost:8000/api/v1/health` returns `{"status":"ok","database":"ok"}`.
- `curl http://localhost:5173/api/v1/health`, through the Vite proxy, returns the
  same body, which proves the whole chain works: React to Vite to FastAPI to
  PostgreSQL.
- `cd backend && pytest -q` reports `1 passed`. The test is deliberately an
  integration test; mocking the database would prove the app boots, not that
  F04's database is reachable.
- `npm run build` (`tsc -b && vite build`) completes with no type errors.
- The frontend page serves with the title `ITSM Helpdesk`.
- `git check-ignore` confirms `.env`, `backend/.venv`, `frontend/node_modules`, and
  `frontend/dist` are all ignored. 30 files are staged and none contain secrets.

## Open items carried forward

1. Pull request #2 still needs Suhail's review. It is a documentation-only
   change and it is the gate on `main` matching the contract.
2. **Suhail's Docker situation is unknown.** The README's golden path assumes
   Docker is available, either as Docker Desktop or as Docker Engine inside
   WSL2. If Suhail cannot run Docker, F04 needs a short native-install appendix,
   and its content depends on his operating system, so it was deliberately not
   guessed. This is the one question the reviewer should answer.
3. On Windows with Docker Engine inside WSL2, the WSL virtual machine shuts down
   roughly a minute after the last WSL command, which stops Docker and the
   database with it. Keep a WSL session open while working, or run
   `docker compose up -d` again before starting the backend. This is documented
   in the README troubleshooting section.
4. The checklist workbook still shows F01 and F02 as "In progress". It is a
   local-only file outside Git and still needs F01 and F02 marked Done with pull
   request #1 as evidence, and F01 noted as proven in one direction only.

## Exact next action

Suhail reviews this pull request. He should follow the four verification steps in
`README.md` on his own machine, then answer one question in review: does he have
Docker available, as Docker Desktop or as Docker Engine inside WSL2? If he does
not, a native-install appendix is added to the README in the same review round,
matching his operating system. Any change agreed in review goes onto this branch
before it merges, so `main` matches the documented setup.
