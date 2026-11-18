# Generated Output

This is the exact renderer output when all platforms and optional features are enabled. It is checked by `tests/golden/all-platforms/tree.txt`.

```text
.agents/skills/architecture-decision/SKILL.md
.agents/skills/docs-check/SKILL.md
.agents/skills/refract/SKILL.md
.agents/skills/semantic-versioning/SKILL.md
.claude/agents/architecture-reviewer.md
.claude/skills/architecture-decision/SKILL.md
.claude/skills/docs-check/SKILL.md
.claude/skills/refract/SKILL.md
.claude/skills/semantic-versioning/SKILL.md
.codex/agents/architecture-reviewer.toml
.codex/config.toml
.githooks/pre-commit
.github/workflows/docs-check.yml
.mcp.json
.omp/RULES.md
.opencode/agents/architecture-reviewer.md
.opencode/commands/adr-new.md
.opencode/commands/docs-check.md
.refract/bin/docs-check
.refract/bin/validate
.refract/config.json
AGENTS.md
CLAUDE.md
docs/AGENT_GUIDED.md
docs/ARCHITECTURE.md
docs/DEVELOPMENT_PROCESS.md
docs/PLATFORM_SUPPORT.md
docs/README.md
docs/RELEASING.md
docs/SECURITY_AUDIT.md
docs/TASK_BREAKDOWN.md
docs/adr/README.md
docs/adr/template.md
opencode.json
setup-hooks.sh
tasks/task-template.md
```

`.refract/manifest.json` is written only after a successful apply and is not renderer output. The project-scoped `refract` skill is advisory and does not install a user-scoped skill or authorize apply. New projects do not receive `.codex.md` or `.claude/claude.json`.
