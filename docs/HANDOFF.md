# Current handoff

Updated: 16 October 2026
Checklist rows: **T07, S01, G01** implemented; **G03, G04, G05, G07** advanced
as far as the implemented API allows, with the limits stated below.
Branch: `feat/T07-S01-G01-support-api`, based on `main` at `2b603c2`
Active owner: **Kavin**, with pull request
[#20](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/20) open against `main`
and Suhail requested as reviewer. Only one person codes at a time; Kavin makes
any review fixes.

## Where the project stands

F01–F06, D01–D08, A01–A07, T01–T04, T05, and T06 are on `main`. The ticket core
merged as `b120441` and category management (T05) as `2b603c2`, both on
15 October; Suhail reviewed neither pull request through GitHub's review
mechanism — #18 was merged without a submitted review and #19 was approved by
Kavin before merge.

Every route in `API_CONTRACT.md` is now implemented except the knowledge-base
articles, dashboards, reports, and the settings pair. Suhail's unstarted rows are
T08–T10 (ticket screens), S02 (notification display), S03/S04 (knowledge base),
S05 (live updates), R01–R05 (reporting), G02 (admin settings and audit screens),
G06 (end-to-end journey), and G08 (final demo).

## What this branch adds

**T07 — attachments.** `app/core/storage.py` holds the bytes on local disk and
`app/api/v1/attachments.py` exposes the three contract routes: list, multipart
upload as `file`, and download. `GET` reuses `visible_ticket_or_404`, so any
agent or admin may read while only the ticket's creator, its assigned agent, or
an admin may add a file; an `attachment_id` from another ticket is a `404`. The
storage name is a bare `uuid4` hex string generated server-side, the client's
name is reduced to its final path component and used only for display, and
`storage_path` re-checks that a resolved row still lands directly inside the
upload root. Type and size come from the singleton settings row, so
`PATCH /settings` will apply to the next upload without a code change. The file
is written before the row commits and unlinked again if the commit fails.

**S01 — notifications.** `app/api/v1/notifications.py` adds the list route
(`include_dismissed`, `unread_only`, newest first) and the two owner-only
`read`/`dismiss` routes. Read and dismissed stay independent, marking either twice
keeps the first timestamp, and dismissing is not a delete. Everything is scoped
to `recipient_id == current_user.id`, so another person's notification is a `404`
rather than a `403`. Neither action writes history or an audit entry, because
`REQUIREMENTS.md` calls them personal UI state. The write side was already
merged in T01–T06 and is now covered by tests asserting that assignment and
comment really do produce the rows these routes read.

**G01 — audit reads.** `app/api/v1/audit_logs.py` adds the admin-only
`GET /audit-logs` with the contract's filters (`actor_id`, `action`,
`entity_type`, `entity_id`, `created_from`, `created_to`), newest first. An
unknown `action` is a valid query that matches nothing, not a `422`, because the
contract names the vocabulary without fixing it. Tests drive real actions and
read them back: `login_success`, `login_failure` (null actor, attempted address
only), `user_create`, `user_update` with old and new values, `ticket_create`, and
`ticket_update`. A no-op edit still writes nothing.

**G03 — `/docs`.** Every router now has a tag, every route a summary, and the app
description explains the bearer token, the permission model, the shared error
codes, and pagination. `tests/test_openapi_docs.py` is the executable half: it
fails if a route lacks a summary or a tag, if a non-public route does not
declare the bearer scheme, if a response shape drifts from the contract, if a
paginated route loses `limit`/`offset`, or if any `DELETE` route appears.

**G04 — Postman.** `docs/postman/` holds a 57-request collection in nine ordered
folders (health, auth, users, categories, tickets, attachments, notifications,
audit logs, error cases) that chains ids and tokens through collection variables
and asserts the documented status codes, plus a short README on how to run it.

**G05 — tests.** The suite went from 48 to 77 tests. It now covers attachments
(permissions, type and size limits, path-traversal names, disk round trip,
missing file, isolation between tickets) and notifications and audit reads
alongside the existing permissions, lifecycle, SLA, filter, and transactional
side-effect coverage.

**G07 — startup guide.** `README.md` gains a copy-paste quick start from clone to
a signed-in UI, the new `UPLOAD_DIR` setting, an attachments-on-disk section, an
updated implemented-route summary, and refreshed structure and verify tables.

Supporting changes: `requirements.txt` gains `python-multipart>=0.0.18`, which
FastAPI needs to parse the multipart upload at all; `.env.example` documents
`UPLOAD_DIR`; `app/core/config.py` gains `upload_dir`/`upload_root`, defaulting
to the gitignored `var/uploads` beside the repository root.

