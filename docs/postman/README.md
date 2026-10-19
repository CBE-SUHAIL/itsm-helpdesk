# G04 — Postman collection

`itsm-helpdesk.postman_collection.json` exercises the implemented API against a
local backend. It is the manual, explorable counterpart to the pytest suite:
the same flows, visible request by request.

## Run it

1. Start the stack as the [README](../../README.md) describes, including
   `alembic upgrade head` and, for the seeded accounts, `python -m app.seed_demo`.
2. In Postman: **Import** → **File** → choose the JSON in this folder.
3. Open the collection's **Variables** tab and set `employeePassword`,
   `agentPassword`, and `adminPassword` to the password you entered when the D08
   seed asked for one. No password is stored in this repository, and the
   placeholder values here are not real credentials.
4. Run the folders in order, **00** to **09**. Earlier folders write the ids the
   later ones use (`categoryId`, `ticketId`, `secondTicketId`, `attachmentId`,
   `notificationId`), so a folder run on its own may have nothing to act on.
   Requests can also be run one at a time; 01 signs in as each role and stores
   that role's token in `accessToken`.

You can run the whole collection with the Collection Runner. Folder **08** is
the negative-case suite: its requests pass only when the API returns the
documented `400`, `401`, `403`, `404`, `409`, and `422`. Folder **09** logs back
in as admin and exercises articles, settings, dashboard, and CSV/PDF export.

## Two requests need a file

`05.1` uploads an attachment and `08.9` proves a disallowed type is refused.
Postman cannot ship a file with a collection, so select one in each request
before sending: any `.txt`, `.pdf`, `.png`, or `.jpeg` for `05.1`, and anything
else (for example a `.zip` or `.json`) for `08.9`. A local path is deliberately
not committed.

The collection uses synthetic local data and can be rerun. Repeated runs add
another article and other demo records; clear the local demo database only if
you intentionally want a fresh presentation state.
