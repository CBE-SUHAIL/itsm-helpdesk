# ITSM repository instructions for coding agents

This is a two-person, one-active-coder-at-a-time internship project. Follow the
full local architecture: React, FastAPI, SQLAlchemy, PostgreSQL, RBAC, ticket
support services, reporting, audit history, and tests. Do not silently shrink
scope to ticket CRUD or introduce cloud dependencies.

Before editing, read `docs/WORKFLOW.md`, `docs/HANDOFF.md`,
`docs/REQUIREMENTS.md`, and `docs/API_CONTRACT.md`. Check Git branch, status,
latest commit, and remote. Work only if named Active owner in the handoff,
or named incoming owner after its handoff trigger, or the human users explicitly
direct a handoff. Pull before editing.

Treat requirements and the API contract as shared decisions. If a change is
needed, update docs and tests with code; do not invent a different rule from
memory or another chat. Before every push, run relevant checks, update
`docs/HANDOFF.md`, commit it with the code, and push. State unfinished work and
the exact next action. Never force-push or overwrite another person's changes.
Keep secrets and real user data out of Git.
