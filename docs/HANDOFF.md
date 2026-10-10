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
- Integration tests are **not yet run**. This environment cannot install the
  Python packages from the network or access Docker Desktop's API. Do not mark
  D01 done or push it as verified until the commands below pass on Suhail's Mac.
- The project checklist workbook is local-only and still has stale statuses.
  Update it after the PR is merged, with evidence links.

## Exact next action

On Suhail's Mac, start Docker Desktop, then from the repository root run:

```bash
cp -n .env.example .env  # keep an existing local configuration
backend/.venv/bin/python -m pip install -r backend/requirements.txt
docker compose up -d
cd backend
.venv/bin/alembic upgrade head
.venv/bin/pytest -q
```

If those checks pass, update this note with the actual results, commit the D01
branch, push it, and open a PR for Kavin to review. If they fail, fix D01 here
before handoff. The next code task after D01 review is F06, unless the team
first chooses to close the F05 acceptance gap.
