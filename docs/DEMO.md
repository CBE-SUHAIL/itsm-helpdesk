# Local ITSM demo walkthrough

This is a reproducible walkthrough for the final internship presentation. Run
the Quick start in the repository README first, including `python -m
app.seed_demo`. Use synthetic data only. The seed asks for one local password
and creates `demo.employee@example.test`, `demo.agent@example.test`, and
`demo.admin@example.test`. Each person running the project needs their own
`.env`, database container, demo seed, and chosen demo password; none of these
are shared through Git.

1. **Employee:** Sign in, open **My tickets**, and create a ticket with an
   active category. Show that it starts Open, Medium, and unassigned. Add a
   comment and upload a small TXT or PDF file. Open **Dashboard** to see the
   employee's own ticket counts.
2. **Support agent:** Sign out and sign in as the agent. Open **Support queue**,
   find the new ticket with search, and assign it to yourself. Start work,
   reply with a comment, set priority with a reason, and resolve with a
   resolution note. Show the status/history, calculated SLA deadlines, and
   **Notifications** inbox.
3. **Employee:** Sign back in, read the resolution notification, download the
   attachment, and close the Resolved ticket. Search published articles in
   **Knowledge base**. New articles are not visible here until published.
4. **Admin:** Sign in as admin. In **Categories**, add or deactivate a category
   and reactivate it. In **Settings**, review SLA and attachment defaults and
   make a small change. In **Knowledge base**, publish an agent draft. In
   **Audit log**, show the relevant changes. Open **Reports**, filter tickets,
   and download both CSV and PDF.

The dashboard, ticket pages, and inbox refresh while open (15-second polling).
For a deliberately expired SLA deadline, the inbox creates one breach alert
for the assignee, or admins if unassigned, on the next inbox request. This is
request-driven, not a continuously running worker. The CSV/PDF report and
dashboard calculate overdue flags directly from current deadlines.

Before the presentation, run `cd backend && python run_tests.py -q` with PostgreSQL healthy,
then `cd frontend && npm run build && npm run lint`. The backend API docs are at
<http://localhost:8000/docs> and the web app at <http://localhost:5173>.
