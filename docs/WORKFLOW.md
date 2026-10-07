# Team workflow

Suhail and Kavin use this workflow for each checklist item.

1. Pick one task ID and agree on its owner and reviewer.
2. Start from the latest `main` and create a branch such as `feat/T01-ticket-api`,
   `fix/T02-status-rule`, or `docs/F02-requirements`.
3. Make small commits that mention the task ID, for example
   `T01: add ticket creation endpoint`.
4. Run the checks relevant to the change and add the result to the pull request.
5. Open a pull request into `main`. Describe what changed, how it was tested,
   and link a screenshot or API example when useful.
6. The other teammate reviews the change. The author fixes any requested
   changes, then merges after approval.
7. Update the checklist status and evidence link. Use the Mentor Updates sheet
   every Monday, Wednesday, and Friday to report completed work and blockers.

`main` is the working integration branch. Avoid committing directly to it after
the initial repository setup. Do not force-push shared branches. Keep local
configuration and secrets out of Git; commit an example configuration instead.

## Pull request checklist

- [ ] The task ID and intended behavior are clear.
- [ ] The change was tested locally.
- [ ] Security and role permissions were checked where relevant.
- [ ] Screenshots or API examples are attached when they help review.
- [ ] The other teammate reviewed the change.
- [ ] The project checklist is updated after merging.

