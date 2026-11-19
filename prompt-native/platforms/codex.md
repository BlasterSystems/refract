# OpenAI Codex

Taken from refract 0.3.1's Codex adapter (verified 2026-11-18 against Codex 0.169.0). Codex loads the project `.codex/` folder only for trusted projects. Tell the user this when you write anything there.

## Always

- **Instructions.** `AGENTS.md`, read natively. Nothing to write.
- **Skills.** `.agents/skills`, read natively. Nothing to write.
- **Invocation.** `$<skill>` or `/skills`.

## Only when selected

`.codex/config.toml` collects permissions, subagents, and MCP. Merge into an existing file through a TOML-aware edit, and show the diff.

- **Permissions.** Ask before leaving the sandbox; write only inside the workspace; no outbound network from tool commands. Sandboxed edits run without asking, and `.env` files are not protected. Tell the user both.

  ```toml
  approval_policy = "on-request"
  sandbox_mode = "workspace-write"

  [sandbox_workspace_write]
  network_access = false
  ```
- **Subagents.** Add `[agents]` with `enabled = true` and `max_concurrent_threads_per_session = 4` to `config.toml`. Then write `.codex/agents/architecture-reviewer.toml`:

  ```toml
  name = "architecture_reviewer"
  description = "Read-only reviewer for architecture impact, ADR quality, and cross-component risks."
  sandbox_mode = "read-only"
  developer_instructions = """
  Read docs/adr/README.md first, then only relevant ADRs. Review decision drivers, alternatives, consequences, security boundaries, migration, rollback, validation, and supersession links. Do not edit files. Report findings with file references.
  """
  ```
- **MCP.** `[mcp_servers.context7]` with `url = "https://mcp.context7.com/mcp"`.
- **Hooks.** `.codex/hooks.json`. Skip it if there is no test command. `<COMMAND>` is the Claude Code Stop-hook command from `claude.md`, with `cd "$PWD"` in place of `cd "${CLAUDE_PROJECT_DIR:-$PWD}"`. Put it into the JSON string through a serializer.

  ```json
  {"description": "refract end-of-turn test check", "hooks": {"Stop": [{"hooks": [{"type": "command", "timeout": 120, "statusMessage": "refract test check", "command": "<COMMAND>"}]}]}}
  ```

## Support row

| OpenAI Codex | Enabled | `AGENTS.md` | `.agents/skills` | `$<skill>` or `/skills` | `.codex/config.toml` (sandboxed edits run without asking; no `.env` protection; trusted projects only) | `AGENTS.md` | `.codex/agents/*.toml` | `.codex/config.toml` | `.codex/hooks.json` Stop hook (trusted projects only) |
