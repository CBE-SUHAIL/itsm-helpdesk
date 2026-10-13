# Current handoff

Updated: 14 October 2026
Checklist task: D05 (Notifications and System Settings tables)
Branch: `feat/D05-notifications-settings`, off `main` at `77dac86`
Pull request: [#12](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/12) into `main`
Active owner: Kavin for this branch
Incoming owner: **Suhail** — reviews and merges #12, then becomes Active owner of D06

## Where the project stands

F01-F04 are on `main`. F05 merged as pull request #4 (`4a549ed`) and provides the
Alembic migration mechanism, with the ER-diagram part of its acceptance still
open (item 6 below). D01 merged as #5 (`1faf1b8`), F06 as #6 (`6bdc3c3`) with its
review recorded in the PR and in `docs/API_CONTRACT.md`, D02 as #9 (`57a90e4`),
D03 as #10 (`0e25fcd`), and D04 as #11 (`77dac86`). Pull requests #7 and #8 were
documentation closeouts, and `origin` carries only `main`.

**Every schema row from D01 to D05 is now merged, and the database holds all ten
tables the architecture picture names**, plus `alembic_version`: `roles`, `users`,
`categories`, `tickets`, `comments`, `ticket_history`, `attachments`,
`audit_logs`, `notifications`, `system_settings`.

**No pull request after #6 has been reviewed.** #7-#11 were merged without one at
Kavin's direction, and the checklist evidence should say so rather than implying
a review trail that does not exist. **#12 is deliberately open for review** and is
the point at which the relay resumes, because the next row belongs to Suhail.

## Done in this handoff

- `backend/app/models/notification.py` and
  `backend/app/models/system_setting.py`, both registered in
  `backend/app/models/__init__.py`.
- `backend/alembic/versions/20261014_d05_notify_settings.py` is the new head,
  `down_revision = 20261014_d04_attachments_audit`, 28 characters. It creates both
  tables **and seeds the single settings row** — the first migration in this
  project that writes data rather than only schema.
- `backend/tests/test_notifications_settings_schema.py` exercises the real
  constraints in one rolled-back transaction, including the two things the row's
  done-when asks for: read and dismissed persist **independently** on the same
  notification, and an edited settings value persists. It also asserts the seeded
  row carries the exact `REQUIREMENTS.md` defaults, that a second settings row is
  impossible, that a settings row missing a priority key or with an empty type
  array is rejected, and that neither table lets its ticket or recipient be
  deleted.
- `backend/tests/test_migrations.py` now asserts `notifications` and
  `system_settings` exist after reaching head.
- `docs/DATA_MODEL.md` gains a **D05 decisions** section and no longer lists
  anything as deliberately undecided; `README.md` reports the new head and the
  full model list.

## Decisions worth reviewing

1. **Settings is one row, read as a singleton**, not a key/value table: the
   contract's Settings shape is a single object. `is_singleton` plus a unique
   constraint makes a second row impossible while keeping the UUID primary key
   convention.
2. **The migration seeds that row**, with the SLA targets (Low 24/72, Medium
   8/48, High 2/24, Critical 1/8), a 10 MiB size limit, and the four allowed MIME
   types. Reference data, not demo data: T01 cannot compute a ticket's deadlines
   without it. Demo users and tickets remain D08's job. If the team would rather
   migrations never write rows, this is the decision to revisit.
3. `sla_targets` is `JSONB` with a check constraint that all four priorities are
   present as keys; the inner hours are the API's to validate.
4. `allowed_attachment_types` is a native `text[]` (the contract's "array of MIME
   type strings"), required to hold at least one entry.
5. `notifications.type` is the closed set from the contract; a reassignment uses
   `assignment`.
6. `notifications` gets one composite index on `(recipient_id, created_at)`;
   `ticket_id` is unindexed because no route lists notifications by ticket.
7. `system_settings` is one of the few tables with `updated_at`, because
   `PATCH /settings` edits it in place. Notifications have no `updated_at`: their
   read and dismiss routes carry their own timestamps. Settings changes are
   audited by G01, so there is no separate history table.

## Checks run

On Kavin's machine, against the containerised PostgreSQL, in this order.

- `docker compose ps` reports `itsm-helpdesk-db-1 ... Up (healthy)`.
- `alembic upgrade head` applied D05 on top of D04 and ran the seed insert with no
  error — including the `JSONB` and `text[]` values, which is the part that could
  have failed silently.
- `alembic current` reports `20261014_d05_notify_settings (head)`.
- `alembic check` reports **No new upgrade operations detected**.
- Reading the live database shows exactly one `system_settings` row with
  `sla_targets` Low 24/72 … Critical 1/8, `max_attachment_bytes` 10485760, and
  the four MIME types.
- `cd backend && pytest -q` reports **11 passed, 1 warning in 42.05s**. The
  warning is the pre-existing Starlette `TestClient` deprecation from F03/F04.
- Practical note carried forward: the WSL2 VM stops about a minute after the last
  WSL command, which kills Docker mid-run and fails every database test with a
  connection timeout. Hold an attached client for the whole run
  (`wsl -d Ubuntu -- sleep 900 &` in the same shell).

## Open items carried forward

1. **Article category — this one blocks D06's own acceptance.** The authoritative
   checklist says D06 is done when "Articles have title, body, category, author,
   and published status", and `docs/DATA_MODEL.md` agrees, but the contract's
   `Article` shape has no category. D06's owner must decide it, then change the
   contract, `DATA_MODEL.md`, and tests in one commit. Because the contract
   defines no article-category route, reusing `categories` is the cheapest
   option. F06's row stays open until this is settled.
2. Two F06 wording items for the D06 doc touch: `GET /articles` implies agents and
   admins see every draft while `GET /articles/{id}` returns a draft only to its
   author agent or an admin; and `PATCH /articles/{id}`'s "Who" column reads
   "Draft author or admin" while `REQUIREMENTS.md` says admins may edit any
   article.
3. **No checklist row owns `GET /settings` and `PATCH /settings`.** The contract
   defines both, D05 stores the row they read and write, but no row in the local
   workbook is assigned to the settings API. Worth raising with the mentor rather
   than quietly absorbing it into another row.
4. No route changes a password — no admin reset and no self-service change. It
   matches row A06's wording, so it is not a defect, but it should be stated as a
   v1 limitation before A06 is implemented.
5. The review trail: #7-#11 have no GitHub review. State that honestly in the
   checklist, and use #12 to resume reviewing.
6. **F05 acceptance gap, still open and owned by Kavin.** The checklist's F05
   done-when is "ER diagram and migrations cover every database entity in the
   architecture"; pull request #4 delivered only an empty baseline and no ER
   diagram. The migration half is now complete for all ten tables, so only the
   diagram is outstanding — and it can now be drawn from real tables rather than
   from the picture.
7. The local-only checklist workbook is stale: F05 shows "In progress", and
   D01-D05 and F06 show "Not started". Update the statuses and evidence links
   after #12 merges, leaving F06 open until item 1 is decided.
8. Targets have slipped: F06 was due 12 October and D02-D05 were due 13-14
   October. Worth stating in the next mentor update.

## Exact next action

**Suhail reviews and merges pull request #12.** The decisions above are the ones
to push back on, especially item 2 in the decisions list (a migration that seeds
a row).

He then becomes Active owner of **D06 (Add knowledge article model)** on branch
`feat/D06-knowledge-articles`. D06's checklist done-when requires an article
**category**, which the contract does not currently define, so open item 1 is his
first decision and it must land in the contract, `DATA_MODEL.md`, and the tests
together. Kavin reviews D06. Keep every revision id to 32 characters or fewer, and
do not start D06 from an older remote state.

Kavin still owes the F05 ER diagram (open item 6) and should complete it before
or alongside the next review round.
