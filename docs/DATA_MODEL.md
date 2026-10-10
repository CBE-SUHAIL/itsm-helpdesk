# Data model

Status: opened by F05 (database schema and migrations), 9 October 2026.

[REQUIREMENTS.md](REQUIREMENTS.md) says what the system must do and
[API_CONTRACT.md](API_CONTRACT.md) says what the API exchanges. Neither decides
the column-level questions those two imply: which checklist row owns which
table, what every constraint is named, and which conventions hold for every
table. This file is that third agreement.

Read it before writing a model or a migration, and change it in the same commit
as the model or migration it describes, the way the other two documents are
changed.

## What F05 decided

F05 owns the migration **mechanism**. The baseline revision
`20261008_2150_baseline` creates no tables, on purpose:

- the chain needs a root before anything can be added to it, and
  `alembic upgrade head` can be proven against the running container while the
  schema is still empty, so a later failure is unambiguously about a later
  revision;
- `app/models/__init__.py` fixes the naming convention (below) before any table
  exists. Constraint names are compared by name during autogenerate, so renaming
  them once a table exists costs a migration per rename.

The tables and their minimal ORM models arrive together with D01-D06, and
`refresh_tokens` with A01/A02. D07 completes shared relationships and session
handling. Keeping each model beside its migration lets
`test_models_match_the_database` detect drift from D01 onward.

## Naming conventions

Every table inherits this metadata convention from `app/models/__init__.py`, so
a constraint can be named in a migration review and found in the database
without opening it:

| Kind | Pattern | Example |
| --- | --- | --- |
| Primary key | `pk_%(table_name)s` | `pk_tickets` |
| Foreign key | `fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s` | `fk_tickets_assignee_id_users` |
| Unique | `uq_%(table_name)s_%(column_0_N_name)s` | `uq_users_email` |
| Check | `ck_%(table_name)s_%(constraint_name)s` | `ck_tickets_status` |
| Index | `ix_%(table_name)s_%(column_0_N_name)s` | `ix_tickets_status` |

Check constraints must therefore be given an explicit `name=` in the model, or
the generated name collapses to a bare `ck_<table>_`. Table names are plural
`snake_case`; column names are singular `snake_case`.

## Conventions that apply to every table

Each of these restates a decision from the two documents above and gives it a
storage shape. Do not vary one table at a time.

- **Primary keys are UUIDs**, stored as PostgreSQL `uuid`, and are exposed in
  JSON as strings. The contract says IDs are UUID strings.
- **Timestamps are `timestamptz` in UTC**, written as `datetime.now(timezone.utc)`,
  and serialised as ISO 8601 ending in `Z`. Never a naive timestamp and never a
  server-default `now()` that the application cannot see.
- **`created_at` and `updated_at` on every table** except the append-only ones
  below, which carry `created_at` only because they are never updated.
- **Nothing is hard-deleted** in v1: not tickets, comments, attachments,
  articles, or users. Users are deactivated; the rest are withheld from list
  routes by a flag or a status instead of a `DELETE`.
- **Ticket History and Audit Logs are append-only.** They are written in the same
  transaction as the change they describe, so a rolled-back change leaves no
  entry, and no route updates or deletes a row.
- **Enumerated values are stored as text with a check constraint**, not as
  PostgreSQL `enum` types, because altering a `enum` needs its own migration
  dance and the naming convention above already gives the check a stable name.
  The closed sets are: ticket status, ticket priority, and role.
- **Foreign keys that point at a record the UI must still be able to name** are
  `ON DELETE RESTRICT`, which is what "no hard delete" means in practice.
- **SLA targets are copied onto the ticket at creation**, not looked up at read
  time, so a later settings change never rewrites an existing deadline.

## Table ownership

| Row | Tables | Notes |
| --- | --- | --- |
| F05 | *(none)* | Mechanism only. `alembic_version` is Alembic's own table. |
| D01 | `users`, `roles` | Users reference one of the three fixed roles. |
| D02 | `tickets`, `categories` | Core ticket and category records. |
| D03 | `comments`, `ticket_history` | Conversation and immutable ticket changes. |
| D04 | `attachments`, `audit_logs` | File metadata and immutable activity records. |
| D05 | `notifications`, `system_settings` | Personal notices and admin settings. |
| D06 | `knowledge_articles` | Knowledge-base content. |
| A01/A02 | `refresh_tokens` | Hashed refresh tokens for session management. |

This assignment now matches the local project checklist. The prior F05 draft
mapped D02-D06 differently; D01 corrected the bookkeeping before later tables
were added.

## Columns the contract already fixes

These follow from the response fields and rules in `API_CONTRACT.md` and are
listed so a D-row does not have to rediscover them:

- `users`: name, email (unique), password hash, role, active flag. The password
  hash is never returned by any route.
- `roles`: one of the three fixed names Employee, Support agent, or Admin. D01
  stores names only; A03 will enforce their permission sets from
  `REQUIREMENTS.md` in backend code. There are no editable permission columns
  or rows in v1 because the contract has no role-permission editing API.
- `tickets`: title, description, `category_id`, `creator_id`, `assignee_id`
  (nullable while unassigned), status, priority, `response_due_at`,
  `resolution_due_at`, `first_response_at`, `resolved_at`, `created_at`,
  `updated_at`. `response_overdue` and `resolution_overdue` appear in the
  ticket response but are **derived** from the due and actual timestamps against
  the current clock, so they are not stored columns.
- `ticket_history`: actor, old value, new value, reason where the change needed
  one, and UTC time.
- `audit_logs`: `actor_id` (null on a failed sign-in, where only the attempted
  email is stored), action, `entity_type`, `entity_id`, `old_value`,
  `new_value`, `created_at`.
- `notifications`: owner, and **two independent** timestamps, read and
  dismissed, because a notification may be read and still listed, or dismissed
  without being read.
- `attachments`: metadata only. File bytes live in a local directory outside the
  public web folder; the stored name is generated server-side and a
  client-supplied path is never trusted.
- `knowledge_articles`: title, body, category, author, and a published flag.
  Drafts are visible to their author agent and to admins; employees see
  published only.
- `system_settings`: SLA targets per priority, attachment size limit, and
  allowed file types.
- `refresh_tokens`: the hash of the token, never the token itself, plus its
  owning user and expiry, so logout can revoke exactly one.

## Not yet decided here

Left deliberately to the rows that own them, so this file does not pretend to a
decision nobody made: whether settings is one row read as a singleton or a
key/value table (D05); the exact ticket status and priority check constraints,
which must match the transition rules in `REQUIREMENTS.md` exactly (D02);
attachment storage layout on disk (D04); or the index strategy for ticket
history (D03) and audit logs (D04) if either grows past a demo.

## D01 decisions

- `users.role_id` is a required foreign key to `roles.id`; the database blocks
  deleting a role while any user references it. Users themselves are deactivated,
  not deleted.
- `roles.name` is unique and limited to the three agreed names. The permission
  matrix remains in `REQUIREMENTS.md` until A03 implements it.
- `users.email` is unique and stored trimmed and lowercase. The database rejects
  non-normalized values, so a later API must normalize before insertion and
  login lookup. User name and password hash cannot be blank. The hash is never
  exposed in an API response.
- Both tables use UUID primary keys and application-written UTC timestamps.
