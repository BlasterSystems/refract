# ADR-0012: Keep-existing retrofit mode

- **Status:** Proposed
- **Date:** 2026-11-18
- **Decision owners:** Not assigned
- **Scope:** Retrofit planning and ownership
- **Tags:** retrofit, ownership, migration, skills, safety
- **Supersedes:** None
- **Superseded by:** None

## Context

Retrofit is all-or-nothing: any unmanaged file at a generated path is a conflict, and the apply stops without changing anything (ADR-0003). Projects with an existing agent setup almost always have such files: `AGENTS.md`, `CLAUDE.md`, a process document, and skills with generic names such as `research` or `implement` (ADR-0011).

A dry run against the reference project produced 8 conflicts, so that project could not adopt refract without first deleting its own files.

There is a second problem: keeping a project's skill in one location while refract generates the same skill elsewhere splits behaviour between agents. Claude Code would load the project's `.claude/skills/research`, Codex, OpenCode and omp would load refract's `.agents/skills/research`, and omp would load both under namespaced names.

## Decision drivers

- Never overwrite or adopt unmanaged files (AGENTS.md rule 4, ADR-0003).
- Let real projects adopt refract incrementally, without deleting their own configuration first.
- Every selected agent must see one version of each skill.
- Keep the default safe and explicit; the new behaviour is opt-in.

## Considered options

### Option 1: Opt-in keep-existing mode with skill-group consistency (selected)

`--keep-existing` plans each conflicting unmanaged file as `SKIP_UNMANAGED`: it is kept and not adopted into the manifest. For every kept skill, the other generated copies of that skill are planned as `SKIP_KEPT` (not created), so all agents use the project's version.

### Option 2: Adopt existing files into the manifest

This would claim user content as generated, making later updates overwrite it, which contradicts ADR-0003.

### Option 3: Per-path interactive prompts

Precise, but unusable for agent-guided and non-interactive runs, and not deterministic for plan identifiers.

## Decision

Adopt Option 1.

- Without the flag, behaviour is unchanged. The conflict detail now points to `--keep-existing`.
- `--keep-existing` is recorded in the plan document, so it is bound to the plan identifier.
- Edited refract-owned files, symlinks and non-regular files still conflict.
- Retrofit prints migration findings about the existing setup. They are read from file names, git tracking and the `CLAUDE.md` import line, never from other file contents:
  - committed personal settings,
  - non-functional configuration files,
  - Pi directories,
  - Claude-only skills,
  - context-file drift.

## Consequences

### Positive

- Projects with existing agent setups can adopt the parity layer and the workflow skills in one pass.
- Agents stay consistent when a project keeps its own skills.

### Negative

- A kept skill or settings file means that platform does not receive refract's version. For example, a kept `.claude/settings.json` means no Claude hooks. The plan warns about each case.

### Risks and mitigations

- Users may keep outdated process documents. The findings and `docs/MIGRATION.md` explain how to merge in the generated seeds.

## Implementation and validation

1. `build_plan(..., keep_existing=True)`, `Action.SKIP_KEPT` and `skill_group` in `src/refract/planner.py`; plumbing in the facade, protocol and CLI; findings in `src/refract/migration.py`.
2. Tests in `tests/integration/test_keep_existing.py`: default conflicts, kept files, group consistency, never-adopted ownership, idempotent re-runs, edited refract-owned files, findings, and CLI output.
3. Evidence: on a temporary clone of the reference project, the default dry run found 8 conflicts. `--keep-existing` kept 8 files, skipped 10 sibling copies, applied, and passed `.refract/bin/validate`.

## Revisit triggers

- Users need to keep some conflicting files and adopt others in one run.
- A supported agent changes how it ranks duplicate skills.

## References

- ADR-0003, ADR-0010, ADR-0011
- `docs/MIGRATION.md`
