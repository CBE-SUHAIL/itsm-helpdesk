# API contract (F02 baseline; F06 shape draft)

This is the shared agreement between the React app and FastAPI backend. It is
not implemented yet. If the team changes a route or rule, update this file,
the requirements, and affected tests in the same commit. FastAPI's generated
OpenAPI page at `/docs` must match the implemented contract.

Pull request #1 accepted this baseline and the four review decisions recorded in
[REQUIREMENTS.md](REQUIREMENTS.md) under "F02 review decisions". Checklist row F06
keeps the narrower job of confirming that every route below names its request
fields, response fields, and error codes, and that both people agree on them.
The F06 additions below are a **local draft** awaiting Kavin's shape review;
they are not implemented API behavior or a claim that F06 is complete.

Base path: `/api/v1`. JSON is used except for multipart file upload and CSV/PDF
downloads. IDs are UUID strings. Timestamps are ISO 8601 UTC strings ending in
`Z`. Authentication uses `Authorization: Bearer <access_token>`.

## Shared behavior

- A 30-minute JWT access token identifies the user and role. A 7-day refresh
  token is stored hashed server-side and revoked on logout. The React app must
  not assume that hiding an action grants or removes permission.
- List routes accept `limit` (default 20, max 100) and `offset` (default 0),
  plus the filters listed below. They return `{items: [...], total: number}`.
- Errors return `{detail: string}`. Use 400 for invalid business input, 401 for
  missing/expired login, 403 for forbidden access, 404 for missing/inaccessible
  records, 409 for conflicting state transitions, and 422 for invalid fields.
  Never include stack traces or passwords in responses.
- Ticket changes are transactional: update the ticket, append history/audit,
  and create relevant notifications together or roll back together.

### Response shapes used below

All fields in these shapes are present; fields marked `null` may contain JSON
`null`. A `PATCH` request contains only the named fields being changed and
must contain at least one of them. Path IDs are UUIDs. `created_at`,
`updated_at`, and other `*_at` fields are UTC timestamps.

| Shape | Exact fields |
| --- | --- |
| `User` | `id`, `name`, `email`, `role` (Employee, Support agent, Admin), `is_active`, `created_at`, `updated_at`. Never include `password` or `password_hash`. |
| `Category` | `id`, `name`, `description`, `is_active`, `created_at`, `updated_at`. |
| `Ticket` | `id`, `title`, `description`, `category_id`, `creator_id`, `assignee_id` (null until assigned), `status`, `priority`, `response_due_at`, `resolution_due_at`, `first_response_at` (null until response), `resolved_at` (null until resolved), `response_overdue`, `resolution_overdue`, `created_at`, `updated_at`. |
| `TicketHistory` | `id`, `ticket_id`, `actor_id`, `field` (status, assignee_id, category_id, or priority), `old_value` (nullable), `new_value` (nullable), `reason` (nullable), `created_at`. One row per changed field. |
| `Comment` | `id`, `ticket_id`, `author_id`, `body`, `created_at`. |
| `Attachment` | `id`, `ticket_id`, `uploader_id`, `file_name`, `content_type`, `size_bytes`, `created_at`. Never include the storage path. |
| `Article` | `id`, `title`, `body`, `author_id`, `is_published`, `created_at`, `updated_at`. |
| `Notification` | `id`, `recipient_id`, `ticket_id` (nullable), `type`, `message`, `read_at` (nullable), `dismissed_at` (nullable), `created_at`. |
| `Settings` | `sla_targets` (one `first_response_hours` and `resolution_hours` pair for each Low, Medium, High, Critical priority), `max_attachment_bytes`, `allowed_attachment_types` (array of MIME type strings). |
| `AuditLog` | `id`, `actor_id` (nullable for failed login), `action`, `entity_type`, `entity_id` (nullable), `old_value` (nullable JSON), `new_value` (nullable JSON), `created_at`. A failed login stores only `attempted_email` in `new_value`, never the password. |

