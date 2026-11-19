# Claude Code

Checked against code.claude.com/docs/en/memory.md and skills.md on 2026-11-19. Tested with Claude Code 2.1.328 on a greenfield run: `AGENTS.md` loaded with no `CLAUDE.md`, and skills were found through the `.claude/skills` link.

## Always

- **Instructions.** Claude Code v2.1.277 and later reads `AGENTS.md` natively, but only when no `CLAUDE.md`, `.claude/CLAUDE.md`, or `CLAUDE.local.md` exists in the project or any parent folder.
  - If none exists, write nothing.
  - If one exists, it must contain the line `@AGENTS.md`. Propose adding it near the top as an approved diff. The import never makes Claude read `AGENTS.md` twice, and it also covers older versions.
- **Skills.** Claude Code discovers skills only under `.claude/skills/<name>/SKILL.md`, never `.agents/skills/`.
  - If `.claude/skills` does not exist, create it as a relative symbolic link to `.agents/skills`.
  - If the link cannot be created (for example on Windows without developer mode), or `.claude/skills` already exists as a folder, copy each refract skill into it instead. Skills in it that refract did not create are handled by `BOOTSTRAP.md` step 6: one with the same name as a refract skill is set aside, and all others are left alone.
  - Record which option you used in `.refract.md`.
- **Invocation.** `/<skill>`.

## Only when selected

All of these go in `.claude/settings.json`. Merge into an existing file through a JSON serializer and show the diff. Never rewrite a file by hand, and never drop keys you did not add.

- **Permissions.** `"permissions": {"deny": ["Read(./.env)", "Read(./.env.*)"]}`.
- **Hooks.** A `Stop` hook that blocks once when the configured test command fails. Skip it if there is no test command. Put the shell command below into a JSON string with a serializer, because the test command may contain quotes:

  ```json
  {"hooks": {"Stop": [{"hooks": [{"type": "command", "timeout": 120, "command": "<COMMAND>"}]}]}}
  ```

  where `<COMMAND>` is:

  ```sh
  input=$(cat); case "$input" in *'"stop_hook_active":true'*|*'"stop_hook_active": true'*) exit 0;; esac; cd "${CLAUDE_PROJECT_DIR:-$PWD}" && <TEST_COMMAND> >/dev/null 2>&1 && exit 0; printf '%s\n' '{"decision":"block","reason":"The configured test command failed. Run it, fix the failures, then finish."}'
  ```

  The `stop_hook_active` check stops an endless fix loop: on a turn a hook already continued, it lets Claude stop.
- **Subagents.** `.claude/agents/architecture-reviewer.md`:

  ```markdown
  ---
  name: architecture-reviewer
  description: Read-only reviewer for architecture impact, ADR quality, and cross-component risks.
  tools: Read, Grep, Glob
  model: inherit
  ---

  Review architecture-related changes without editing files. Read `docs/adr/README.md` first, then only relevant ADRs. Check decision drivers, alternatives, consequences, security boundaries, migration, rollback, validation, and supersession links. Report findings with file references.
  ```
- **MCP.** `.mcp.json`: `{"mcpServers": {"context7": {"type": "http", "url": "https://mcp.context7.com/mcp"}}}`.

## Support row

| Claude Code | Enabled | `AGENTS.md` (native, or `@AGENTS.md` in `CLAUDE.md`) | `.claude/skills` → `.agents/skills` | `/<skill>` | `.claude/settings.json` | `AGENTS.md` | `.claude/agents/*.md` | `.mcp.json` | `.claude/settings.json` Stop hook |
