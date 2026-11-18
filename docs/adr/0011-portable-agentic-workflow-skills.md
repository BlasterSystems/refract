# ADR-0011: Portable agentic workflow skills

- **Status:** Proposed
- **Date:** 2026-11-18
- **Decision owners:** Not assigned
- **Scope:** Generated portable core (skills, process documents, templates)
- **Tags:** skills, workflow, deployment, process, portability
- **Supersedes:** None
- **Superseded by:** None

## Context

refract's purpose is to give old and new projects the agentic development process proven in a production reference project, made generic. That process lives in a chain of skills:

- `research`: idea to evidence-grounded plan, with tickets only after approval.
- `implement`: ticket to tested pull request.
- A readiness gate, a security check, review lenses, and commits that keep a living branch document.
- Tag-driven `deploy-dev` and `deploy-prd` flows with post-deploy verification, plus a hotfix flow.

Before this decision refract generated only four meta-skills (bootstrap, ADRs, docs-check, versioning). The reference project's skills were also mixed with domain, language, cloud and tracker specifics: hard-coded project keys, site URLs, tag suffixes and Confluence pages. The same skills copied into user-level directories leaked into every project on the machine.

## Decision drivers

- Ship the process, not the reference project: no project keys, hosts, languages, cloud providers or tracker APIs in generated skills.
- Keep skills portable: the same `SKILL.md` must serve Claude Code, Codex, OpenCode and omp (ADR-0010). Platform syntax stays out of the portable core.
- Deployment is high-impact and project-specific. Its parameters must live in a project-owned document that the skills read, never in the skills themselves.
- Side effects outside the repository (tickets, merges, tags, pushes) require explicit human confirmation.
- Skills are generated into the project, never into user-level directories.

## Considered options

### Option 1: Generic portable skills plus a project-owned deployment seed (selected)

Ship nine portable skills and a mutable `docs/DEPLOYMENT.md` seed:

- the workflow skills `research`, `confidence-check`, `implement`, `security-check`, `code-review` and `commit`;
- the release skills `deploy-dev`, `deploy-prd` and `hotfix`.

The deploy skills refuse to act while the seed says `Status: UNCONFIGURED`.

### Option 2: Copy the reference project's skills

Fast, but it ships domain, tracker and cloud specifics and hard-coded identifiers to every project.

### Option 3: Document the process only

Put the process in `docs/DEVELOPMENT_PROCESS.md` and ship no skills. This is portable, but agents would not get invocable, step-by-step workflows, so the process would not actually be followed.

## Decision

Adopt Option 1.

- **Skills.** The nine skills join `CORE_SKILLS`. They are rendered to `.agents/skills`, mirrored where a platform needs it, and invocable natively on each platform.
- **Seeds.** `docs/DEPLOYMENT.md` and `docs/branches/README.md` are mutable seeds.
- **Templates.**
  - `tasks/task-template.md` gains an implementation plan, a deployment block, an extended review, and a completion summary.
  - With `--github`, a mutable `.github/PULL_REQUEST_TEMPLATE.md` adds a "Deploy-affecting?" block.
- **Process document.** `docs/DEVELOPMENT_PROCESS.md` gains the skill workflow table and a Deploy section: deploy-affecting changes name an artifact invariant and a functional probe, and configuration changes count as deploys. The generated ticket lifecycle becomes section 9.

## Consequences

### Positive

- New and retrofitted projects get the full research-to-deploy workflow on every supported agent.
- Deployment parameters are reviewed project content. The skills cannot guess tag schemes or pipelines.

### Negative

- Nine more generated skills: a larger tree, and longer skill catalogs in agents.
- Existing projects that already have same-named skills (for example a hand-written `research`) report a retrofit conflict until the owner resolves it.

### Risks and mitigations

- An agent deploying without being asked: the deploy skills state that they run only on explicit request, require a configured `docs/DEPLOYMENT.md`, and confirm before merging, tagging or pushing.
- Tag injection: tag names are validated against a configured regex before use.

## Implementation and validation

1. Skills under `src/refract/templates/core/skills/`, seeds under `templates/core/docs/`, and the pull request template under `templates/integrations/github/`.
2. `CORE_SKILLS` in `src/refract/model.py`; renderer wiring in `src/refract/renderer.py`.
3. Gates: the unittest suite, `refract validate --target .`, portable-token and skill front-matter validation, the golden tree and examples refresh, and the all-platform dry-run preview.

## Revisit triggers

- A supported agent adds a portable way to mark skills as user-invocation-only.
- Retrofit of projects with same-named skills needs an adopt-or-skip mode.
- Deployment patterns beyond tag-driven pipelines need first-class support.

## References

- ADR-0005, ADR-0010
- `docs/DEVELOPMENT_PROCESS.md` (generated), `docs/DEPLOYMENT.md` (generated)
