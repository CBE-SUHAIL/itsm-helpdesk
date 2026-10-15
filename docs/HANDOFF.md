# Current handoff

Updated: 15 October 2026
Checklist row: **T05 — category management API**
Branch: `feat/T05-categories-api`, based on `main` at `b120441`
Active owner: **Suhail** until T05 is pushed for Kavin's review. Only one person
codes at a time; Kavin reviews this branch after the pull request is opened.

## Where the project stands

F01–F06, D01–D08, A01–A07, and T01–T04/T06 are on `main`. Kavin's ticket-core
pull request [#18](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/18) merged as
`b120441` on 15 October, despite the preceding handoff's plan to leave it open
for more Kavin rows. T07, S01, G01, G03, G04, G05, and G07 remain unstarted.
The ticket-core write helpers `app/core/notify.py` and `app/core/audit.py` are
available for S01 and G01. `POST /tickets/{id}/category` was included in the
ticket-core merge; T05 adds the category *management* routes, not that route.

## T05 implementation

- `GET /api/v1/categories` requires login, returns only active categories,
  sorted by name and ID, with the contract's `{items, total}` pagination.
- `POST /api/v1/categories` is admin-only, creates an active category, and
  returns all six `Category` fields. A name is trimmed, must not be blank, and
  duplicate names return `409`. Description is required but may be empty.
- `PATCH /api/v1/categories/{id}` is admin-only and accepts a nonempty subset of
  `name`, `description`, and `is_active`. It can deactivate or reactivate without
  deleting rows, so existing tickets and articles retain their category link.
  Missing IDs return `404`, duplicate names `409`, invalid shapes `422`.
- The existing category table already has the needed fields; T05 adds no
  migration, new table, or column. No category audit entry is required by the
  agreed audit list in `docs/REQUIREMENTS.md`.

## Checks and open points

- New `backend/tests/test_categories_api.py` checks roles, active-only listing,
  paging, validation, duplicate handling, edit/deactivation/reactivation, and
  the effect of deactivation on existing versus new tickets.
- Full backend suite on Suhail's Mac: **48 passed, 1 warning**. The warning is
  the pre-existing Starlette TestClient deprecation. Tests use an outer
  rollback transaction, so no T05 test rows persist.
- `alembic check`: **No new upgrade operations detected**.
- `GET /categories` is active-only even for admins, as `API_CONTRACT.md`
  specifies. An admin therefore needs a previously known category ID to
  reactivate an inactive category; a future reviewed contract change could add
  an admin-only inactive-list option. This is not silently added in T05.
- Kavin's #17 review left non-blocking follow-ups: refresh-token reuse/family
  revocation, pruning expired tokens, a missing last-admin-demotion test,
  login `503` contract documentation, and OpenAPI `422` documentation.
- No checklist row owns `GET /settings` or `PATCH /settings`; assignment still
  needs a team decision. Mentor update entries from 2026-10-07 onward were
  marked not sent in the preceding handoff and have not been changed here.

## Exact next action

Suhail pushes T05 and opens one pull request into `main`, requesting Kavin's
review. Kavin checks permissions, validation, active-only filtering, and whether
the contract should later expose inactive categories to admins. Suhail handles
review fixes; merge only after review. Both update `main` before another task.

On another computer, read `AGENTS.md`, `docs/WORKFLOW.md`,
`docs/REQUIREMENTS.md`, and `docs/API_CONTRACT.md`, then check branch, status,
commit, and remote before editing. No secrets or local-only reference files
belong in Git.
