# Current handoff

Updated: 14 October 2026
Checklist task: D06 (Knowledge Article model)
Branch: `feat/D06-knowledge-articles`, based on `main` at `989c58b`
Active owner: **Suhail** until the D06 branch is pushed; then **Kavin** reviews
the pull request before it is merged. Do not start another implementation row
from this branch.

## Where the project stands

F01-F04 and D01-D05 are on `main`. F05's migration mechanism is on `main`, but
its ER diagram is still missing and remains Kavin's open acceptance item. F06's
API shapes were reviewed in pull request #6. D05 pull request
[#12](https://github.com/CBE-SUHAIL/itsm-helpdesk/pull/12) was merged as
`989c58b` on 14 October before the Suhail review requested in the prior
handoff; **do not record #12 as reviewed**. I checked the merged model, migration,
and database tests afterward, with no blocking issue found. D02-D04 also lack
a recorded GitHub review. Resume the review step on D06.

The database now has all ten tables in the architecture image plus Alembic's
version table. D06 adds the eleventh, `knowledge_articles`, required by the
knowledge-base UI.

## D06 change

- Added `KnowledgeArticle` and migration `20261014_d06_knowledge_articles`,
  whose 31-character revision ID fits Alembic's 32-character version column.
- Each article has nonblank title and body, a required author, a required
  category, published status defaulting to false, and created/updated times.
  Category and author foreign keys restrict deletion. Indexes serve category
  filtering and an agent's own-draft listing.
- Reused the existing `categories` table rather than creating a second category
  system. `category_id` is now present in the Article response, create, patch,
  and optional list filter in `docs/API_CONTRACT.md`. The API must allow only
  active categories when creating or recategorizing; deactivating one leaves
  old articles readable. This is an API rule, not a database constraint.
- Aligned article visibility and editing across `REQUIREMENTS.md` and the API
  contract: employees see published only; agents see published plus own drafts
  and may edit own drafts; admins see and may edit any article. Only admins
  publish/unpublish. No article route exists yet: this row owns the schema only.
- Added a real-PostgreSQL constraint test and made migration-chain tests require
  the new table. Updated `DATA_MODEL.md` and `README.md`.

## Checks

On Suhail's Mac, using the existing local Postgres container on port 5433:

- `backend/.venv/bin/pytest -q backend/tests`: **12 passed, 1 warning**. The
  warning is the pre-existing Starlette `TestClient` deprecation.
- The suite upgrades to the new head, checks model/migration parity, and rolls
  back its changes. It tests category/author foreign keys, nonblank content,
  draft default, publish-state persistence, and restrictive delete behavior.
- `compileall` and `git diff --check` passed.

## Open items

1. Kavin reviews D06 before merge. Check especially whether sharing ticket
   categories with articles is acceptable for v1, and that the API contract's
   `400` on inactive category fits implementation plans. The previous F06
   article-category gap is resolved by D06's change, subject to that review.
2. F05 still needs an ER diagram showing the implemented tables and relations;
   Kavin owns this outstanding acceptance item.
3. No checklist row owns `GET /settings` and `PATCH /settings`; ask the mentor
   which task should implement them rather than silently expanding D05.
4. No route changes or resets a password in v1; make this explicit before A06.
5. The separately maintained local checklist workbook still has stale statuses
   and needs evidence links after review/merge. Do not mark unreviewed PRs as
   reviewed.

## Exact next action

After Suhail pushes this branch and opens its PR, **Kavin reviews D06**. He
should leave a GitHub review (or actionable comments), then Suhail incorporates
changes if needed and the PR is merged. Both pull `main` before the next task.
The incoming coder reads this file, `AGENTS.md`, `WORKFLOW.md`,
`REQUIREMENTS.md`, and `API_CONTRACT.md`, then checks branch, status, commit,
and remote before editing. Do not code from a stale checkout.