`docs/API_CONTRACT.md` changed only its "what is implemented" paragraph — no
route, shape, rule, or error code was changed.

## Row status: what is finished and what is not

- **T07, S01, G01** are implemented and tested. They are the reviewable part of
  this pull request.
- **G03** is done for the implemented API only. It has to be re-checked as
  articles, reports, and settings land, because the guard test can only assert
  what exists.
- **G04** covers only implemented routes. The reports, articles, and settings
  folders can be added only when those routes exist, so the row is not Done.
- **G05** is not Done. Its own done-when names report totals, and there is no
  reports API yet. Everything it can cover today is covered.
- **G07** is done as far as the implemented routes go.

None of the seven rows is marked Done in the checklist.

## Checks

- Full backend suite: **77 passed, 1 warning**. The warning is the pre-existing
  Starlette `TestClient` deprecation. The suite was 48 tests before this branch.
- `alembic check`: **No new upgrade operations detected**; `alembic current` is
  `20261015_a02_refresh_tokens (head)`. This branch adds no migration, table, or
  column: T07 reuses D04's `attachments`, S01 D05's `notifications`, and G01
  D04's `audit_logs`.
- `git diff --check`: clean.
- The development database was left with zero rows, and no `var/uploads`
  directory was created: the tests run against real PostgreSQL inside one outer
  transaction that is rolled back, and the attachment tests point `UPLOAD_DIR` at
  pytest's `tmp_path`.
- OpenAPI: 28 operations, every one summarised, tagged, and carrying the bearer
  scheme, with only `GET /health`, `POST /auth/login`, and `POST /auth/refresh`
  public.
- Local environment note, not a code change: this machine's `backend/.venv` was
  missing `PyJWT`, which `requirements.txt` already declared, so it was
  reinstalled before the suite could run. A fresh
  `pip install -r requirements.txt` includes both it and `python-multipart`.

## Open items carried forward

New in this branch, needing a decision rather than a fix:

- `GET /tickets/{id}/attachments` is ordered newest first. The contract does not
  say, unlike the comment and history routes, so the frontend has nothing agreed
  to follow. Either the contract gains the sentence or this row changes.
- A missing settings row makes uploads answer `503`, mirroring the existing SLA
  `503` in ticket creation. Neither `503` appears in the contract's error column
  for those routes, so the contract and the code disagree in the same way in two
  places.
- The attachment type is the one the client declares in the multipart part,
  matched against the settings list; the bytes are not sniffed. That is why a
  `.zip` renamed to `.txt` would still be accepted, and it is stated in the
  README rather than hidden.
- No notification is created for an attachment upload, and no audit entry for an
  attachment upload or a category change. Both follow the agreed trigger and
  audit lists in `REQUIREMENTS.md`; raising it here in case the team wants either
  list widened.

Still open from before:

- Kavin's #17 review left five non-blocking follow-ups: refresh-token reuse and
  family revocation, no pruning of expired refresh tokens, the untested
  demote-last-admin branch, `503` missing from the login contract row, and the
  OpenAPI `422` documentation mismatch.
- Kavin's #19 review left four: the active-only `GET /categories` leaves an admin
  unable to discover an inactive category's id, so reactivation needs a known id
  and wants a recorded decision; the F06 bullet files "duplicate name or email"
  under `400` while the route tables say `409`; nothing prevents deactivating the
  last active category; and the `schemas.py` docstring (now corrected here) had
  narrowed its scope.
- No checklist row owns `GET /settings` and `PATCH /settings`. This is now the
  only unimplemented pair with no obvious owner, and G01's `settings_update`
  audit action cannot exist until it does.
- The mentor-updates sheet is due on Mondays, Wednesdays, and Fridays; the
  entries from 2026-10-07 onward are still marked not sent.

## Review focus and exact next action

Suhail reviews pull request
[#20](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/20) for T07's
authorization and path handling, S01's read/dismiss independence and ownership
scoping, and G01's filters and admin-only guard. He should also confirm the two
contract questions raised above (attachment list ordering, and `503` for missing
settings) and say whether the G03/G04/G05/G07 partial state is acceptable as
recorded, rather than being split into their own rows.

Kavin makes any review fixes. After merge, both pull `main` before starting the
next branch. The next unclaimed work is Suhail's T08 (ticket list, search, and
filters); Kavin's next row after this one is G05's remaining report coverage,
which is blocked until R01–R05 exist.

On another computer, read `AGENTS.md`, `docs/WORKFLOW.md`, `docs/REQUIREMENTS.md`,
and `docs/API_CONTRACT.md`, then check branch, status, commit, and remote before
editing. No secrets, real user data, or local-only `reference/` files belong in
Git.