`Page<T>` means `{items: T[], total: integer}`. List routes use the shared
`limit` and `offset` parameters unless a route says otherwise. Empty lists
return `items: []` and `total: 0` (or `[]` for unpaginated lists), not 404.
For every route, the "Errors" column names its expected HTTP error status
codes; the shared `{detail: string}` body applies to each. `422` also covers
malformed UUID path values, invalid query types, and extra request fields.
Ticket `status` is one of Open, Assigned, In Progress, Resolved, Closed;
`priority` is one of Low, Medium, High, Critical. Notification `type` is one
of `assignment`, `comment`, `resolution`, `closure`, or `sla_breach`.

## Authentication and users

| Method and route | Who | Request fields | Success response | Errors |
| --- | --- | --- | --- | --- |
| `POST /auth/login` | Public | JSON `email`, `password` | `200` `{access_token, refresh_token, token_type: "bearer", user: User}` | `401` invalid credentials or inactive user, without revealing which; `422` invalid fields |
| `POST /auth/refresh` | Refresh-token holder | JSON `refresh_token` | `200` `{access_token, refresh_token, token_type: "bearer"}`; old refresh token revoked | `401` invalid, expired, or revoked token; `422` invalid fields |
| `POST /auth/logout` | Logged-in user | Bearer token; JSON `refresh_token` | `204` no body; revoke that refresh token | `401` invalid login or refresh token; `422` invalid fields |
| `GET /users/me` | Logged-in user | Bearer token; no body or query | `200` `User` | `401` missing or expired login |
| `GET /users` | Admin | Query `limit`, `offset`, optional `role`, `is_active`; no body | `200` `Page<User>` | `401`, `403`, `422` |
| `POST /users` | Admin | JSON `name`, `email`, `password`, `role`; no public registration | `201` `User` | `400` invalid business input; `401`, `403`; `409` email already used; `422` invalid fields |
| `PATCH /users/{id}` | Admin | Path `id`; JSON any nonempty subset of `name`, `role`, `is_active`; no password update here | `200` `User` | `400` invalid business input; `401`, `403`, `404`, `422` |

An initial admin account is seeded locally through setup, not through a public
registration endpoint. User deactivation preserves linked ticket history.

## Categories and tickets

| Method and route | Who | Request fields | Success response | Errors |
| --- | --- | --- | --- | --- |
| `GET /categories` | Logged-in user | Query `limit`, `offset`; no body. Active categories only | `200` `Page<Category>` | `401`, `422` |
| `POST /categories` | Admin | JSON `name`, `description` | `201` `Category` | `400` invalid business input; `401`, `403`; `409` duplicate name; `422` invalid fields |
| `PATCH /categories/{id}` | Admin | Path `id`; JSON any nonempty subset of `name`, `description`, `is_active` | `200` `Category` | `400` invalid business input; `401`, `403`, `404`; `409` duplicate name; `422` invalid fields |
| `GET /tickets` | Logged-in user | Query `limit`, `offset`, optional `status`, `priority`, `category_id`, `assignee_id`, `created_from`, `created_to`; no body. Employees see own tickets only | `200` `Page<Ticket>` | `401`, `422` |
| `POST /tickets` | Employee | JSON exactly `title`, `description`, `category_id`; `priority` is forbidden | `201` `Ticket` with Open, Medium, and null assignee | `400` inactive category; `401`, `403`, `404` category missing; `422` invalid or extra fields |
| `GET /tickets/{id}` | Ticket owner, agent, admin | Path `id`; no body or query | `200` `Ticket` with current SLA fields | `401`, `404` missing or inaccessible, `422` |
| `POST /tickets/{id}/assignment` | Agent self-assigning an unassigned Open ticket; admin for Open/Assigned/In Progress | Path `id`; JSON `assignee_id` (UUID or null). Null is admin-only | `200` updated `Ticket` | `400` invalid assignee; `401`, `403`, `404`; `409` invalid ticket state; `422` |
| `POST /tickets/{id}/status` | Assigned agent for work transitions; ticket owner or admin for close | Path `id`; JSON `status`, optional `resolution_note` (required and nonblank for Resolved) | `200` updated `Ticket` | `401`, `403`, `404`; `409` invalid transition; `422` missing/blank note or invalid fields |
| `POST /tickets/{id}/priority` | Assigned agent or admin | Path `id`; JSON `priority`, nonblank `reason` | `200` updated `Ticket` | `401`, `403`, `404`; `409` conflicting state; `422` missing/blank reason or invalid fields |
| `POST /tickets/{id}/category` | Assigned agent or admin | Path `id`; JSON `category_id`, nonblank `reason` | `200` updated `Ticket` | `400` inactive category; `401`, `403`, `404`; `409` conflicting state; `422` missing/blank reason or invalid fields |
| `GET /tickets/{id}/history` | Ticket owner, agent, admin | Path `id`; query `limit`, `offset`; no body | `200` `Page<TicketHistory>` ordered oldest first | `401`, `404` missing or inaccessible ticket, `422` |

