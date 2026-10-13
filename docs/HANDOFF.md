# Current handoff

Updated: 14 October 2026
Checklist task: F06 (API request/response/error shapes) — reviewed and merged;
next row is D02 (Tickets and Categories tables)
Branch: `docs/F06-closeout`, off `main` at `6bdc3c3`
Pull request: [#7](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/7) into `main`
Active owner: Kavin (this closeout, then D02)
Incoming owner: Suhail (reviewer for this closeout and for D02)

## Where the project stands

F01-F04 are on `main`. F05 merged as pull request #4 (`4a549ed`) and provides the
Alembic migration mechanism and data-model notes. D01 merged as pull request #5
(`1faf1b8`). F06 merged as pull request [#6](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/6)
(`6bdc3c3`), and both people's agreement is now recorded in `docs/API_CONTRACT.md`.

Pull request #6 is the first merge in this project to carry a GitHub review:
Kavin approved it with the verification below written into the PR, which is what
the F03 evidence note asked reviewers to start doing instead of leaving the
review trail only in this file.

## F06 review outcome (14 October 2026)

Kavin reviewed the branch as the incoming reviewer named by the F06 handoff.

- All **36** F02 routes are present in the same order with the same "Who" text as
  the F02 baseline; no route, permission, or lifecycle rule changed. The change
  is additive documentation only.
- Every route table now names its request fields, success response, and error
  codes, and `git diff --check` is clean.
- The **400 versus 422** rule is agreed: `400` is a well-formed request the
  domain refuses (inactive category, disallowed attachment type or excess size,
  invalid settings limits, duplicate name/email, invalid assignee); `422` is a
  request that does not validate (wrong or missing types, extra fields, blank
  required strings, malformed UUIDs, invalid enum values).
- The `User` shape was cross-checked against the already-merged D01 schema: the
  contract exposes the role *name*, and the three listed names are identical to
  D01's `ck_roles_name_allowed` constraint on `roles.name`; `id`, `is_active`,
  `created_at`, and `updated_at` also match the `users` table.
- `response_overdue` and `resolution_overdue` are response-only derived fields,
  which is what `docs/DATA_MODEL.md` already states, so there is no conflict.

## Open items carried forward

1. **Article category — the one F06 item still open.** The contract's `Article`
   shape omits a category, but two other documents require one:
   `docs/DATA_MODEL.md` ("knowledge_articles: title, body, category, author, and
   a published flag") and the authoritative local checklist row **D06**, whose
   done-when is "Articles have title, body, category, author, and published
   status." Only `REQUIREMENTS.md`/F02 is silent, so the field cannot be removed
   by treating the contract as the winner. Because the contract defines no
   article-category route or field, reusing the existing `categories` table is
   the cheapest option. Decide before D06 (owner Suhail, checklist target
   20 October) and update `API_CONTRACT.md`, `DATA_MODEL.md`, and the tests in the
   same commit. F06's checklist row stays open until this is decided; the other
   35 shapes are agreed as written.
2. Two smaller F06 wording items, to fold into the D06/D07 doc touch rather than
   a separate branch: `GET /articles` says employees see published only, which
   implies agents and admins see every draft, while `GET /articles/{id}` returns
   a draft only to its author agent or an admin; and `PATCH /articles/{id}`'s
   "Who" column reads "Draft author or admin" while `REQUIREMENTS.md` says admins
   may edit any article.
3. No route changes a password — no admin reset and no self-service change. That
   matches checklist row A06's wording (create, list, edit, deactivate, assign
   role), so it is not a defect, but it should be stated as a v1 limitation
   before A06 is implemented.
4. **F05 acceptance gap, still open and owned by Kavin.** The checklist's F05
   done-when is "ER diagram and migrations cover every database entity in the
   architecture"; pull request #4 deliberately delivered only an empty baseline
   and no ER diagram. The migration half closes incrementally as D02-D06 and D07
   land tables, but the ER diagram is still missing. Kavin owns the row
   (reviewer Suhail, checklist target 12 October, already passed), so resolve it
   with a diagram that matches `docs/DATA_MODEL.md` once D02 lands.
5. The local-only checklist workbook has stale rows: F05 is still "In progress",
   and D01 and F06 are still "Not started" after merging as pull requests #5 and
   #6. Update the statuses and evidence links after this closeout merges, and
   leave F06 open until item 1 is decided.
6. Merged branches `feat/F05-schema-migrations` (`305ad52`) and
   `docs/F06-api-shapes` (`fe5009e`) still exist on `origin`; both are merged and
   safe to delete.
7. Targets have slipped: F06 was due 12 October and was reviewed on 14 October;
   D02 was due 13 October. Worth stating in the next mentor update.

## Checks run

- `git diff --check origin/main origin/docs/F06-api-shapes` reports clean.
- A diff of the route rows between `main` and the F06 branch is empty, and every
  route row has all four columns.
- `gh pr review 6 --approve` posted the review above, and pull request #6 merged
  with `mergeStateStatus: CLEAN`.
- F06 changes no code, so there is no new test run. The D01 result — `4 passed,
  1 warning`, the pre-existing Starlette `TestClient` deprecation warning — is
  prior evidence only and is not a claim that these shapes are implemented.

## Exact next action

Suhail reviews and merges this closeout pull request #7; Kavin authored it, so
Kavin must not merge it. Then both switch to `main` and pull with
`git pull --ff-only`.

After that, **D02 (Tickets and Categories tables)** is the next row. The
checklist assigns it to Kavin as owner and Suhail as reviewer, so it starts on
Kavin's side against the working D01 database, with the ticket columns and
derived-field notes already fixed in `docs/DATA_MODEL.md`. The exact ticket
status and priority check constraints must match the transition rules in
`REQUIREMENTS.md`, which `DATA_MODEL.md` already lists as a D02 decision. Do not
start D02 from an older remote state, and decide open item 1 before D06.
