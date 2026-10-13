# Current handoff

Updated: 14 October 2026
Checklist task: D02 (Tickets and Categories tables)
Branch: `feat/D02-tickets-categories`, off `main` at `cd1afbb`
Pull request: [#9](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/9) into `main`
Active owner: Kavin
Incoming owner: Suhail (reviewer for D02)

## Where the project stands

F01-F04 are on `main`. F05 merged as pull request #4 (`4a549ed`) and provides the
Alembic migration mechanism, with the ER-diagram part of its acceptance still
open (item 4 below). D01 merged as pull request #5 (`1faf1b8`). F06 merged as
pull request [#6](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/6)
(`6bdc3c3`) and its review is recorded in the PR and in
`docs/API_CONTRACT.md`. Pull requests #7 and #8 were documentation closeouts.
`origin` carries only `main`.

D02 is this branch. It adds the `categories` and `tickets` tables, so the
database now holds `roles`, `users`, `categories`, and `tickets`.

## Done in this handoff

- `backend/app/models/category.py` and `backend/app/models/ticket.py` define the
  two tables; both are registered in `backend/app/models/__init__.py` so Alembic
  sees them in `Base.metadata`.
- `backend/alembic/versions/20261014_d02_tickets_categories.py` is the new head,
  `down_revision = 20261010_0001_d01_users_roles`.
- `backend/tests/test_tickets_categories_schema.py` exercises the real
  PostgreSQL constraints inside one rolled-back transaction: the Open/Medium
  defaults, a null assignee, and rejection of an unknown or lowercase status or
  priority, blank titles and descriptions, missing or dangling
  category/creator/assignee references, a duplicate or blank category name, a
  null category description, and deletion of a category or user a ticket still
  references.
- `backend/tests/test_migrations.py` now asserts the `categories` and `tickets`
  tables exist after reaching head.
- `docs/DATA_MODEL.md` gains a `categories` entry, a **D02 decisions** section,
  and no longer lists the ticket status and priority constraints as undecided.
- `README.md` reports the new head and lists the new models.

## Decisions worth reviewing

1. Status and priority are text plus `CHECK`, matching `REQUIREMENTS.md`
   exactly, and are case-sensitive: `open` and `medium` are rejected.
2. The legal transitions are **not** database constraints. They are T02
   business rules, and encoding them here would make a legitimate intermediate
   state unrepresentable.
3. Indexes are on the three foreign keys only. `status` and `priority` are
   deliberately unindexed: 5 and 4 distinct values make a sequential scan the
   cheaper plan at demo size.
4. `categories.description` is `NOT NULL`, because the contract's Category shape
   always carries it and never marks it nullable. Empty is allowed.
5. `response_due_at` and `resolution_due_at` are required and copied from the
   SLA targets in force at creation; `response_overdue` and `resolution_overdue`
   are not columns because they are derived from the clock.
6. The resolution note is stored as `ticket_history.reason` (D03), because the
   contract's Ticket shape has no resolution-note field.
7. Revision ids must fit `alembic_version.version_num`, which is `varchar(32)`.
   D01's `<date>_<counter>_<row>_<slug>` pattern does not scale: the obvious
   `20261014_0001_d02_tickets_categories` is 36 characters and PostgreSQL
   rejected it during this work. D02 uses `20261014_d02_tickets_categories`
   (31). Later rows must stay at 32 or fewer.

## Checks run

On Kavin's machine, against the containerised PostgreSQL, in this order.

- `docker compose ps` reports `itsm-helpdesk-db-1 ... Up (healthy)`.
- `alembic upgrade head` ran the chain from this database's previous state
  (`20261008_2150_baseline` — Kavin's volume had not yet applied D01) through
  D01 and D02 with no error.
- `alembic current` reports `20261014_d02_tickets_categories (head)`.
- `alembic check` reports **No new upgrade operations detected**, so the models
  and the migration agree. This guard earned its keep during D02: it caught the
  migration creating `status` and `priority` indexes the models did not declare,
  which is why those two indexes were removed.
- `cd backend && pytest -q` reports **5 passed, 1 warning in 26.37s**. The
  warning is the pre-existing Starlette `TestClient` deprecation warning raised
  by F03/F04's health test, not by D02.
- Practical note for this machine: the WSL2 VM stops after about a minute
  without an attached WSL client, which kills Docker mid-run and makes every
  database test fail with a connection timeout. Hold a WSL session open for the
  whole run (`wsl -d Ubuntu -- sleep 600 &` in the same shell works) before
  starting the backend or Alembic.

## Open items carried forward

1. **Article category**, still the one F06 item open. `docs/DATA_MODEL.md` and
   checklist row D06 both require a category on articles; the contract's
   `Article` shape omits it. Decide before D06 (owner Suhail, checklist target
   20 October) and update the contract, `DATA_MODEL.md`, and tests in one
   commit. Reusing `categories` is the cheapest option.
2. Two F06 wording items to fold into the D06/D07 doc touch: `GET /articles`
   implies agents and admins see every draft while `GET /articles/{id}` returns a
   draft only to its author agent or an admin; and `PATCH /articles/{id}`'s "Who"
   column reads "Draft author or admin" while `REQUIREMENTS.md` says admins may
   edit any article.
3. No route changes a password — no admin reset and no self-service change. It
   matches checklist row A06's wording, so it is not a defect, but it should be
   stated as a v1 limitation before A06 is implemented.
4. **F05 acceptance gap, still open and owned by Kavin.** The checklist's F05
   done-when is "ER diagram and migrations cover every database entity in the
   architecture"; pull request #4 delivered only an empty baseline and no ER
   diagram. The migration half closes as D02-D06 and D07 land tables; the ER
   diagram is still missing and now has four real tables to cover.
5. The local-only checklist workbook is stale: F05 is "In progress", D01, D02,
   and F06 are still "Not started". Update statuses and evidence links after this
   pull request merges, leaving F06 open until item 1 is decided.
6. Targets have slipped: F06 was due 12 October and D02 was due 13 October; both
   finished on 14 October. Worth stating in the next mentor update.

## Exact next action

Suhail reviews pull request #9 as the checklist's D02 reviewer. The decisions in
the list above are the ones to push back on if he disagrees; item 7 in
particular is a convention change for every later migration.

After the pull request merges, both switch to `main` and run
`git pull --ff-only`, and the checklist rows for D01 and D02 are updated with
their pull request links. Then **D03 (Comments and Ticket History tables)** is
the next row — checklist owner Kavin, reviewer Suhail — on branch
`feat/D03-comments-history`, with `ticket_history.reason` already spoken for as
the home of the resolution note. Do not start D03 from an older remote state.
