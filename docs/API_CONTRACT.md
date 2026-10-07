# API contract (F02 working baseline)

This is the shared agreement between the React app and FastAPI backend. It is
not implemented yet. If the team changes a route or rule, update this file,
the requirements, and affected tests in the same commit. FastAPI's generated
OpenAPI page at `/docs` must match the implemented contract.

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

## Authentication and users

| Method and route | Who | Request → response |
| --- | --- | --- |
| `POST /auth/login` | Public | `{email, password}` → `{access_token, refresh_token, token_type: "bearer", user}` |
| `POST /auth/refresh` | Refresh-token holder | `{refresh_token}` → new access token and rotated refresh token |
| `POST /auth/logout` | Logged-in user | `{refresh_token}` → `204`; revoke that refresh token |
| `GET /users/me` | Logged-in user | Current user profile, without password hash |
| `GET /users` | Admin | Paginated user list, filterable by role/active state |
| `POST /users` | Admin | `{name, email, password, role}` → created user |
| `PATCH /users/{id}` | Admin | Change name, role, or active state; never return password hash |

An initial admin account is seeded locally through setup, not through a public
registration endpoint. User deactivation preserves linked ticket history.

## Categories and tickets

| Method and route | Who | Request → response |
| --- | --- | --- |
| `GET /categories` | Logged-in user | Active categories for the ticket form |
| `POST /categories` | Admin | `{name, description}` → category |
| `PATCH /categories/{id}` | Admin | Change name, description, or active state |
| `GET /tickets` | Logged-in user | Paginated list; filters: status, priority, category_id, assignee_id, created_from, created_to. Employees receive only their own tickets. |
| `POST /tickets` | Employee | `{title, description, category_id}` → new Open, Medium, unassigned ticket |
| `GET /tickets/{id}` | Ticket owner, agent, admin | Ticket detail with current SLA state |
| `POST /tickets/{id}/assignment` | Agent self-assigning an unassigned Open ticket; admin for Open/Assigned/In Progress | `{assignee_id}` or `{assignee_id: null}` → updated ticket |
| `POST /tickets/{id}/status` | Assigned agent for work transitions; ticket owner or admin for close | `{status, resolution_note?}` → updated ticket; enforce transition rules |
| `POST /tickets/{id}/priority` | Assigned agent or admin | `{priority, reason}` → updated ticket |
| `POST /tickets/{id}/category` | Assigned agent or admin | `{category_id, reason}` → updated ticket |
| `GET /tickets/{id}/history` | Ticket owner, agent, admin | Ordered immutable change history |

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

| Method and route | Who | Request → response |
| --- | --- | --- |
| `GET /tickets/{id}/comments` | Ticket owner, agent, admin | Ordered comments |
| `POST /tickets/{id}/comments` | Ticket owner, assigned agent, admin | `{body}` → comment; first assigned-agent comment records first response |
| `GET /tickets/{id}/attachments` | Ticket owner, agent, admin | Attachment metadata |
| `POST /tickets/{id}/attachments` | Ticket owner, assigned agent, admin | Multipart `file` → metadata; enforce type/size limits |
| `GET /tickets/{id}/attachments/{attachment_id}` | Ticket owner, agent, admin | File download, never a raw storage path |
| `GET /articles` | Logged-in user | Search with `q`; employees see only published articles |
| `GET /articles/{id}` | Published: logged-in user; draft: author agent/admin | Article detail |
| `POST /articles` | Agent or admin | `{title, body}` → draft article |
| `PATCH /articles/{id}` | Draft author or admin | Change title/body while draft; admin may edit any article |
| `POST /articles/{id}/publish` | Admin | Publish or unpublish with `{published: boolean}` |

Comments are public to everyone who can view the ticket; there are no private
agent notes in v1. No comment, attachment, or article hard-delete route in v1.

## Notifications, dashboards, reports, settings, and audit

| Method and route | Who | Request → response |
| --- | --- | --- |
| `GET /notifications` | Logged-in user | Own notifications; optional `unread_only` filter |
| `PATCH /notifications/{id}/read` | Notification owner | Mark read → updated notification |
| `GET /dashboard/summary` | Logged-in user | Counts by status/priority, overdue counts, agent workload where allowed |
| `GET /reports/tickets` | Agent or admin | Filters as in ticket list plus `format=csv` or `format=pdf` → downloadable report |
| `GET /settings` | Admin | SLA targets, attachment limit, allowed types |
| `PATCH /settings` | Admin | Partial settings update → current settings; audit change |
| `GET /audit-logs` | Admin | Paginated immutable activity records |

The frontend polls relevant ticket and notification endpoints every 15 seconds
while open. SLA breach detection may run in a local periodic backend worker;
it must create each breach notification only once. All data remains local.

## Data model implied by the contract

The architecture's PostgreSQL tables are Users, Roles, Tickets, Categories,
Comments, Ticket History, Attachments, Audit Logs, Notifications, and System
Settings. Add Knowledge Articles for the pictured knowledge-base UI and hashed
Refresh Tokens for session management. Store file metadata in Attachments and
file bytes outside PostgreSQL in local storage.
