# Current handoff

Updated: 8 October 2026
Checklist task: F02 closeout, then F03 and F04
Branch: `docs/F02-closeout` (off `main`)
Active owner: Kavin
Outgoing owner: Suhail (authored the F02 documentation)

## Where the project actually stands

Pull request [#1](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/1) was merged
into `main` on 8 October 2026 as commit `4503712`, authored by Kavin. F01 and
F02 are therefore done in substance:

- F01: the relay was exercised end to end in one direction — Suhail branched,
  pushed, and opened a pull request; Kavin reviewed, merged, and pulled. The
  reverse direction (Kavin opening, Suhail reviewing) is still unproven.
- F02: the feature rules and API contract are on `main` and are the working
  baseline for all later work.

The previous handoff note, which described pull request #1 as open and
unreviewed, and `docs/WORKFLOW.md`, which told the incoming person to switch to
`docs/F02-requirements`, are both out of date. That branch was deleted by the
merge; `main` is the only branch.

## Done in this handoff

- Answered the four decisions Suhail left open for review instead of settling
  them alone. They are recorded in `docs/REQUIREMENTS.md` under "F02 review
  decisions", each reflected in `docs/API_CONTRACT.md` in this commit:
  1. a notification can be dismissed as well as read;
  2. sign-in success/failure, user changes, ticket changes, and settings changes
     all write append-only audit records;
  3. no role sets priority when creating a ticket;
  4. F06 is not a duplicate: it keeps the narrowed job of confirming that every
     route names its request fields, response fields, and error codes.
- Rewrote this file to the post-merge state.

## Current state and checks

- Documentation only. There is still no application code, no database, and no
  test suite, so there are no application tests to run.
- Checks run on this branch: `git diff --check` is clean, all Markdown links in
  `docs/` resolve, and the requirements and contract agree with each other on
  all four decisions, including the new `PATCH /notifications/{id}/dismiss`
  route and the audit write rules.
- This branch is **not pushed yet**. Until it is, F02 is not handed over and the
  other person must not code from it.
- The reference checklist workbook and its extract stay local, outside Git, and
  must never be pushed.

## Open items carried forward

1. Suhail reviews the four decisions and objects if he disagrees. Any change
   goes into the docs before code, as `AGENTS.md` requires.
2. The checklist workbook still shows F01 and F02 as "In progress" with empty
   evidence. It needs F01 and F02 set to Done with pull request #1 as evidence,
   and F01 noted as proven in one direction only.
3. F06 is a live task again, with the narrowed scope above.

## Exact next action

Push `docs/F02-closeout`, open a pull request into `main`, and ask Suhail to
review the four decisions and the workbook update. After that merge, start F03
and F04 together on one branch, `feat/F03-F04-scaffold`: React and FastAPI
starter apps that run from documented commands, and a local PostgreSQL setup
with a committed sample environment file and no secrets. Both are due
9 October 2026 12:00, so F03/F04 is the next work, not F05.

F05 (schema and migrations) follows on 12 October, and needs the F03/F04
structure in place first. Suhail's earliest unblocked work after this merge is
D01 (Users and Roles tables), which only needs the F04 database running.
