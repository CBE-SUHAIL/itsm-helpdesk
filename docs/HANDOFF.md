# Current handoff

Updated: 14 October 2026
Checklist task: F05 (Define database schema and migrations) — its outstanding
acceptance item, the ER diagram
Branch: `docs/F05-er-diagram`, based on `main` at `ec5c63a`
Pull request: [#14](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/14) into
`main`, with Suhail requested as reviewer
Active owner: **Kavin** on this branch. Incoming owner: **Suhail** reviews and
merges, then takes the next row.

## Where the project stands

F01-F04 and D01-D06 are on `main`. D06 pull request
[#13](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/13) was **reviewed and
approved by Kavin on GitHub** and merged as `ec5c63a`, which is the first
recorded GitHub review approval since #6; the F06 article-category gap is closed
with it. D05 (#12) and D02-D04 were merged without a recorded GitHub review and
must still be described that way rather than as reviewed.

F05's migration mechanism has been on `main` since #4, but its **ER diagram was
never drawn**, which is why the row is still In progress. That is what this
branch does. The database now holds all eleven tables: the ten in the mentor
workbook's database layer plus `knowledge_articles` from D06.

## F05 change

- `docs/DATA_MODEL.md` gains an **ER diagram** section: a Mermaid `erDiagram`
  of all eleven tables with every column, its type, and its PK/FK/UK marker, and
  all fifteen restrictive foreign keys as relationship lines. Nullable pointers
  (`tickets.assignee_id`, `audit_logs.actor_id`, `notifications.ticket_id`) are
  drawn `|o`, so the diagram states which links are optional rather than leaving
  it to prose.
- `alembic_version` is deliberately not drawn; it is Alembic's table, not part of
  the model. `refresh_tokens` must be added to the diagram in the same commit
  that A01/A02 adds it.
- `backend/tests/test_er_diagram.py` is new. It parses that block and compares it
  with `Base.metadata`: every table, every column, every PK/FK/UK marker, every
  foreign key, and the nullable/required shape of each link. It needs **no
  database**, so unlike the rest of the suite it still runs with Postgres down.

## Checks

- `pytest -q backend/tests`: **16 passed, 1 warning**. The warning is the
  pre-existing Starlette `TestClient` deprecation. This is the first full-suite
  run on Kavin's machine, so it also re-verifies D06's schema and migration tests
  after the merge.
- The guard was verified in both directions, not just green: deleting a column,
  deleting a relationship line, and flipping a nullable `|o` to `||` each made
  the relevant test fail, and the file was restored afterwards.
- The diagram was parsed with **Mermaid's own parser** (mermaid 11 + jsdom in a
  scratch directory): `PARSE OK`, `diagramType: "er"`, 11 entities, 15
  relationships. So it renders on GitHub rather than only looking plausible.
- The local database was upgraded from D05 to head
  (`20261014_d06_knowledge_articles`).
- `git diff --check` and `compileall` passed.

### Making the database reachable, recorded because it cost an afternoon

The suite first failed on this machine wholesale, with psycopg connection
timeouts on every database-backed test. The cause was not the schema and not this
branch. `.wslconfig` sets `networkingMode=mirrored`, and WSL shuts an idle distro
(or VM) down after `instanceIdleTimeout`, whose default is **15 seconds**. With no
interactive WSL session open, the distro stopped between test files, so
`localhost:5432` stopped answering part-way through a run. That is also why a raw
TCP connect could succeed while the Postgres handshake timed out: the listener
disappeared mid-conversation.

`[wsl2] vmIdleTimeout` does **not** help: the WSL documentation restricts it to
`networkingMode=NAT`. The working setting is `[general] instanceIdleTimeout`.
`~/.wslconfig` now carries `instanceIdleTimeout=43200000` (12 hours), and WSL was
restarted with `wsl --shutdown`. The previous file is at
`~/.wslconfig.backup-20261014-234804`; `-1` disables auto-shutdown entirely if a
12-hour window is not wanted. Verify with `wsl -l -v` showing `Running` and
`pytest -q backend/tests` passing.

## Open items

1. No checklist row owns `GET /settings` and `PATCH /settings`; ask the mentor
   which task should implement them rather than silently expanding D05.
2. No route changes or resets a password in v1; make this explicit before A06.
3. The separately maintained local checklist workbook still has stale statuses
   (D02-D05 still read "Not started") and needs evidence links. Do not mark
   unreviewed pull requests as reviewed.
4. The ER-diagram guard only covers the diagram. A later row that adds a table
   will fail `test_er_diagram.py` until the diagram is redrawn, which is the
   intent, so redraw rather than relax the test.
5. `instanceIdleTimeout` keeps the WSL VM resident for 12 hours. With
   `autoMemoryReclaim=disabled` in the same file, that holds memory the VM has
   claimed until it stops. Use `wsl --shutdown` when finished for the day if that
   matters.

## Exact next action

**Suhail reviews this branch.** Check that the diagram agrees with the models he
reviewed, that drawing eleven tables rather than the workbook's ten is the right
reading of F05's done-when, and whether a `docs/` branch is the right place for a
tooling test. Then merge, pull `main`, and start **D07 (models, relationships, and
session handling)**, which is Kavin's next row and which the diagram's
relationship section now describes. The database is reachable again, so D07's
acceptance, transactions committing and rolling back against a live database, is
testable on this machine.

The incoming coder reads this file, `AGENTS.md`, `WORKFLOW.md`,
`REQUIREMENTS.md`, and `API_CONTRACT.md`, then checks branch, status, commit,
and remote before editing. Do not code from a stale checkout.
