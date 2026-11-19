# Development Process

## Purpose

Use this workflow for changes to **{{PROJECT_NAME}}**. Scale the ceremony to the risk and size of the task, but do not skip validation or explicit architectural decisions.

## Skill workflow

The portable project skills implement this process. Invoke them by name on any supported coding agent.

| Stage | Skill | Output |
|---|---|---|
| Idea or epic, no code yet | `research` | `tasks/research-<slug>.md`; tracker tickets only after approval |
| Readiness | `confidence-check` | Readiness result in the task file |
| One ticket | `implement` | Task file, branch, tested change, pull request |
| Security | `security-check` | CRITICAL / WARNING / INFO report |
| Adversarial review | `quality-review` | Independent review that tries to break the change: verdict, verified findings, claims that survived |
| Commit | `commit` | Conventional commit and updated branch document |
| Deploy | `deploy-dev`, `deploy-prd` | Tag, pipeline result, verification evidence |
| Emergency | `hotfix` | Minimal fix through the full checks |
| Decisions | `architecture-decision` | Indexed ADR |
| Release version | `semantic-versioning` | Release commit and annotated tag |

Deploy skills act only on explicit request and only after the readiness check in `docs/DEPLOYMENT.md` passes.

## 1. Understand

- Read the request and acceptance criteria.
- Inspect relevant code and current documentation.
- Identify unknowns, risks, and affected components.
- Confirm assumptions that could materially change the solution.

## 2. Plan

- Create or update a task file from `tasks/task-template.md`.
- Break work into independently verifiable steps.
- For multi-step or ambiguous work, use the planning-and-task-breakdown skill; the task list target and tracker mapping are defined in `docs/TASK_BREAKDOWN.md`.
- Record expected tests and documentation changes.
- Decide whether the task has architectural impact.
- To re-run or upgrade the agent setup itself, use the `refract` skill.

## 3. Architecture Decision Check

An ADR is normally required for cross-cutting, durable, security-sensitive, data-model, deployment, foundational dependency, or external integration decisions.

If required:

1. Read `docs/adr/README.md`.
2. Load only relevant ADRs.
3. Copy `docs/adr/template.md` to the next available four-digit ID.
4. Complete options, consequences, validation, and revisit triggers.
5. Add the proposed ADR to the index.
6. Obtain the required decision approval before treating it as Accepted.

Routine refactors and local implementation details do not require ADRs.

## 4. Implement

- Keep the change focused and consistent with established patterns.
- Avoid unrelated cleanup.
- Keep one writer for overlapping files when agents are used.
- Never hide failures by weakening tests or security controls.

## 5. Validate

Run applicable commands:

1. The `process-check` skill.
2. `{{TEST_COMMAND}}`
3. `{{BUILD_COMMAND}}`
4. The `docs-check` skill.

Skip commands marked “Not configured”; record the missing configuration instead of executing that text.

## 6. Review

Review the diff for correctness, security, compatibility, test coverage, documentation, and unnecessary complexity. Update the task file with evidence and residual risks.

Open a pull request for reviewable changes. **Every pull request gets an independent adversarial review before merge**, using the `quality-review` skill:
- It runs in a fresh, read-only context that does not share the author's reasoning.
- It assumes the change is wrong, and tries to disprove its correctness, security, compatibility, and scope claims.
- It reports only findings it has verified.

Scale the depth to the size and risk of the change, but never skip it. A self-review is not independent: if no fresh context is available, a human reviews before merge. Every `BLOCK` finding is resolved before merge.

For security-sensitive changes or open vulnerability questions, use the security-audit skill in guidance mode; see `docs/SECURITY_AUDIT.md`.

## 7. Deploy

Deployments follow `docs/DEPLOYMENT.md`. Deploy-affecting changes name an artifact invariant and a functional probe before merge, and every deployment records both results as evidence. A configuration change made outside the pipeline is a deploy.

## 8. Complete

- Ensure acceptance criteria are met.
- Ensure new or superseding ADRs are indexed and linked.
- Confirm generated configuration still validates.
- Provide a concise summary of changes, validation, and remaining risks.
- Before tagging a release that touches security-relevant surfaces, run the scoped release-gate audit described in `docs/SECURITY_AUDIT.md`.
- For a version bump or release, follow `docs/RELEASING.md` with the `semantic-versioning` skill; obtain explicit confirmation before creating the release commit or tag.

{{TICKET_LIFECYCLE}}
