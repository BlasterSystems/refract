# OpenCode

Taken from refract 0.3.1's OpenCode adapter (verified 2026-11-18 against OpenCode 1.19.5).

## Always

- **Instructions.** `AGENTS.md`, read natively.
- **Skills.** `.agents/skills`, read natively.
- **Invocation.** One slash command per skill, `.opencode/commands/<skill>.md`:

  ```markdown
  ---
  description: "<the skill's description, as a JSON-quoted string>"
  agent: plan
  ---

  Load and follow the `<skill>` skill for this request.

  $ARGUMENTS
  ```

  Keep `agent: plan` only for the advisory skills (`docs-check`, `security-check`, `quality-review`, `process-check`), so they run read-only. Leave it out for every other skill.
- **`opencode.json`.** Write it through a JSON serializer, merging into an existing file and showing the diff:

  ```json
  {
    "$schema": "https://opencode.ai/config.json",
    "permission": {"edit": "ask", "bash": "ask"},
    "agent": {"plan": {"permission": {"edit": "deny"}}}
  }
  ```

  The agent-scoped deny keeps `plan` read-only. OpenCode applies the last matching rule, so the project-level `edit: ask` would otherwise override it.

## Only when selected

- **Permissions.** Add `"read": {"*": "allow", "*.env": "deny", "*.env.*": "deny"}` under `permission`. Tell the user that grep and shell commands can still read `.env`.
- **Subagents.** `.opencode/agents/architecture-reviewer.md`:

  ```markdown
  ---
  description: Reviews architecture impact and ADR quality without editing files
  mode: subagent
  permission:
    edit: deny
    bash: deny
  ---

  Read `docs/adr/README.md` first, then only ADRs relevant to the current scope. Review decision drivers, alternatives, consequences, security boundaries, migration, rollback, validation, and supersession links. Do not edit files. Report findings with file references.
  ```
- **MCP.** Add `"mcp": {"context7": {"type": "remote", "url": "https://mcp.context7.com/mcp", "enabled": true}}` to `opencode.json`.
- **Hooks.** OpenCode hooks are JavaScript plugins, the only code this setup writes. Skip the hook if there is no test command. Write `.opencode/plugins/refract-check.js`, with the confirmed test command as a JSON string literal:

  ```js
  // refract end-of-turn check: runs the project's test command when a session goes idle.
  const TEST_COMMAND = "<TEST_COMMAND as a JSON string>"
  export const RefractCheck = async ({ $, directory }) => ({
    event: async ({ event }) => {
      if (event.type !== "session.idle") return
      const result = await $`sh -c ${TEST_COMMAND}`.cwd(directory).nothrow().quiet()
      if (result.exitCode !== 0) console.error(`refract: test command failed: ${TEST_COMMAND}`)
    },
  })
  ```

## Support row

| OpenCode | Enabled | `AGENTS.md` | `.agents/skills` | `.opencode/commands/<skill>.md` | `opencode.json` permission (Read tool denied on `.env`; grep and shell can still read) | `AGENTS.md` | `.opencode/agents/*.md` | `opencode.json` mcp | `.opencode/plugins/refract-check.js` (session.idle) |
