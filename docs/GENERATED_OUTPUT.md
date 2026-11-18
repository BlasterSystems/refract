# Generated Output

This is the exact renderer output when all platforms and optional features are enabled. It is checked by `tests/golden/all-platforms/tree.txt`.

```text
.agents/skills/architecture-decision/SKILL.md
.agents/skills/commit/SKILL.md
.agents/skills/confidence-check/SKILL.md
.agents/skills/deploy-dev/SKILL.md
.agents/skills/deploy-prd/SKILL.md
.agents/skills/docs-check/SKILL.md
.agents/skills/hotfix/SKILL.md
.agents/skills/implement/SKILL.md
.agents/skills/quality-review/SKILL.md
.agents/skills/refract/SKILL.md
.agents/skills/research/SKILL.md
.agents/skills/security-check/SKILL.md
.agents/skills/semantic-versioning/SKILL.md
.claude/agents/architecture-reviewer.md
.claude/settings.json
.claude/skills/architecture-decision/SKILL.md
.claude/skills/commit/SKILL.md
.claude/skills/confidence-check/SKILL.md
.claude/skills/deploy-dev/SKILL.md
.claude/skills/deploy-prd/SKILL.md
.claude/skills/docs-check/SKILL.md
.claude/skills/hotfix/SKILL.md
.claude/skills/implement/SKILL.md
.claude/skills/quality-review/SKILL.md
.claude/skills/refract/SKILL.md
.claude/skills/research/SKILL.md
.claude/skills/security-check/SKILL.md
.claude/skills/semantic-versioning/SKILL.md
.codex/agents/architecture-reviewer.toml
.codex/config.toml
.codex/hooks.json
.githooks/pre-commit
.github/PULL_REQUEST_TEMPLATE.md
.github/workflows/docs-check.yml
.mcp.json
.omp/RULES.md
.omp/agents/architecture-reviewer.md
.omp/hooks/post/refract-check.ts
.omp/mcp.json
.omp/settings.json
.opencode/agents/architecture-reviewer.md
.opencode/commands/architecture-decision.md
.opencode/commands/commit.md
.opencode/commands/confidence-check.md
.opencode/commands/deploy-dev.md
.opencode/commands/deploy-prd.md
.opencode/commands/docs-check.md
.opencode/commands/hotfix.md
.opencode/commands/implement.md
.opencode/commands/quality-review.md
.opencode/commands/refract.md
.opencode/commands/research.md
.opencode/commands/security-check.md
.opencode/commands/semantic-versioning.md
.opencode/plugins/refract-check.js
.refract/bin/agent-check
.refract/bin/deploy-ready
.refract/bin/docs-check
.refract/bin/validate
.refract/config.json
AGENTS.md
CLAUDE.md
docs/AGENT_GUIDED.md
docs/ARCHITECTURE.md
docs/DEPLOYMENT.md
docs/DEVELOPMENT_PROCESS.md
docs/PLATFORM_SUPPORT.md
docs/README.md
docs/RELEASING.md
docs/SECURITY_AUDIT.md
docs/TASK_BREAKDOWN.md
docs/adr/README.md
docs/adr/template.md
docs/branches/README.md
opencode.json
setup-hooks.sh
tasks/task-template.md
```

`.refract/manifest.json` is written only after a successful apply and is not renderer output. The project-scoped `refract` skill is advisory and does not install a user-scoped skill or authorize apply. New projects do not receive `.codex.md` or `.claude/claude.json`.

## Retrofit conflicts

A generated path that already holds an unmanaged file, such as a hand-written skill named `research` or `commit`, an existing `docs/DEPLOYMENT.md`, or (with `--github`) an existing `.github/PULL_REQUEST_TEMPLATE.md`, is reported as a conflict. The apply then stops without changing anything; refract never overwrites it. Run the retrofit with `--keep-existing` to keep such files as project-owned. Kept skills replace refract's copies on every platform (ADR-0012, `docs/MIGRATION.md`).
