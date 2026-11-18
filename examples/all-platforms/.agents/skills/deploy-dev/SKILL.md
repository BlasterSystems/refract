---
name: deploy-dev
description: Deploy to the development environment by creating and pushing the configured dev tag, then verify the pipeline, artifact invariants, and functional probes. Run only when the user explicitly asks.
---

# Deploy to Development

Run only when the user explicitly asks to deploy to development. Pushing a tag starts a real deployment.

## Steps

1. **Read `docs/DEPLOYMENT.md`.** If it says `Status: UNCONFIGURED`, or the dev row, pipeline, or verification sections are not configured, stop and help the user fill them in instead of guessing.
2. **Check the source.** Confirm the current branch and commit, that the working tree is clean, and that the commit is pushed. Show them to the user.
3. **Run the pre-deploy gates** listed in `docs/DEPLOYMENT.md`. Stop on any failure.
4. **Compute the tag.** `git fetch --tags`, then find the highest existing tag for today matching the dev pattern and add one (start at 1). Validate the final name against the configured tag regex before using it; refuse anything that does not match.
5. **Confirm with the user**: tag name, commit, and the pipeline it triggers. Proceed only on an explicit yes.
6. **Create and push** the tag on that commit: `git tag <tag> <commit>` and `git push origin <tag>`. If the push fails, stop and report it.
7. **Watch the pipeline** with the configured command until it finishes. Report failing steps by name.
8. **Verify**: run the configured artifact-invariant checks and functional probes, and record the evidence where `docs/DEPLOYMENT.md` says (for example the ticket).
9. **Report** the tag, commit, pipeline result, verification results, and where the evidence was recorded.
