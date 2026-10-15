# Current handoff

Updated: 15 October 2026
Checklist tasks: T01–T04 and T06 (ticket core APIs)
Branch: `feat/T01-T07-S01-G01-support-api`, based on `main` at `88eb827`
Active owner: **Kavin**, with pull request
[#18](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/18) open against `main`
and Suhail requested as reviewer. Only one person codes at a time; Suhail makes
review fixes if any are needed.

## Where the project stands

F01–F06 and D01–D08 are on `main`, and A01–A07 merged as `88eb827` after Kavin
approved pull request [#17](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/17).
The only implemented endpoints are health, auth, users, and now the ticket core
in this branch.

Suhail's next checklist row is **T05, the category management API**. It is
unstarted, has no branch, and is deliberately **not** in this pull request:
`GET`, `POST`, and `PATCH /categories` remain planned in `API_CONTRACT.md`. The
categories a ticket can be filed under therefore come only from the D08 demo
seed until T05 lands. `POST /tickets` works against those seeded rows.

Kavin's remaining rows — T07 (attachments), S01 (notification API), G01
(audit-log API), G03, G04, G05, and G07 — are not started either. Two of them
are already unblocked by this branch: `app/core/notify.py` and `app/core/audit.py`
hold the write side that S01 and G01 need.

The workflow normally uses one branch per checklist row. Kavin and Suhail
agreed to batch the remaining Kavin rows onto one branch and one pull request,
the same way A01–A07 was handled, so this branch stays open and keeps receiving
commits until that set is done.

## What this branch adds

- **T01** — `GET /tickets` (filtered by `status`, `priority`, `category_id`,
  `assignee_id`, `created_from`, `created_to`, newest first), `POST /tickets`,
  and `GET /tickets/{id}`. An employee is scoped to their own tickets before
  any filter is applied, and another employee's ID answers `404` rather than
  `403` so tickets cannot be probed for existence.
- **T02** — `POST /tickets/{id}/status`. `Open → Assigned → In Progress →
  Resolved → Closed`. Only the assigned agent starts or resolves work; only the
  ticket's creator (the employee who raised it, not the assigned agent) or an
  admin closes. `Resolved` requires a nonblank `resolution_note`, kept on the
  history row as `reason`, and resuming a `Resolved` ticket clears `resolved_at`.
- **T03** — `POST /tickets/{id}/assignment`. An agent self-assigns an
  unassigned `Open` ticket; an admin reassigns or unassigns. A null assignee is
  admin-only and moves `Assigned`/`In Progress` back to `Open`. An assignee who
  is unknown, inactive, or not an agent is a `400`.
- **T04** — `POST /tickets/{id}/priority` with a required nonblank reason, plus
  the SLA helpers in `app/core/sla.py`. Deadlines are copied onto the ticket at
  creation and recomputed from the original `created_at` when the priority
  changes, because priority is what determines them. `response_overdue` and
  `resolution_overdue` are derived at read time and stay visible once breached.
- **T06** — `GET`/`POST /tickets/{id}/comments` and `GET /tickets/{id}/history`,
  both oldest first. The first comment from the assigned agent also records
  `first_response_at`.

Supporting modules: `app/core/sla.py` (deadlines and the overdue rules),
`app/core/audit.py` (`record_audit`, append-only, same transaction), and
`app/core/notify.py` (`notify` and `notify_admins`, same transaction). Ticket
changes are transactional end to end: the ticket, one history row per changed
field, one audit entry, and the relevant notifications commit or roll back
together, and a request that changes nothing writes neither history nor audit.

`docs/API_CONTRACT.md` had its "what is implemented" paragraph updated to name
the ticket routes; no route, shape, or rule in it was changed.

## Checks

- Full backend suite on this machine: **45 passed, 1 warning**. The warning is
  the pre-existing Starlette `TestClient` deprecation.
- `alembic check`: **No new upgrade operations detected**. This branch adds no
  migration, table, or column.
- New file `backend/tests/test_tickets_api.py` has 15 tests covering
  permissions, transitions, SLA boundary arithmetic, list filters, pagination,
  and the transactional side effects.
- The development database was left with zero tickets, history, comments,
  notifications, audit entries, categories, and users, so the tests leave no
  residue. The suite runs against real PostgreSQL inside one outer transaction
  that is rolled back.
- No secrets, no real user data, and nothing from the local-only `reference/`
  folder is committed. `git status` on `main` is clean.

## Open items carried forward

- Kavin's review of [#17](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/17)
  left five non-blocking follow-ups that are still open: refresh-token reuse and
  family revocation, no pruning of expired refresh tokens, the untested
  demote-last-admin branch, `503` missing from the login contract row, and the
  OpenAPI `422` documentation mismatch.
- No checklist row owns `GET /settings` and `PATCH /settings`; that needs a
  decision.
- The mentor-updates sheet is due on Mondays, Wednesdays, and Fridays. The
  entries from 2026-10-07 onward are still marked not sent.

## Review focus and exact next action

Suhail reviews pull request
[#18](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/18) as it stands, for the
`404`-instead-of-`403` choice on other employees' ticket IDs, for whether the
notification triggers match what S01 will need, and for whether
`POST /tickets/{id}/category` belongs with T05 instead of here. He leaves a
GitHub review or actionable comments, and Kavin makes any review fixes.

By agreement this pull request stays **open and unmerged** and keeps
accumulating Kavin's remaining rows — T07, S01, G01, G03, G04, G05, and G07 —
so that all of them land under one branch and one review. It merges once that
set is complete and reviewed. That is a deliberate departure from the usual one
branch per row; A01–A07 was batched the same way.

Kavin is paused here, at Suhail's next checklist row. Suhail becomes active
owner for **T05**, the category management API, on a new branch taken from
`main`. T05 also edits `backend/app/api/v1/schemas.py`, which this branch
changes, so expect a merge in that file when #18 eventually lands.

On another computer, read `AGENTS.md`, `WORKFLOW.md`, `REQUIREMENTS.md`, and
`API_CONTRACT.md`, then check branch, status, commit, and remote before editing.
