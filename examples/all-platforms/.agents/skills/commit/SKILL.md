---
name: commit
description: Commit and push the current work with a conventional commit message, keeping the living branch document in docs/branches up to date.
---

# Commit and Push

## Steps

1. **Check the changes**: `git status` and `git diff`. Stop if there is nothing to commit.
2. **Validate**: `.refract/bin/validate` and the configured test command. Do not commit failing work without telling the user.
3. **Update the branch document** at `docs/branches/<branch-name>.md` (see `docs/branches/README.md`). It is a living business document, not a git log: update the affected sections and add one changelog entry, newest first.
4. **Stage explicitly**, file by file. Never stage credentials, `.env` files, local or personal settings, or generated secrets. Warn the user if any such file is part of the change.
5. **Write the message** from the staged diff: `type(scope): summary`, using types such as `feat`, `fix`, `refactor`, `docs`, `test`, `chore`. Reference the ticket key when the project uses one, and add any attribution the project's rules require.
6. **Commit**, then **push** the current branch. Never push directly to the default branch when the process requires pull requests, and never force-push shared branches.
7. **Report** the commit hash, branch, files changed, and the branch-document sections touched.
