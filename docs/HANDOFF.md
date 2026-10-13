# Current handoff

Updated: 14 October 2026
Checklist task: D03 (Comments and Ticket History tables)
Branch: `feat/D03-comments-history`, off `main` at `57a90e4`
Pull request: [#10](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/10) into `main`
Active owner: Kavin
Incoming owner: Suhail (reviewer for D03)

## Where the project stands

F01-F04 are on `main`. F05 merged as pull request #4 (`4a549ed`) and provides the
Alembic migration mechanism, with the ER-diagram part of its acceptance still
open (item 5 below). D01 merged as pull request #5 (`1faf1b8`). F06 merged as
pull request #6 (`6bdc3c3`) with its review recorded in the PR and in
`docs/API_CONTRACT.md`. D02 merged as pull request [#9](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/9)
(`57a90e4`). Pull requests #7 and #8 were documentation closeouts, and `origin`
carries only `main`.

**No pull request after #6 has been reviewed.** #7 and #8 were documentation
closeouts, and #9 (D02) was merged without a review at Kavin's direction. The
checklist's evidence column should say so rather than implying a review trail
that does not exist.

D03 is this branch. The database now holds `roles`, `users`, `categories`,
`tickets`, `comments`, and `ticket_history`.

## Done in this handoff

- `backend/app/models/comment.py` and `backend/app/models/ticket_history.py`
  define the two tables and are registered in `backend/app/models/__init__.py`.
- `backend/alembic/versions/20261014_d03_comments_history.py` is the new head,
  `down_revision = 20261014_d02_tickets_categories`, and it is 29 characters,
  inside the `varchar(32)` limit D02 discovered.
- `backend/tests/test_comments_history_schema.py` exercises the real constraints
  inside one rolled-back transaction: a valid comment and one valid history row
  per field, rejection of a blank or null body, null or dangling ticket and
  author references, an unknown, mis-cased, or null `field`, a null timestamp,
  and the restrictive deletes that stop a ticket or user being removed while
  comments or history still reference them. It also asserts the composite index
  exists in the database and that neither table has an `updated_at` column.
- `backend/tests/test_migrations.py` now asserts `comments` and
  `ticket_history` exist after reaching head.
- `docs/DATA_MODEL.md` gains a `comments` entry, a **D03 decisions** section, and
  no longer lists the ticket-history index strategy as undecided.
- `README.md` reports the new head and lists the new models.

## Decisions worth reviewing

1. `comments` and `ticket_history` carry `created_at` only, with no `updated_at`.
   Neither has an update route, so a comment is never edited and a history row is
   written once.
2. `ticket_history.field` is the closed set `status`, `assignee_id`,
   `category_id`, `priority` as a check constraint — the exact list of changes
   `REQUIREMENTS.md` says must be recorded.
3. "One row per changed field" is enforced by T02/T03's write path, **not** by an
   `old_value IS DISTINCT FROM new_value` constraint, for the same reason
   transitions are not constraints: T02 owns that meaning and a constraint could
   reject a legitimate record.
4. `old_value` and `new_value` are `varchar(64)` (a label or the string form of a
   UUID) and `reason` is `text`, because the resolution note lands there.
5. The index strategy this row was left to decide: one composite index per table
   on `(ticket_id, created_at)`, because both read routes filter by ticket and
   order oldest first. No index on `author_id` or `actor_id`, since no route
   looks either up by author.

## Checks run

On Kavin's machine, against the containerised PostgreSQL, in this order.

- `docker compose ps` reports `itsm-helpdesk-db-1 ... Up (healthy)`.
- `alembic upgrade head` applied D03 on top of D02 with no error.
- `alembic current` reports `20261014_d03_comments_history (head)`.
- `alembic check` reports **No new upgrade operations detected**, so the models
  and the migration agree.
- `cd backend && pytest -q` reports **7 passed, 1 warning in 31.55s**. The
  warning is the pre-existing Starlette `TestClient` deprecation warning from
  F03/F04, not D03.
- The database now contains all seven tables: `alembic_version`, `categories`,
  `comments`, `roles`, `ticket_history`, `tickets`, `users`, with
  `ix_comments_ticket_id_created_at` and
  `ix_ticket_history_ticket_id_created_at`.
- Practical note carried forward: the WSL2 VM stops after about a minute without
  an attached WSL client, which kills Docker mid-run and fails every database
  test with a connection timeout. Hold a WSL session open for the whole run
  (`wsl -d Ubuntu -- sleep 900 &` in the same shell works).

## Open items carried forward

1. **Article category**, still the one F06 item open. `docs/DATA_MODEL.md` and
   checklist row D06 both require a category on articles; the contract's
   `Article` shape omits it. Decide before D06 (owner Suhail, checklist target
   20 October) and update the contract, `DATA_MODEL.md`, and tests in one commit.
   Reusing `categories` is the cheapest option.
2. Two F06 wording items to fold into the D06/D07 doc touch: `GET /articles`
   implies agents and admins see every draft while `GET /articles/{id}` returns a
   draft only to its author agent or an admin; and `PATCH /articles/{id}`'s "Who"
   column reads "Draft author or admin" while `REQUIREMENTS.md` says admins may
   edit any article.
3. No route changes a password — no admin reset and no self-service change. It
   matches checklist row A06's wording, so it is not a defect, but it should be
   stated as a v1 limitation before A06 is implemented.
4. The review trail: #7, #8, and #9 have no GitHub review. Either review them in
   the checklist evidence honestly, or start requesting review again from #10 on.
5. **F05 acceptance gap, still open and owned by Kavin.** The checklist's F05
   done-when is "ER diagram and migrations cover every database entity in the
   architecture"; pull request #4 delivered only an empty baseline and no ER
   diagram. The migration half now covers six of the tables; the ER diagram is
   still missing and has enough real tables to be worth drawing.
6. The local-only checklist workbook is stale: F05 is "In progress", and D01,
   D02, D03, and F06 are still "Not started". Update the statuses and evidence
   links after this pull request merges, leaving F06 open until item 1 is
   decided.
7. Targets have slipped: F06 was due 12 October, D02 and D03 were due 13
   October. Worth stating in the next mentor update.

## Exact next action

Suhail reviews pull request #10 as the checklist's D03 reviewer; the decisions
above are the ones to push back on if he disagrees.

After the pull request merges, both switch to `main` and run
`git pull --ff-only`, and the checklist rows for D01, D02, and D03 are updated
with their pull request links. Then **D04 (Attachments and Audit Logs tables)**
is the next row — checklist owner Kavin, reviewer Suhail — on branch
`feat/D04-attachments-audit`, with attachment storage layout on disk and the
audit-log index strategy still to be decided there. Keep every revision id to 32
characters or fewer. Do not start D04 from an older remote state.
