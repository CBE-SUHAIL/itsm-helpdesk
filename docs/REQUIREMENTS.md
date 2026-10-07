# ITSM requirements and working decisions

Status: F02 working baseline, 7 October 2026. The mentor left product choices to
the team. Suhail and Kavin may revise these defaults together, but changes must
be recorded here and reflected in the API contract before implementation.

The goal is the full locally deployed architecture in the project workbook:
React, FastAPI, SQLAlchemy, PostgreSQL, JWT/RBAC, ticket lifecycle, support
services, dashboards, reports, audit history, and tests. No AI/ML is required.

## Roles and permissions

| Role | Permissions |
| --- | --- |
| Employee | Create tickets; view, comment on, and attach files to own tickets; read published knowledge articles and own notifications; close own Resolved tickets. |
| Support agent | View the support queue and all tickets; self-assign Open tickets; work on, comment on, attach files to, and set priority for assigned tickets; draft knowledge articles. |
| Admin | Manage users, roles, categories, settings, and knowledge articles; assign or reassign any ticket; close any Resolved ticket; view all reports and audit logs. |

The API enforces permissions. Hiding a control in React is not authorization.
Users are deactivated rather than hard-deleted so ticket history remains intact.
No role can edit or delete ticket history or audit entries.

## Ticket lifecycle

`Open → Assigned → In Progress → Resolved → Closed`

1. An employee creates a ticket with title, description, and category. It starts
   `Open`, `Medium` priority, unassigned. The employee cannot set priority.
2. An agent may self-assign an Open ticket. An admin may assign or reassign an
   Open, Assigned, or In Progress ticket. Assigning an Open ticket sets it to
   `Assigned`.
3. Only the assigned agent may move `Assigned → In Progress` and
   `In Progress → Resolved`. Resolving requires a nonempty resolution note.
4. The employee who created it or an admin may move `Resolved → Closed`.
   There is no automatic closure or reopening in v1. If a closed issue recurs,
   create a new ticket and reference the old ID.
5. An admin may return `Assigned` or `In Progress` to `Open` by removing the
   assignee. The assigned agent may return `Resolved → In Progress` before
   closure if the fix is incomplete. Other transitions are rejected.

An agent or admin may change priority with a required reason. Every status,
assignee, category, or priority change creates immutable Ticket History with
actor, old/new values, reason where relevant, and UTC time. Important actions
also create Audit Log entries. Comments and attachments remain after closure.
No hard deletion of tickets in v1.

## Priority and SLA

SLA time is measured in **calendar hours** from ticket creation, including
nights and weekends. The first public comment from the assigned agent counts as
a response;
assignment alone does not. Resolution time is when status first becomes
  `Resolved`. If a ticket returns to In Progress, its previous resolution no
  longer counts; the next Resolved transition supplies the resolution time.

| Priority | First response within | Resolution within |
| --- | ---: | ---: |
| Low | 24 hours | 72 hours |
| Medium | 8 hours | 48 hours |
| High | 2 hours | 24 hours |
| Critical | 1 hour | 8 hours |

These are seeded defaults editable by an admin. Each ticket stores the targets
applied at creation, so later settings changes do not rewrite old deadlines.
A breach marks the ticket overdue, appears on dashboards/reports, and creates
an in-app notification for the assignee or admins. It does not automatically
change priority, status, or assignee.

## Notifications and live updates

In-app notifications are created for assignment/reassignment, a new comment,
resolution, closure, and SLA breach. Email is not required in v1. The React UI
refreshes ticket and notification data every 15 seconds while open, without a
manual reload. This is the agreed local-demo meaning of "real-time updates";
WebSocket/SSE is optional later.

## Knowledge base, attachments, reports, and settings

- Knowledge articles: agents can create/edit drafts; admins can publish,
  unpublish, and edit any article. Employees search/read published articles.
  The architecture picture shows the UI but not its API/table; both are needed.
- Attachments: authorized users can upload/download PDF, PNG, JPEG, or TXT up
  to 10 MB per file. Store bytes in a local directory outside the public web
  folder and metadata in PostgreSQL. Generate storage names; never trust a
  client-supplied path. No deletion in v1.
- Dashboards: ticket counts by status/priority, overdue counts, and agent
  workload. Employees see only their tickets; agents/admins see support data.
- Reports: agents/admins filter by creation date, status, priority, category,
  and assignee and export results as CSV or PDF. Employees use their own-ticket
  dashboard rather than the support report.
- Settings: admin edits SLA targets and attachment limits; changes are audited.

## System boundaries

- React responsive web app with role-specific screens.
- FastAPI `/api/v1` REST API; see [API_CONTRACT.md](API_CONTRACT.md).
- SQLAlchemy models/transactions and locally running PostgreSQL.
- JWT access and refresh tokens; role checks on protected API routes.
- Swagger/OpenAPI docs, Postman examples, Pytest tests, and Git.
- All services run locally, with no cloud dependency.

## Decisions that may be revised

These are working team choices, not claims that the workbook specifies them:
calendar-hour SLA targets; no reopen or automatic closure; in-app-only
notifications; 15-second polling; attachment limits; and article approval.
Record the date, reason, and resulting API/test changes for any revision.
