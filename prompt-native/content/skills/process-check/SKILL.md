---
name: process-check
description: Check that this project's agent instructions, docs, ADRs, and skills are structurally sound. Use before committing, after changing ADRs or skills, and at the end of a refract setup.
---

# Process Check

A read-only checklist. Report every failure with its file and line; do not fix anything without being asked. A pass means the structure is sound, not that the content is right.

## Instructions and docs

1. `AGENTS.md` exists and has these sections: `## Project`, `## Working Agreement`, `## Progressive Disclosure`, `## Architecture Decisions`, `## Validation`.
2. Every file path named in the `AGENTS.md` progressive-disclosure table exists.
3. No file contains a leftover setup placeholder: two opening curly braces, an upper-case name with underscores, and two closing curly braces. GitHub expressions that start with `${{` are not placeholders.
4. If a `CLAUDE.md` exists, it contains the line `@AGENTS.md`. Claude Code otherwise ignores `AGENTS.md`.

## Portable core stays provider-neutral

5. `AGENTS.md`, `docs/`, `tasks/`, and `.agents/skills/` do not mention `mcp__`, `Task tool`, `.claude/`, `.codex/`, `.opencode/`, or `.omp/`. Platform-specific instructions belong in the platform files.

## Skills and agents

6. Each `.agents/skills/<name>/SKILL.md` starts with front matter whose `name` equals `<name>` and whose `description` is not empty.
7. If `.claude/skills` exists, it is a link to `.agents/skills`, or each skill in it is identical to its `.agents/skills` copy. omp prefers `.claude/skills`, so drift silently changes behavior.
8. Agent files (`.claude/agents/*.md`, `.omp/agents/*.md`) have front matter with `name` equal to the file name and a `description`. `.opencode/agents/*.md` and `.opencode/commands/*.md` have a `description`. `.codex/agents/*.toml` have non-empty `name`, `description`, and `developer_instructions`.
9. No skill, agent, command, `CLAUDE.md`, or `.omp/RULES.md` tells the agent to install anything under the user's home directory (`~/.claude`, `~/.codex`, `~/.agents`, `~/.omp`, `~/.config/opencode`, or `$HOME/...`).
10. Every JSON and TOML configuration file parses.

## ADRs (`docs/adr/`)

11. `docs/adr/README.md` exists. Every other ADR file except `template.md` is named `NNNN-short-title.md`, with no duplicate numbers.
12. Each ADR's heading starts with `# ADR-NNNN:` using its own number. It has a valid `Status` (`Proposed`, `Accepted`, `Rejected`, `Deprecated`, `Superseded`) and these sections: `## Context`, `## Decision drivers`, `## Considered options`, `## Decision`, `## Consequences`, `## Implementation and validation`, `## Revisit triggers`, `## References`.
13. Every ADR has an index row whose status and link match the file.
14. Every `Supersedes` and `Superseded by` reference points to an existing ADR:
    - A `Superseded` ADR names its replacement.
    - Only `Superseded` ADRs have a `Superseded by` field.
    - The replacement is `Accepted` and lists the old ADR under `Supersedes`.

## Report

End with `process-check: PASS` or `process-check: FAIL (<n> problems)`, followed by the list.
