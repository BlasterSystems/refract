---
name: deploy-prd
description: Ship to production - optionally merge a reviewed pull request, sync the default branch, create and push the configured production tag, and verify the deployment. Run only when the user explicitly asks.
---

# Deploy to Production

Run only when the user explicitly asks to deploy to production. Merging and tagging change shared state and start a real deployment; every step that does so needs explicit confirmation.

## Steps

1. **Read `docs/DEPLOYMENT.md`.** If it says `Status: UNCONFIGURED`, or the prd row, merge strategy, pipeline, verification, or rollback sections are not configured, stop and help the user fill them in.
2. **Optional pull request merge.** When the user gives a pull request URL or number:
   - Inspect it first: state open, not a draft, targets the default branch, mergeable, and all required checks green. Report failing checks by name and stop; never merge a failing pull request unless the user explicitly overrides.
   - Show the title, branches, checks, and the tag that will follow, then ask for confirmation.
   - Merge with the configured strategy and delete the merged branch. Stop if the merge fails.
3. **Sync the default branch**: `git checkout <default>` and `git pull --ff-only`. Stop and ask if it cannot fast-forward.
4. **Run the pre-deploy gates** listed in `docs/DEPLOYMENT.md`. Production deploys come from the default branch; warn and ask if the current branch is anything else.
5. **Compute the tag** exactly as `deploy-dev` does, using the prd pattern, and validate it against the configured regex.
6. **Confirm with the user** (tag, commit, pipeline), then create and push the tag. If the push fails, stop: do not update tickets or documents.
7. **Watch the pipeline** and **verify** with the configured artifact invariants and functional probes. On failure, report it and point to the rollback section; do not roll back without the user's decision.
8. **Close the loop**: record deploy evidence on the ticket and, when the user confirms, complete the ticket lifecycle in `docs/DEVELOPMENT_PROCESS.md`.
9. **Report** the merged pull request, default-branch commit, tag, pipeline result, verification results, and ticket status.
