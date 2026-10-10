# Current handoff

Updated: 10 October 2026
Checklist task: D01 (Users and Roles tables)
Branch: `feat/D01-users-roles`, from `main` at `4a549ed`
Active owner: Suhail
Incoming owner: Kavin, after D01 is tested, pushed, and offered for review

## Where the project stands

F01-F04 are on `main`. F05 merged in pull request #4 as `4a549ed` and provides
the Alembic migration mechanism and data-model notes. D01 is the next assigned
implementation row. F06 (API request/response shapes) is also assigned to
Suhail and remains open.

The local checklist's F05 acceptance says an ER diagram and migrations cover
every architecture entity. Pull request #4 intentionally delivered only an
empty baseline and no ER diagram. Treat F05 as a scope/acceptance gap to resolve
with Kavin; merging that PR did not satisfy the original done-when wording.

## D01 work in this branch

- Added `roles` and `users` models and an Alembic migration. Users have a
  required role reference, a unique normalized email, a nonblank name and
  password hash, an active flag, UUID IDs, and UTC timestamps. Role names are
  restricted to Employee, Support agent, and Admin.
- Registered the models with Alembic's shared metadata so its drift check can
  work before D07 adds all remaining models and session handling.
- Added a PostgreSQL constraint test and made the migration tests roll back
  their downgrade/upgrade transaction so running tests cannot erase local rows.
- Corrected `docs/DATA_MODEL.md`'s D02-D06 table assignment against the local
  checklist. The old F05 mapping was provisional and did not match it.
- Updated the README to describe D01 and the new migration head.

## Checks and open items

- Python files parse, and `git diff --check` is clean.
- On 10 October, Suhail ran `.venv/bin/alembic upgrade head` successfully and
  `.venv/bin/pytest -q` reported **4 passed, 1 warning** (a Starlette
  `TestClient` deprecation warning). The database migration reached
  `20261010_0001_d01_users_roles`.
- Suhail's Mac also runs a separate PostgreSQL server on loopback port 5432.
  The ignored local `.env` uses `POSTGRES_PORT=5433` so the backend reaches the
  Docker database. That machine's Docker project is `itsm-helpdesk-d01`; use
  `docker compose -p itsm-helpdesk-d01 ...` there. Do not copy this local port
  choice or Docker project name into Kavin's environment without checking it.
- The project checklist workbook is local-only and still has stale statuses.
  Update it after the PR is merged, with evidence links.

## Exact next action

Push this verified D01 branch, then open a PR against `main` for Kavin to
review. Kavin should not start editing from an older remote state; after the
push, he can review the PR and pull the task branch if changes are needed.
After D01 merges, update the checklist with the PR evidence, pull `main`, and
then start F06 unless the team first chooses to close the F05 acceptance gap.
