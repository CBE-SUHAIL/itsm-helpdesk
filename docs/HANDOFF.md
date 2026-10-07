# Current handoff

Updated: 8 October 2026
Checklist task: F02 — Confirm feature rules and interfaces
Branch: `docs/F02-requirements`
Pull request: [#1](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/1) into `main` — open, awaiting review
Active owner: Kavin
Outgoing owner: Suhail (authored both F02 documentation commits)
Handoff completed: Kavin accepted the invitation, pulled `docs/F02-requirements`,
and became Active owner on 8 October 2026. Suhail reviews the open pull request
and does not edit this branch until the next handoff.

## Completed on this branch

- Working product defaults in `docs/REQUIREMENTS.md`.
- API endpoints and payload rules in `docs/API_CONTRACT.md`.
- Relay process in `docs/WORKFLOW.md` and root `AGENTS.md`.
- Pull request #1 opened against `main`.

## Added in this handoff

- This handoff note updated to the post-handoff, under-review state.
- No edits to Suhail's requirements or API contract. The open decisions below
  are left for review instead of being changed unilaterally during the handoff.

## Current state and checks

- Documentation only; application code has not been started.
- Documentation checks: `git diff --check` is clean and all 7 local Markdown
  links resolve. No application code exists yet, so there are no application
  tests to run.
- Pull request #1 is open and unreviewed. `main` still contains only
  `docs/WORKFLOW.md`.
- The reference checklist workbook and its extract are kept locally outside Git
  and must never be pushed.

## Open decisions for review (pull request #1)

1. Notification dismiss: S01 says users can "read or dismiss"; the contract has
   read only.
2. Audit coverage: G01 requires audit records for login, user, ticket, and
   settings changes; the contract documents only `GET /audit-logs`.
3. Ticket priority at creation: T09 mentions "priority where permitted", but
   `POST /tickets` is Employee-only and employees cannot set priority.
4. F06 overlap: "Define API request and response shapes" duplicates work that
   `docs/API_CONTRACT.md` already covers.

## Exact next action

Suhail reviews pull request #1 and resolves the four decisions above in review.
Agreed edits go on this branch in the same review round, so `main` matches the
contract when it merges. After merge: mark F02 Done in the checklist with pull
request #1 as evidence, record F01 against the same pull request while noting
that the reverse direction is still unproven, and both people pull `main` before
starting F03. Do not begin application code from undocumented alternative rules.
