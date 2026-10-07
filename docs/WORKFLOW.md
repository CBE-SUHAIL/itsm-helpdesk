# Two-person relay workflow

Suhail and Kavin work on the same project **one person at a time**. GitHub is
the source of truth. An agent's chat history is not: the next agent must be
able to continue from the repository alone.

## Branches and handoff

- Keep `main` stable. Use one shared branch per checklist task, such as
  `docs/F02-requirements` or `feat/T01-ticket-api`. Do not create competing
  branches for the same unfinished task.
- Before touching files, the incoming person checks Git status and pulls the
  current branch with `git pull --ff-only`. If this fails, stop and resolve the
  divergence together. Never force-push or discard the other's work.
- Only the person named **Active owner** in [HANDOFF.md](HANDOFF.md) edits the
  task branch. At a stated handoff trigger, the named incoming owner becomes
  active after pulling that pushed commit. The other person may read and
  discuss but waits to code.
- **Before every push**, update `docs/HANDOFF.md` with what changed, checks,
  blockers, and the exact next action. Commit code and handoff note together,
  then push. Tell the next person the branch name and commit hash. The next
  person pulls before editing and becomes Active owner in the next handoff.
- Work that has not been pushed is **not handed over**. The other person must
  not code from an older remote version.
- Every agent reads `AGENTS.md`, `docs/HANDOFF.md`, `docs/REQUIREMENTS.md`, and
  `docs/API_CONTRACT.md`, then checks branch/status/commit before editing.

## Incoming person's Git commands

On a new computer, clone once, then open an agent in that folder:

```bash
git clone https://github.com/CBE-SUHAIL/itsm-helpdesk.git
cd itsm-helpdesk
```

At the current F02 handoff:

```bash
git status
git fetch origin
git switch docs/F02-requirements
git pull --ff-only origin docs/F02-requirements
```

For a branch not yet present locally, use
`git switch --track origin/docs/F02-requirements` instead of `git switch`.
For later tasks, replace `docs/F02-requirements` with the branch named in
`docs/HANDOFF.md`.

If `git status` shows uncommitted work, do not pull over it. Ask the outgoing
person what it is. Never commit passwords, API keys, or real employee data.
Only the named Active owner pushes changes to the task branch.

## Review and integration

When a task is ready, open a pull request from the shared task branch into
`main`. The other teammate reviews the code and test evidence. Merge after
review, then both pull `main` before starting the next branch. Avoid direct
commits to `main`. Update the checklist and evidence link after merge. Use the
Mentor Updates sheet every Monday, Wednesday, and Friday.

The first small PR should verify F01: both can pull, branch, push, review,
and merge without overwriting each other.

## Pull request checklist

- [ ] Task ID and intended behavior are clear.
- [ ] Relevant checks ran; results are stated.
- [ ] Permissions/data handling were checked where relevant.
- [ ] `docs/HANDOFF.md` describes the resulting state.
- [ ] The other teammate reviewed the change.
- [ ] The project checklist is updated after merge.
