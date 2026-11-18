---
name: hotfix
description: Emergency production fix - minimal change on a hotfix branch from the default branch, full checks, expedited pull request, then dev and production deployment through the deploy skills.
---

# Hotfix

Use for urgent production defects only.

1. **Start from the default branch**: check it out and pull with `--ff-only`, then create `hotfix/<short-description>`.
2. **Record the incident** in `tasks/INCIDENT-<id>.md` from `tasks/task-template.md`: symptom, impact, start time, suspected cause.
3. **Implement the smallest fix** that resolves the defect. No refactoring, no adjacent changes, no features.
4. **Add a regression test** that fails without the fix.
5. **Run the checks**: `.refract/bin/validate`, the configured test and build commands, and the `security-check` skill. A hotfix does not skip checks.
6. **Open an expedited pull request** titled `fix: <description> (HOTFIX)` that links the incident file, and request immediate review.
7. **After merge**, deploy with `deploy-dev` to validate, then `deploy-prd`. Both skills require `docs/DEPLOYMENT.md` to be configured and ask for confirmation.
8. **Follow up** in the incident file: root cause, verification evidence, and preventive actions (tests, monitoring, ADR if a durable decision changed).
