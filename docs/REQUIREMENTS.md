# ITSM requirements draft

Status: Draft for Suhail, Kavin, and mentor review. The project will implement the
full architecture diagram. The choices marked **Decision needed** must be agreed
before the related feature is coded.

## Users and permissions

| Role | Proposed access | Decision needed |
| --- | --- | --- |
| Employee | Create tickets; view, comment on, and attach files to own tickets; read published knowledge articles and own notifications. | Can an employee close or reopen a ticket? |
| Support agent | View and work on assigned tickets; update status, comments, attachments, and resolution; view support dashboard. | Can agents self-assign any open ticket or only receive assignments? |
| Admin | Manage users, roles, categories, system settings, knowledge articles, and all tickets; view reports and audit logs. | Can admins edit or delete ticket history? Proposed answer: no. |

The API must enforce these permissions. Hiding a button in React is not sufficient.

## Ticket workflow

The diagram defines `Open → Assigned → In Progress → Resolved → Closed`.

| Event | Proposed rule | Decision needed |
| --- | --- | --- |
| Create | Employee submits title, description, and category; ticket starts Open. | Is priority chosen by the employee, agent, or a rule? |
| Assign | Agent or admin becomes the assignee; status becomes Assigned. | Who may assign or reassign? |
| Start work | Assignee moves Assigned to In Progress. | May the ticket return to Open or Assigned? |
| Resolve | Assignee records a resolution note and moves to Resolved. | Is a resolution note required? |
| Close | Ticket moves to Closed after confirmation or a defined delay. | Who closes it, and can it be reopened? |

Every status, priority, and assignee change must create a Ticket History entry with
the actor, old value, new value, and time. Important actions also create Audit Log
entries. Comments and attachments stay linked to the ticket.

## Priority and SLA

The architecture includes priority and SLA tracking. Agree on the priority names,
response deadline, resolution deadline, and whether time is counted in business
hours or calendar hours. The app should show an overdue state and report overdue
tickets. **Decision needed:** What action, if any, occurs when an SLA is breached?

## Notifications and updates

The architecture includes notifications and a user interface that updates without
manual reload. Proposed notification events are assignment, reassignment, new
comment, resolution, closure, and SLA breach. **Decision needed:** Are notifications
inside the app only, or must email also be sent? What update method and delay are
acceptable for the local demonstration?

## Knowledge base, attachments, and reports

- Knowledge base: published articles can be searched and read by employees;
  admins can create, edit, publish, and unpublish. The diagram shows a UI page but
  no article API or table, so those must be added for the page to function.
- Attachments: authorized users can upload and download ticket files. Agree on
  allowed types, maximum size, and local storage location before coding.
- Dashboard and reports: show ticket counts, status and priority breakdowns,
  overdue SLA counts, and agent workload. Agree on exact metrics, date filters,
  and CSV/PDF content before implementing exports.
- System settings: admin can edit the settings needed by the agreed rules, such
  as SLA targets and attachment limits. Changes are audited.

## System boundaries

- React web application for employee, support agent, and admin screens.
- FastAPI REST API for authentication, users, tickets, categories, comments,
  attachments, knowledge articles, notifications, dashboard, reports, settings,
  and audit history.
- SQLAlchemy models and transactions against local PostgreSQL.
- JWT authentication and role checks on protected API routes.
- Swagger documentation, Postman API testing, Pytest tests, Git version control,
  and a fully local setup without a cloud dependency.

## Questions to resolve before implementation

- [ ] Confirm the three roles and their exact permissions.
- [ ] Confirm valid ticket transitions, assignment, closure, and reopening rules.
- [ ] Confirm priority levels, SLA targets, time calculation, and breach behavior.
- [ ] Confirm notification channels and trigger events.
- [ ] Confirm attachment restrictions and storage.
- [ ] Confirm knowledge article approval and publishing rules.
- [ ] Confirm dashboard metrics, report filters, and CSV/PDF content.
- [ ] Confirm what “real-time updates” means for the local demonstration.

Record decisions here with the date and mentor's response before changing these
proposals into implementation rules.
