# Current handoff

Updated: 14 October 2026
Checklist task: D04 (Attachments and Audit Logs tables)
Branch: `feat/D04-attachments-audit`, off `main` at `0e25fcd`
Pull request: [#11](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/11) into `main`
Active owner: Kavin
Incoming owner: Suhail (reviewer for D04, and reviewer of the next row)

## Where the project stands

F01-F04 are on `main`. F05 merged as pull request #4 (`4a549ed`) and provides the
Alembic migration mechanism, with the ER-diagram part of its acceptance still
open (item 6 below). D01 merged as #5 (`1faf1b8`), F06 merged as #6 (`6bdc3c3`)
with its review recorded in the PR and in `docs/API_CONTRACT.md`, D02 merged as
#9 (`57a90e4`), and D03 merged as #10 (`0e25fcd`). Pull requests #7 and #8 were
documentation closeouts. `origin` carries only `main`.

**Since #6 there has been no review at all.** #7, #8, #9, and #10 were merged
without one, at Kavin's direction. The checklist evidence column should say that
rather than implying a review trail that does not exist. **The next row, D05, is
deliberately left open for review**, so the relay resumes with an actual reviewer.

D04 is this branch. The database now holds eight tables plus `alembic_version`:
`roles`, `users`, `categories`, `tickets`, `comments`, `ticket_history`,
`attachments`, `audit_logs`.

## Done in this handoff

- `backend/app/models/attachment.py` and `backend/app/models/audit_log.py`, both
  registered in `backend/app/models/__init__.py`.
- `backend/alembic/versions/20261014_d04_attachments_audit.py` is the new head,
  `down_revision = 20261014_d03_comments_history`, 30 characters.
- `backend/tests/test_attachments_audit_schema.py` exercises the real
  constraints in one rolled-back transaction: a valid attachment and a valid
  audit entry, a failed sign-in with no actor and no entity id, and rejection of a
  missing or dangling ticket, uploader, or actor, a blank or null file name or
  storage name, a null content type, a negative size, a duplicate storage name, a
  blank or null action or entity type, and the restrictive deletes. It also
  asserts the three new indexes exist and that neither table has `updated_at`.
- `backend/tests/test_migrations.py` now asserts `attachments` and `audit_logs`
  exist after reaching head.
- `docs/DATA_MODEL.md` gains a **D04 decisions** section and no longer lists the
  attachment storage layout or the audit-log index strategy as undecided.
- `README.md` reports the new head and the new models.

## Decisions worth reviewing

1. **Attachment storage layout.** Bytes live under `uploads/` at the repository
   root (already excluded by `.gitignore`, and outside anything the app serves),
   stored as `uploads/<first two characters of storage_name>/<storage_name>`.
   `storage_name` is a server-generated UUID4 in hex plus an extension chosen
   from the allowed types by MIME type; the client's file name is display-only.
   The table stores no directory part, so moving the root invalidates nothing.
2. `storage_name` is the one column the contract hides: the Attachment shape says
   the storage path is never returned, so it exists in the table and must be
   dropped from every response by T07.
3. Attachment rows are write-once (no `updated_at`, no update or delete route).
   `size_bytes >= 0` is the only size constraint, because the real limit is a
   configurable setting and the API enforces it.
4. **Audit-log index strategy**, the other F05 open question: `created_at` for the
   newest-first listing and `(entity_type, entity_id)` for one record's history.
   `actor_id` and `action` are unindexed by choice.
5. `old_value`/`new_value` are `JSONB`. `action` and `entity_type` have no closed
   set — G01 owns that vocabulary and the contract never fixes it.
6. `entity_id` has no foreign key because it identifies whatever `entity_type`
   names; `actor_id` does, and is nullable for a failed sign-in.

## Checks run

On Kavin's machine, against the containerised PostgreSQL, in this order.

- `docker compose ps` reports `itsm-helpdesk-db-1 ... Up (healthy)`.
- `alembic upgrade head` applied D04 on top of D03 with no error.
- `alembic current` reports `20261014_d04_attachments_audit (head)`.
- `alembic check` reports **No new upgrade operations detected**.
- `cd backend && pytest -q` reports **9 passed, 1 warning in 36.70s**. The warning
  is the pre-existing Starlette `TestClient` deprecation from F03/F04.
- Two of D04's own test cases were wrong on the first run and were fixed rather
  than deleted: an "invalid" row that was actually valid, and an empty
  `storage_name` that nothing rejected, which is why the column gained a
  not-blank check.
- Practical note carried forward: the WSL2 VM stops about a minute after the last
  WSL command, which kills Docker mid-run and fails every database test with a
  connection timeout. Hold an attached client for the whole run
  (`wsl -d Ubuntu -- sleep 900 &` in the same shell).

## Open items carried forward

1. **Article category**, still the one F06 item open. `docs/DATA_MODEL.md` and
   checklist row D06 both require a category on articles; the contract's
   `Article` shape omits it. Decide before D06 (owner Suhail, checklist target
   20 October) and update the contract, `DATA_MODEL.md`, and tests in one commit.
   Reusing `categories` is the cheapest option.
2. Two F06 wording items for the D06/D07 doc touch: `GET /articles` implies
   agents and admins see every draft while `GET /articles/{id}` returns a draft
   only to its author agent or an admin; and `PATCH /articles/{id}`'s "Who"
   column reads "Draft author or admin" while `REQUIREMENTS.md` says admins may
   edit any article.
3. No route changes a password — no admin reset and no self-service change. It
   matches checklist row A06's wording, so it is not a defect, but it should be
   stated as a v1 limitation before A06 is implemented.
4. **Who inserts the first `system_settings` row.** Migrations stay schema-only,
   so the SLA defaults and attachment limits in `REQUIREMENTS.md` need a home:
   either D05's API reads with defaults, or D08 seeds the row. T01 cannot compute
   a ticket's deadlines without it. D05 decides; the handoff records it either
   way.
5. The review trail: #7-#10 have no GitHub review. State that honestly in the
   checklist, and use the open D05 pull request to resume reviewing.
6. **F05 acceptance gap, still open and owned by Kavin.** The checklist's F05
   done-when is "ER diagram and migrations cover every database entity in the
   architecture"; pull request #4 delivered only an empty baseline and no ER
   diagram. The migration half now covers eight tables out of the ten the
   architecture names; the ER diagram is still missing.
7. The local-only checklist workbook is stale: F05 is "In progress", and D01-D04
   and F06 are still "Not started". Update statuses and evidence after this pull
   request merges, leaving F06 open until item 1 is decided.
8. Targets have slipped: F06 was due 12 October, D02-D05 were due 13-14 October.

## Exact next action

Merge pull request #11 (D04) — Kavin's direction is that only the last row before
Suhail's next owned row gets a review, and that is D05.

Then implement **D05 (Notifications and System Settings tables)** on branch
`feat/D05-notifications-settings`: checklist owner Kavin, reviewer Suhail.
D05 must decide the settings singleton question and item 4 above, and it owns the
remaining F05 open item list. Its pull request is **left open for Suhail to
review and merge** — do not self-merge it. After D05 merges, the next row is
**D06 (Knowledge article model)**, whose checklist owner is Suhail, so the relay
hands over there. Keep every revision id to 32 characters or fewer, and do not
start D05 from an older remote state.
