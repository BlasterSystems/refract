# Refract Project Summary

**Current release:** 0.3.0  
**Status:** Implemented; acceptance is enforced by the test and validation suites.

## Objective

Bootstrap greenfield or existing software projects with provider-neutral instructions, progressive disclosure, ADRs, safe generated-file ownership, native capability parity across Claude Code, Codex, OpenCode, and OhMyPi (omp), and a portable research-to-deploy agentic workflow. Pi remains selectable but is deprecated.

## MVP capabilities

- Typed Python core with a shell entry point.
- Portable `AGENTS.md` instruction source.
- Native adapter artifacts driven by one capability registry, with warnings for unsupported selections and capability-specific support documentation.
- Portable workflow skills (`research`, `confidence-check`, `implement`, `security-check`, `quality-review`, `commit`, `deploy-dev`, `deploy-prd`, `hotfix`) with a project-owned deployment seed and a deterministic `deploy-ready` gate.
- Deterministic agent end-of-turn hooks with hash-pinned launchers, and a project-scope guard against home and multi-repository targets.
- Indexed ADRs, documentation catalog, shared skills, lifecycle, and validation.
- Semantic Versioning release guidance, changelog maintenance, release commits, and annotated Git tags.
- Dry-run, JSON plans, conflicts, manifests, rollback, and idempotency.
- Optional agent-guided bounded inspection, strict typed proposals, plan-integrity identifiers, and trusted-terminal human handoff.
- Opt-in MCP, agents, permission policies, GitHub workflows, scheduled audits, and Git and agent hooks.
- `--keep-existing` retrofit for projects with existing agent setups, with migration findings (`docs/MIGRATION.md`).
- Unit, integration, golden-tree, and platform contract tests.

The command surface exposes `init`, `retrofit`, read-only `inspect`, and `validate`. Existing agent setups are adopted with `retrofit --keep-existing`; there is no refract-version migration surface beyond ownership-aware re-generation.

## Acceptance evidence

- The test suite passes on Python 3.11, 3.13, and 3.14.
- Repository and generated-project validators pass.
- All platform contract diagnostics pass.
- Wheel build and isolated installed-CLI smoke pass.
- Independent hostile safety and final release-gate reviews pass with no remaining blockers.

## Source of truth

- Architecture: `docs/ARCHITECTURE.md`
- Decisions: `docs/adr/README.md`
- Platform evidence: `docs/PLATFORM_SUPPORT.md`
- Workflow: `docs/DEVELOPMENT_PROCESS.md`
