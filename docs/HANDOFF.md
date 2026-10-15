# Current handoff

Updated: 15 October 2026
Checklist task: D08 (Seed demo users and tickets)
Branch: `feat/D08-demo-seed`, based on `main` at `1bbb2ea`
Active owner: **Kavin** for review of D08 pull request
[#16](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/16). Suhail owns any
review fixes, then takes A01 and A02 after merge.

## Where the project stands

F01-F06 and D01-D07 are on `main`. The eleven application tables and F05 ER
diagram are present. D07 pull request
[#15](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/15) merged at `1bbb2ea`
after Kavin resolved its F05 documentation conflict. GitHub records **no
submitted review** on #15, even though Suhail was requested. F05 #14 and D02-D05
also lack recorded reviews. Do not claim those branches were reviewed; resume
the review step on D08.

## D08 change

- `python -m app.seed_demo` is an opt-in local setup command from `backend/`,
  after `alembic upgrade head`. It creates all three fixed roles if absent,
  one synthetic employee, support agent, and admin, three clearly named demo
  categories, and five tickets spanning Open, Assigned, In Progress, Resolved,
  and Closed. Ticket deadlines copy the current settings targets.
- Demo-owned users, categories, and tickets have stable UUIDs. Emails use the
  reserved `example.test` domain. The entire run commits once. On a repeat run,
  it adds only missing rows; it never changes existing passwords or tickets.
  An email/name/ID collision with an unrelated row fails instead of taking
  ownership of real data.
- The command prompts locally for one password shared by the three *new* demo
  accounts. No password or default credential is committed. The salted
  PBKDF2-SHA256 hash and verifier live in `app/core/passwords.py`; A01/A02 must
  use the verifier for seeded accounts or explicitly migrate the format.
- These tickets are synthetic snapshots, not simulated API actions. D08 does
  not fabricate ticket history or audit entries. T01/T02 and G01 will write
  those for real actions.
- Added `backend/tests/test_demo_seed.py`, plus setup guidance in `README.md`
  and rationale in `docs/DATA_MODEL.md`. No schema or migration changed.

## Checks

On Suhail's Mac, the existing `itsm-helpdesk-d01` Postgres container uses port
5433. It was at the D01 migration, so `alembic upgrade head` brought the local
development database to D06. That was setup, not a repository change. The
full suite initially found the pre-existing D07 relationship test assumed an
already-migrated database; after the required setup:

- `backend/.venv/bin/pytest -q backend/tests`: **25 passed, 1 warning**. The
  warning is the pre-existing Starlette TestClient deprecation.
- D08's database test creates a unique test-only seed inside an outer
  transaction, runs the seed twice, checks every role and ticket status,
  verifies password hashes, proves no duplicates or resets, then rolls back.
  It leaves **no demo users or tickets** in the development database.
- Seven database-free tests passed separately. `compileall` and `git diff --check`
  passed. No demo password was printed or stored in Git.

## Open items

1. Kavin reviews D08, particularly whether one locally entered password for
   all demo accounts is acceptable for the internship demo. After approval,
   merge the PR; both pull `main` before A01 begins.
2. A01 owns login and must verify D08's password format. A02 owns token/session
   rules. Neither exists yet, so demo accounts cannot sign in today.
3. No checklist row owns `GET /settings` and `PATCH /settings`; ask the mentor
   which row should implement them.
4. No password-change/reset route is in the v1 contract; state this limitation
   before A06.
5. The separately maintained checklist workbook still has stale statuses and
   needs evidence links after merge. Keep review evidence honest.
6. Kavin's Windows/WSL database may stop when idle; his D07 handoff documented
   the `instanceIdleTimeout` setting. On Suhail's Mac, start only the existing
   local Postgres container when database tests are needed, then stop it.

## Exact next action

The implementation was pushed as `039a9f9`; D08 PR
[#16](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/16) is open and Kavin
was requested as reviewer. **Kavin reviews it** and leaves a GitHub review or
actionable comments. Suhail responds to changes if needed; merge only after
review. Next active implementation row for Suhail
is A01 (Password storage and login API), followed by A02 (JWT validation and
session rules). Read `AGENTS.md`, `WORKFLOW.md`, `REQUIREMENTS.md`, and
`API_CONTRACT.md`, then check branch, status, commit, and remote before editing.
