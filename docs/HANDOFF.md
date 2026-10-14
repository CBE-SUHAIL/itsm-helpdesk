# Current handoff

Updated: 14 October 2026
Checklist task: F05 (Define database schema and migrations) — its outstanding
acceptance item, the ER diagram
Branch: `docs/F05-er-diagram`, based on `main` at `ec5c63a`
Pull request: *link added in the next commit*
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

- `pytest -q tests/test_er_diagram.py`: **4 passed**.
- The guard was verified in both directions, not just green: deleting a column,
  deleting a relationship line, and flipping a nullable `|o` to `||` each made
  the relevant test fail, and the file was restored afterwards.
- The diagram was parsed with **Mermaid's own parser** (mermaid 11 + jsdom in a
  scratch directory): `PARSE OK`, `diagramType: "er"`, 11 entities, 15
  relationships. So it renders on GitHub rather than only looking plausible.
- **The rest of the suite could not be run on this machine.** Postgres is
  unreachable from Windows here: the container is up and healthy inside WSL
  (answering on 127.0.0.1:5432 there), but Windows sees no listener on 5432 and
  psycopg times out. All 9 database-backed tests fail identically on `main`
  before this branch, so this is a local environment fault, not a code change.
  See open item 1.
- The local database is still at revision `20261014_d05_notify_settings`; run
  `alembic upgrade head` to reach D06 before running the schema tests.

## Open items

1. **Windows cannot reach the project's Postgres.** `.wslconfig` sets
   `networkingMode=mirrored` (for the separate Kubernetes assignment), which
   stops Docker's published port being mirrored to Windows. Fixing it means
   editing that personal file and `wsl --shutdown`, or running the backend from
   inside WSL; neither was done unasked. Everything DB-backed is unverified on
   this machine until it is resolved.
2. No checklist row owns `GET /settings` and `PATCH /settings`; ask the mentor
   which task should implement them rather than silently expanding D05.
3. No route changes or resets a password in v1; make this explicit before A06.
4. The separately maintained local checklist workbook still has stale statuses
   (D02-D05 still read "Not started") and needs evidence links. Do not mark
   unreviewed pull requests as reviewed.
5. The ER-diagram guard only covers the diagram. A later row that adds a table
   will fail `test_er_diagram.py` until the diagram is redrawn, which is the
   intent, so redraw rather than relax the test.

## Exact next action

**Suhail reviews this branch.** Check that the diagram agrees with the models he
reviewed, that drawing eleven tables rather than the workbook's ten is the right
reading of F05's done-when, and whether a `docs/` branch is the right place for a
tooling test. Then merge, pull `main`, and start **D07 (models, relationships, and
session handling)**, which is Kavin's next row and which the diagram's
relationship section now describes. Resolve open item 1 first: D07's acceptance
depends on transactions committing and rolling back against a live database.

The incoming coder reads this file, `AGENTS.md`, `WORKFLOW.md`,
`REQUIREMENTS.md`, and `API_CONTRACT.md`, then checks branch, status, commit,
and remote before editing. Do not code from a stale checkout.
