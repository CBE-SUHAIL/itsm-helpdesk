# Current handoff

Updated: 9 October 2026
Checklist task: F05 (database schema and migrations)
Branch: `feat/F05-schema-migrations`, off `e80717f`
Pull request: opened from this branch into `main`; the number is added in the
follow-up commit, as was done for F02 and F03/F04
Active owner: Kavin (F05)
Incoming owner: Suhail (reviewer for F05)

## Where the project actually stands

F01 through F04 are complete and on `main`. Pull request #1 merged as `4503712`,
#2 as `93a85c5`, and #3 (the F03/F04 scaffold) as `e80717f`. The four F02 review
decisions are on `main` and remain the working contract.

`feat/F03-F04-scaffold` has been deleted, locally and on the remote;
`git ls-remote --heads origin` now returns only `refs/heads/main`. This branch
was cut from `e80717f`, which is the tip of `main`, so the base is current and
no rebase is needed.

## Done in this handoff

F05 delivers the migration **mechanism**, not the tables. The baseline revision
creates nothing on purpose; the reasoning is recorded in `docs/DATA_MODEL.md`
and in the revision's own docstring.

- `backend/alembic.ini` is the generated config with three deliberate changes:
  `sqlalchemy.url` is left unset so credentials have exactly one home,
  `script_location` is anchored with `%(here)s` so it works from any directory,
  and the filename template is `YYYYMMDD_HHMM_<rev>_<slug>` so revisions sort by
  date in the filesystem.
- `backend/alembic/env.py` builds the URL from `app.core.config`, which reads the
  repository-root `.env`, so Compose and Alembic can never target different
  databases. It escapes `%` before handing the URL to configparser, passes
  `compare_type=True` to both the offline and online paths, and sets
  `connect_timeout=5` to match `app/core/db.py`.
- `backend/alembic/env.py` supports Alembic's documented connection sharing:
  a caller may put an open connection in `config.attributes["connection"]` and
  the whole chain runs inside it. `tests/test_migrations.py` uses that to keep
  the suite to **one** connection per test, which matters behind the WSL2 port
  forward.
- `backend/alembic/versions/20261008_2150_baseline.py` is the chain root:
  `down_revision = None`, and both `upgrade()` and `downgrade()` are no-ops by
  design.
- `backend/app/models/__init__.py` defines the SQLAlchemy `Base` and the metadata
  naming convention (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`). This had to exist before
  any table, because constraint names are compared by name during autogenerate.
- `backend/alembic/script.py.mako` and `backend/alembic/README` are the generated
  scaffolding, with the revision template given real docstrings.
- `backend/tests/test_migrations.py` adds two tests: the chain reaches head from
  base, reports head, is repeatable, and `alembic_version` exists; and Alembic's
  own `command.check()` drift guard, which is vacuous against an empty schema
  today and becomes meaningful when D07 lands the models.
- `backend/requirements.txt` adds `alembic>=1.14`.
- `docs/DATA_MODEL.md` is **new**. Four files referenced it and it did not exist.
  It records what F05 decided, the naming convention, the conventions that hold
  for every table, and the row-to-table ownership map. The D02-D06 split there is
  a working plan to confirm against the checklist workbook.
- `README.md` is refreshed: the status paragraph describes F05, the setup adds
  `alembic upgrade head`, the verify table gains an Alembic row and corrects
  `1 passed` to `3 passed` (stale since F05), the structure block lists the new
  directories, and troubleshooting gains an Alembic entry.
- The dangling reference in `env.py` to a `scripts/verify_migrations.py` that was
  never written has been repointed at the test that actually does the job.

## Checks run

All against the running container, in this order.

- `docker compose ps` reports `itsm-helpdesk-db-1 ... Up (healthy)`.
- `cd backend && alembic current` reports `20261008_2150_baseline (head)`.
- `alembic history` reports
  `<base> -> 20261008_2150_baseline (head), baseline: establish the migration chain`.
- `alembic upgrade head` is a clean no-op when already at head, and `alembic
  current` still reports head afterwards.
- `cd backend && pytest -q` reports **3 passed, 1 warning in 16.30s**. The warning
  is the pre-existing `StarletteDeprecationWarning` from `httpx` with
  `starlette.testclient`, raised by F03/F04's health test, not by F05.
- Toolchain: alembic 1.20.0, SQLAlchemy 2.1.4, psycopg 3.3.6.

## Open items carried forward

1. `docs/DATA_MODEL.md` assigns the tables to D01-D06. D01 is confirmed by the
   F03/F04 handoff; the D02-D06 grouping is a working plan, because the checklist
   workbook is local-only and not in Git. Confirm it and correct the table in the
   same commit as the first migration that disagrees.
2. **Suhail's Docker situation is still unknown**, carried from the F03/F04
   handoff and still unanswered. If he cannot run Docker, the README needs a
   short native-install appendix, and its content depends on his operating
   system, so it was not guessed.
3. On Windows with Docker Engine inside WSL2, the WSL virtual machine shuts down
   roughly a minute after the last WSL command, which stops Docker and the
   database with it. Keep a WSL session open while working — on this side that
   means holding one open in a background terminal — or run
   `docker compose up -d` again before starting the backend or running a
   migration. Documented in the README troubleshooting section.
4. The checklist workbook still shows F01 and F02 as "In progress". It is a
   local-only file outside Git and still needs F01 and F02 marked Done with pull
   requests #1 and #2 as evidence, F01 noted as proven in one direction only, and
   F03 and F04 marked Done with pull request #3 once it merges.
5. No tables exist yet, by design. `refresh_tokens` is the only table outside
   D01-D06, and it belongs to A01/A02.

## Exact next action

Suhail reviews the F05 pull request. He should run the README verification table
on his own machine — including `cd backend && alembic current`, which now has its
own row — and answer the Docker question left open from the previous handoff
(open item 2) in the same round.

Reviewers should push back on one decision in particular if they disagree:
`docs/DATA_MODEL.md` stores enumerated values as text plus a check constraint
rather than as PostgreSQL `enum` types. It is a deliberate F05 choice with the
reasoning recorded there, and it is the cheapest one to reverse now and the most
expensive to reverse once tables exist.

If the review agrees, D01 (Users and Roles tables) is the next row and can start
on Suhail's side against the F04 database that is already running.