`POST /tickets` accepts exactly `title`, `description`, and `category_id`. A
`priority` field is rejected with 422 for every role, including agents and
admins, so a new ticket always starts `Medium`; priority is set only through
`POST /tickets/{id}/priority`, which requires a reason.

`POST /tickets/{id}/assignment` with a null assignee is admin-only and moves
Assigned/In Progress back to Open. It is rejected for Resolved/Closed tickets.
`POST /tickets/{id}/status` permits only the transitions documented in
[REQUIREMENTS.md](REQUIREMENTS.md); `Resolved` requires `resolution_note`.
The ticket owner means its creating employee, not its assigned agent.

Ticket response fields include `id`, `title`, `description`, `category_id`,
`creator_id`, `assignee_id`, `status`, `priority`, `response_due_at`,
`resolution_due_at`, `first_response_at`, `resolved_at`, `response_overdue`,
`resolution_overdue`, `created_at`, and `updated_at`.

## Comments, attachments, and knowledge articles

| Method and route | Who | Request fields | Success response | Errors |
| --- | --- | --- | --- | --- |
| `GET /tickets/{id}/comments` | Ticket owner, agent, admin | Path `id`; query `limit`, `offset`; no body | `200` `Page<Comment>` ordered oldest first | `401`, `404` missing or inaccessible ticket, `422` |
| `POST /tickets/{id}/comments` | Ticket owner, assigned agent, admin | Path `id`; JSON nonblank `body` | `201` `Comment`; first assigned-agent comment also records first response | `401`, `403`, `404`; `422` blank body or invalid fields |
| `GET /tickets/{id}/attachments` | Ticket owner, agent, admin | Path `id`; query `limit`, `offset`; no body | `200` `Page<Attachment>` | `401`, `404` missing or inaccessible ticket, `422` |
| `POST /tickets/{id}/attachments` | Ticket owner, assigned agent, admin | Path `id`; multipart `file` (PDF, PNG, JPEG, or TXT; at most current size limit) | `201` `Attachment` metadata | `400` disallowed type or excess size; `401`, `403`, `404`, `422` missing file/invalid ID |
| `GET /tickets/{id}/attachments/{attachment_id}` | Ticket owner, agent, admin | Path `id`, `attachment_id`; no body | `200` file bytes with `Content-Type` and `Content-Disposition` filename; never a storage path | `401`, `404` missing/inaccessible ticket or attachment, `422` |
| `GET /articles` | Logged-in user | Query `limit`, `offset`, optional `q`; no body. Employees see published only | `200` `Page<Article>` | `401`, `422` |
| `GET /articles/{id}` | Published: logged-in user; draft: author agent/admin | Path `id`; no body | `200` `Article` | `401`, `404` missing or inaccessible, `422` |
| `POST /articles` | Agent or admin | JSON `title`, `body` | `201` draft `Article` with `is_published: false` | `401`, `403`; `422` blank content or invalid fields |
| `PATCH /articles/{id}` | Draft author or admin | Path `id`; JSON nonempty subset of `title`, `body`. Agent may edit own draft only | `200` updated `Article` | `401`, `403`, `404`; `422` blank content or invalid fields |
| `POST /articles/{id}/publish` | Admin | Path `id`; JSON `published` (boolean) | `200` updated `Article` | `401`, `403`, `404`, `422` |

Comments are public to everyone who can view the ticket; there are no private
agent notes in v1. No comment, attachment, or article hard-delete route in v1.

## Notifications, dashboards, reports, settings, and audit

