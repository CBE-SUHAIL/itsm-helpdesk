# Current handoff

Updated: 17 October 2026
Owner: Suhail, final-completion branch `feat/final-itsm-completion`
Base: `origin/main` at `f75892d` (Kavin's T07/S01/G01 work is merged)

## What is ready for review

The final branch completes the remaining UI and API layers in one pull request:

- T08–T10: role-aware ticket queue, search/filter/paging, employee creation,
  ticket detail, assignment, priority/category changes, comments, attachments,
  status transitions, and history.
- S02–S05: notification inbox with read/dismiss controls, knowledge-base
  draft/search/publish flows, and 15-second polling of live views.
- R01–R05: role-scoped dashboard counts, overdue and workload metrics,
  filtered CSV/PDF ticket reports, and the report screen.
- G02–G08: admin settings/categories/audit screens, OpenAPI coverage, expanded
  Postman collection, 83 backend tests including an employee-agent-admin
  journey, README/setup guidance, and a final demo script.

New API routes are `/articles`, `/articles/{id}`,
`/articles/{id}/publish`, `/dashboard/summary`, `/reports/tickets`, and
`/settings`. The existing ticket list accepts `q` search, and admins may list
inactive categories for reactivation. No new table or migration is needed:
these routes use Kavin's merged schema and the agreed API contract.

## Important behavior and boundaries

- Each laptop runs its own `.env`, PostgreSQL container, demo seed, and upload
  directory. Git carries code and documentation only, not local data or
  credentials. Kavin can pull `main` after this PR merges and run the README
  Quick start without this machine's state.
- Ticket and notification screens poll every 15 seconds. The notification
  inbox checks for elapsed SLA deadlines and creates one breach alert per
  ticket and recipient under a PostgreSQL transaction lock. Because the app
  has no cloud worker, a breach alert is delivered at the next inbox request,
  not while the app is shut down. Dashboard/report overdue counts always use
  the current deadline and timestamp directly.
- The employee sees own tickets and published articles; agents see the support
  queue and their drafts; admins see all articles and settings/audit tools.
  These restrictions are enforced by the API as well as the UI.
- The admin category list includes inactive rows; deactivating the last active
  category is allowed and pauses new intake until one is restored.
- A locally served Vite development app proxies `/api` to FastAPI. A separate
  static production deployment would need its own reverse proxy/base URL
  configuration; this project promises local deployment only.

## Verification

- Backend: `83 passed, 1 warning` (`StarletteDeprecationWarning` from the
  installed FastAPI TestClient dependency). `python run_tests.py -q` runs in
  a fresh random PostgreSQL database and removes only that database afterward.
  This matters after `seed_demo`: several pre-existing tests assume an empty
  database, so bare `pytest` can fail against the developer's demo database.
- Frontend: `npm run build` and `npm run lint` pass.
- Alembic: `No new upgrade operations detected`.
- Postman collection JSON parses. Folder 09 exercises the final routes.
- End-to-end API test covers create → assign → start → comment → resolve →
  notify → close → report/audit. The presentation path is in `docs/DEMO.md`.
- Browser smoke test: seeded employee login, dashboard, ticket list, and ticket
  detail rendered; the browser reported no warnings or errors. This checkout's
  local `.env` has no JWT secret, so the first login correctly returned 503.
  The test server was restarted with a temporary process-only demo key to
  finish verification. Set your own `JWT_SECRET` in `.env` before normal use.

## Review and next action

Kavin should review the single final-completion pull request, particularly
role permissions, export scoping, the request-driven SLA notification behavior,
and the ticket UI flow. After merge, both developers pull the same `main`
before any further work. No additional task-specific PRs are planned.

For a second machine: read `AGENTS.md`, this handoff, `docs/WORKFLOW.md`,
`docs/REQUIREMENTS.md`, and `docs/API_CONTRACT.md`; inspect branch/status and
remote before editing. Never commit `.env`, local uploads, real employee data,
or files under the project mirror's `sources/` directory.
