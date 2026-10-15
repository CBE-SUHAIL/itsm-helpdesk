# Current handoff

Updated: 15 October 2026
Checklist tasks: A01–A07 (authentication, permissions, and user administration)
Branch: `feat/A01-A07-auth-admin`, based on `main` after D08 merge `5ff2239`
Active owner: **Kavin** for review of combined A01–A07 pull request
[#17](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/17). Only one person
codes at a time; Suhail handles any review fixes after Kavin leaves comments.

## Where the project stands

F01–F06 and D01–D08 are on `main`. Kavin approved D08 pull request
[#16](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/16), which merged as
`5ff2239`. His condition that real user creation hash each user's own password
is met by `POST /users`. His non-blocking request to test demo-seed collision
handling is covered by `test_demo_seed_refuses_to_claim_an_unrelated_category`.
The repository workflow normally uses one branch and PR per task, but Suhail
explicitly chose one review request for all seven A-tasks here.

## A01–A07 implementation

- A01: `POST /auth/login` checks D08-compatible PBKDF2 password hashes, returns
  an access token and a refresh token, and writes success/failure audit records.
  Failed login messages do not reveal whether the email exists. `POST /users`
  hashes the password supplied for that individual account.
- A02: HS256 access JWTs last 30 minutes; random refresh tokens last seven
  days, are stored only as SHA-256 digests in the new `refresh_tokens` table,
  rotate on refresh, and revoke on logout. Invalid, expired, and revoked tokens
  fail. Each machine needs its own `JWT_SECRET` in `.env`; no signing key is
  committed. Access tokens already issued can survive logout until expiry.
- A03: Shared backend `current_user` and `require_roles` dependencies protect
  every currently implemented non-public route. Admin user routes reject
  employee and agent tokens. Role changes invalidate old access tokens. Later
  ticket/support routes must use these dependencies too.
- A04: React sign-in, in-memory access token, persisted local-demo refresh
  token, session restore after reload, automatic refresh, and sign-out.
- A05: React gates current pages by role. Admin-only navigation and direct
  `/admin/users` URL both block employee/agent accounts. Future ticket/report
  screens are intentionally not presented as implemented.
- A06: Admin can list/filter/page users, create users, edit name or role, and
  deactivate/reactivate. No hard delete or public registration. Changes are
  audited. The last active admin cannot be deactivated or demoted.
- A07: React admin Users page exposes the matching create/edit/deactivate
  controls. It never displays a password hash.

The only implemented business endpoints so far are health, auth, and users;
the rest of `API_CONTRACT.md` remains planned. A01–A07 do not implement password
reset/change, ticket management, categories, reports, or settings.

## Checks and local environment

- Full backend suite on Suhail's Mac: **30 passed, 1 warning**. The warning is
  the pre-existing Starlette TestClient deprecation.
- `alembic check`: **No new upgrade operations detected** against the A02
  migration, after upgrading the local dev database to head.
- `npm run build` and `npm run lint`: both pass without warnings.
- Safari local-flow check: sign-in reached the admin workspace and user list;
  add-user form opened; employee navigation hid Users and a direct admin URL
  showed Access Restricted; reload restored the employee session; sign-out
  returned to login. API tests exercise user creation/edit/deactivation and
  refresh/logout. Browser form submission was not used to change credentials.
- Temporary browser-check accounts, tickets, categories, tokens, logs, and
  three unreferenced roles were removed. Verified the local dev database has
  zero roles, users, tickets, and categories afterward. Backend, Vite,
  PostgreSQL container, and Docker Desktop were stopped after verification.

## Review focus and exact next action

Kavin reviews the combined branch for API-contract shapes, token/session
behavior, audit safety, and frontend role gates. In particular, check the
local-storage refresh-token choice: it supports seven-day demo session restore
but would need a stronger browser storage design before real employee data is
used. Also confirm that future routes apply `require_roles` appropriately;
A03 cannot protect routes that do not exist yet.

Implementation commit `ca9bb8b` and handoff commit `fd6b221` were pushed.
PR [#17](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/17) is open against
`main`, and Kavin was requested as reviewer. Kavin submits a GitHub review or
actionable comments. Suhail makes review fixes if
needed; merge only after review. Both pull `main` before starting the next
checklist row. On another computer, read `AGENTS.md`, `WORKFLOW.md`,
`REQUIREMENTS.md`, and `API_CONTRACT.md`, then check branch, status, commit,
and remote before editing.