| Method and route | Who | Request fields | Success response | Errors |
| --- | --- | --- | --- | --- |
| `GET /notifications` | Logged-in user | Query `limit`, `offset`, optional `include_dismissed` (default false), `unread_only` (default false); no body | `200` `Page<Notification>` for current user, newest first | `401`, `422` |
| `PATCH /notifications/{id}/read` | Notification owner | Path `id`; no body | `200` updated `Notification` with `read_at` set; remains listed | `401`, `404` missing or not owned, `422` |
| `PATCH /notifications/{id}/dismiss` | Notification owner | Path `id`; no body | `200` updated `Notification` with `dismissed_at` set; hidden from default list | `401`, `404` missing or not owned, `422` |
| `GET /dashboard/summary` | Logged-in user | No body or query | `200` `{counts_by_status, counts_by_priority, response_overdue_count, resolution_overdue_count, agent_workload}`; count maps use status/priority labels and integer values; `agent_workload` maps agent UUIDs to integer counts for agent/admin, or is null for employee | `401` |
| `GET /reports/tickets` | Agent or admin | Query optional `status`, `priority`, `category_id`, `assignee_id`, `created_from`, `created_to`; required `format` (`csv` or `pdf`); no body | `200` downloadable bytes with `Content-Type: text/csv` or `application/pdf` and `Content-Disposition`; columns: ticket `id`, `title`, `status`, `priority`, `category_id`, `creator_id`, `assignee_id`, `created_at`, `response_due_at`, `resolution_due_at`, `response_overdue`, `resolution_overdue` | `401`, `403`, `422` invalid format/filters |
| `GET /settings` | Admin | No body or query | `200` `Settings` | `401`, `403` |
| `PATCH /settings` | Admin | JSON nonempty subset of `sla_targets`, `max_attachment_bytes`, `allowed_attachment_types` | `200` updated `Settings`; change audited | `400` invalid business limits; `401`, `403`, `422` invalid fields |
| `GET /audit-logs` | Admin | Query `limit`, `offset`, optional `actor_id`, `action`, `entity_type`, `entity_id`, `created_from`, `created_to`; no body | `200` `Page<AuditLog>` newest first | `401`, `403`, `422` |

The frontend polls relevant ticket and notification endpoints every 15 seconds
while open. SLA breach detection may run in a local periodic backend worker;
it must create each breach notification only once. All data remains local.

### Notification read and dismiss

`PATCH /notifications/{id}/read` and `PATCH /notifications/{id}/dismiss` are
separate owner-only actions on the same record. Read leaves the notification in
the list and clears it from the unread count; dismiss removes it from the
default list. Neither is a hard delete, and neither writes a history or audit
entry. A notification may be read and still listed, or dismissed without being
read. The React dismiss control is optional in v1; marking read is required.

### Audit records

`GET /audit-logs` reads records the API writes, and no route creates, updates,
or deletes an audit record directly. One entry is written in the same
transaction as the change it describes for:

- sign-in success and sign-in failure, where `actor_id` is null on failure and
  only the attempted email is stored;
- user create, edit, role change, and deactivation;
- ticket create, and every status, assignee, category, or priority change;
- settings changes, including SLA targets and attachment limits.

Each record has `id`, `actor_id`, `action`, `entity_type`, `entity_id`,
`old_value`, `new_value`, and `created_at` (UTC). `GET /audit-logs` is
admin-only, paginated like other list routes, and filters by `actor_id`,
`action`, `entity_type`, `entity_id`, `created_from`, and `created_to`.
Notification read and dismiss actions are not audited.

## Data model implied by the contract

The architecture's PostgreSQL tables are Users, Roles, Tickets, Categories,
Comments, Ticket History, Attachments, Audit Logs, Notifications, and System
Settings. Add Knowledge Articles for the pictured knowledge-base UI and hashed
Refresh Tokens for session management. Store file metadata in Attachments and
file bytes outside PostgreSQL in local storage. Notifications store read and
dismissed timestamps as independent states, and Audit Logs are append-only:
never updated and never deleted.

## F06 review before this becomes the shared contract

The tables above cover all 36 F02 routes. Before marking F06 done, Suhail and
Kavin must explicitly confirm the proposed field names and error codes,
especially the `User`/`Ticket`/`Settings` shapes, dashboard counts, report
export fields, and the 400-versus-422 distinction. Record their agreement in
`docs/HANDOFF.md` during the F06 review; the branch must not be treated as a
completed frontend/backend agreement until then. Later implementation tests
and FastAPI's `/docs` must match the confirmed shapes.
