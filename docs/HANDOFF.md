# Current handoff

Updated: 14 October 2026
Checklist task: D07 (Models, relationships, and session handling)
Branch: `feat/D07-relationships-session`, based on `main` at `ec5c63a` and now
merged with `main` at `2be6600` (F05's ER diagram)
Pull request: [#15](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/15) into
`main`, with Suhail requested as reviewer
Active owner: **Kavin** on this branch. Incoming owner: **Suhail** reviews and
merges, then takes D08.

## Where the project stands

F01-F04 and D01-D06 are on `main`, and all eleven tables exist. D06 pull request
[#13](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/13) was approved and
merged as `ec5c63a`, the first recorded GitHub review approval since #6. D05
(#12) and D02-D04 were merged without a recorded GitHub review and must still be
described that way.

**F05's ER diagram landed while this branch was open.**
[#14](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/14), `docs/F05-er-diagram`,
was merged as `2be6600` on 14 October at Kavin's direction with **no recorded
GitHub review** (`gh pr view 14` shows an empty review list), so it joins #12 and
D02-D04: do not describe it as reviewed. `main` passes 16 tests at that commit —
the 12 that were already there plus the 4 ER-diagram guards — and F05's
remaining acceptance item is met.

This branch has since merged `main` at `2be6600`. That merge touched only the two
docs: `docs/DATA_MODEL.md` and this file now carry **both** F05's ER-diagram
section and D07's decisions section, with neither dropped. The full suite is
**22 passed** after the merge — F05's diagram guards pass unchanged against D07's
models, because relationships add no column and `alembic check` reports no drift.

## F05 change (already merged to `main` as `2be6600`, kept here for context)

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

## D07 change

No table and no column: D07 is the Python side of the data access layer, and
`alembic check` reports **no drift** after it, so no migration is needed.

- **Relationships.** All fifteen foreign keys now have a `relationship()` on the
  child and a `back_populates` collection on the parent, so a route reads
  `ticket.category.name` instead of hand-writing a join. The two ambiguous links
  are `tickets.creator_id` and `tickets.assignee_id`, both pointing at `users`;
  each side names its foreign key explicitly. Reverse collections are named for
  the role they play (`tickets_created`, `tickets_assigned`,
  `ticket_history_entries`) because `User.tickets` twice would be ambiguous.
- **No cascade deletes.** Nothing sets `cascade="all, delete"`, so
  `session.delete(user)` cannot quietly take tickets, history, or audit rows with
  it; the restrictive foreign keys raise instead.
- **Session handling** in `app/core/db.py`: a `SessionLocal` factory
  (`autoflush=False`, `expire_on_commit=False`), a `get_db` FastAPI dependency,
  and a `session_scope` context manager. The request is one unit of work and the
  caller commits it, because `API_CONTRACT.md` requires a ticket change to update
  the ticket and append its history, audit, and notification rows "together or
  roll back together". `db.py` owns the failure path, never the commit: `get_db`
  rolls back if the route raises and always closes; `session_scope` commits on
  success and rolls back on error.
- `backend/tests/test_relationships_and_sessions.py` is new. The first test needs
  no database and fails if a foreign key has no relationship, if a
  `back_populates` names something that does not exist, or if a relationship
  appears that no foreign key justifies. The rest run real PostgreSQL and prove a
  relationship loads from the database rather than from the identity map, that a
  commit is visible to a later session, and that a rollback leaves nothing behind.
- `docs/DATA_MODEL.md` gains a D07 decisions section; `README.md` states that D07
  adds no table.

## Checks

- `pytest -q backend/tests`: **22 passed** after merging `main` at `2be6600`.
  That is the 16 tests on `main` (the 12 already there plus F05's 4 ER-diagram
  guards) plus the 6 D07 added. Before the merge the branch reported 18 passed,
  which is the 12 on `main` at `ec5c63a` plus the 6 added here; F05's branch
  reported 16 at that commit.
- `alembic check`: **no new upgrade operations detected**, which is the point of
  this row — relationships are Python-side and must not drift the schema.
- F05's diagram guard was verified in both directions, not just green: deleting a
  column, deleting a relationship line, and flipping a nullable `|o` to `||` each
  made the relevant test fail, and the file was restored afterwards. It was also
  parsed with **Mermaid's own parser** (mermaid 11 + jsdom in a scratch
  directory): `PARSE OK`, `diagramType: "er"`, 11 entities, 15 relationships, so
  it renders on GitHub rather than only looking plausible.
- The D07 relationship guard was verified in both directions as well: deleting
  `Ticket.assignee` makes the database-free test fail, and restoring it passes.
- Every database-backed D07 test wraps itself in an outer transaction with
  `join_transaction_mode="create_savepoint"`, so a session really commits while
  the surrounding transaction still discards it. These tests cannot leave a row in
  the development database.
- The local database is at head (`20261014_d06_knowledge_articles`); F05 upgraded
  it from D05 and D07 adds no migration.
- `git diff --check` and `compileall` passed.
- Verified count before and after: 15 foreign keys, 30 relationship endpoints,
  and `SystemSetting` deliberately has none.

### Environment: the database must be reachable for any of this

Recorded because it cost most of an afternoon on both F05 and D07. The
database-backed tests first failed wholesale with psycopg connection timeouts,
which looked like a networking problem but is not. `.wslconfig` sets
`networkingMode=mirrored`, and WSL shuts an idle distro (or VM) down after
`[general] instanceIdleTimeout`, whose default is **15 seconds**. With no
interactive WSL session open, the distro stopped between test files, so
`localhost:5432` disappeared part-way through a run — which is also why a raw TCP
connect could succeed while the Postgres handshake timed out: the listener
disappeared mid-conversation.

`[wsl2] vmIdleTimeout` does **not** fix this; the WSL documentation restricts it
to `networkingMode=NAT`. The working setting is `[general]
instanceIdleTimeout=43200000` (12 hours), now in `~/.wslconfig`, followed by
`wsl --shutdown`. The previous file is at `~/.wslconfig.backup-20261014-234804`,
and `-1` disables auto-shutdown entirely. Verify with `wsl -l -v` showing
`Running` and `pytest -q backend/tests` passing. The dev database is at head
(`20261014_d06_knowledge_articles`).

## Open items

1. The `main` merge conflict in this file and `docs/DATA_MODEL.md` is **resolved
   on this branch** by keeping both the F05 and D07 sections. Nothing further to
   do here; it is listed so the reviewer knows it was deliberate.
2. No checklist row owns `GET /settings` and `PATCH /settings`; ask the mentor
   which task should implement them rather than silently expanding D05.
3. No route changes or resets a password in v1; make this explicit before A06.
4. The separately maintained local checklist workbook still has stale statuses
   (D02-D05 still read "Not started") and needs evidence links. Do not mark
   unreviewed pull requests as reviewed.
5. The ER-diagram guard only covers the diagram. A later row that adds a table
   will fail `test_er_diagram.py` until the diagram is redrawn, which is the
   intent, so redraw rather than relax the test.
6. `instanceIdleTimeout` keeps the WSL VM resident for 12 hours. With
   `autoMemoryReclaim=disabled` in the same file, that holds memory the VM has
   claimed until it stops. Use `wsl --shutdown` when finished for the day if that
   matters.
7. `refresh_tokens` arrives with A01/A02. When it does, it needs a relationship
   like the others, and the database-free test here will fail until it has one.
   The ER diagram must be updated in the same commit.

## Exact next action

**Suhail reviews this branch**, then merges. Worth checking: whether the
transaction policy (the caller commits, `get_db` only rolls back) is the split he
wants before T01 starts writing routes against it, and whether naming the reverse
collections `tickets_created`/`tickets_assigned` is better than one `tickets`
collection. Also confirm the merge kept both docs sections and that
`pytest -q backend/tests` reports **22 passed**.

After that, **D08 (seed demo users and tickets)** is Suhail's row, and A01/A02
follow it. `D07` is the last row Kavin owns in the data phase; his next rows after
this are T01-T04, T06, T07, S01, G01, G03-G05, and G07.

The incoming coder reads this file, `AGENTS.md`, `WORKFLOW.md`,
`REQUIREMENTS.md`, and `API_CONTRACT.md`, then checks branch, status, commit,
and remote before editing. Do not code from a stale checkout.
