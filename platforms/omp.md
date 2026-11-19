# OhMyPi (omp)

Taken from refract 0.3.1's omp adapter (verified 2026-11-18 against omp 18.22.2).

## Always

- **Instructions.** `AGENTS.md`, read natively.
- **Skills.** `.agents/skills`, read natively. omp ranks `.claude/skills` above `.agents/skills`. When Claude Code is also selected, `.claude/skills` must be a link to `.agents/skills` or an identical copy (see `claude.md`).
- **Invocation.** `/skill:<skill>`, registered automatically.
- **`.omp/RULES.md`.** Sticky rules:

  ```markdown
  # Invariants

  Never expose credentials or weaken security controls to make a task pass.

  Changes to the agent setup go through the `refract` skill, which shows every diff to an existing file and waits for approval.

  Follow `docs/DEVELOPMENT_PROCESS.md`: pull requests for reviewable changes, independent adversarial review before merge, ADRs for durable decisions.
  ```
- **`.omp/settings.json`.** Always contains `{"autolearn": {"enabled": false}}`. Auto-learn creates user-scope skills from this project's sessions, which then load into every other project. This setting is about project scope, not permissions, so it is not optional.

## Only when selected

- **Permissions.** Add `"tools": {"approvalMode": "always-ask"}` to `.omp/settings.json`. Tell the user three things:
  - Reads are approved automatically.
  - Task subagents run without approvals.
  - `.env` files are not protected.
- **Subagents.** `.omp/agents/architecture-reviewer.md`:

  ```markdown
  ---
  name: architecture-reviewer
  description: Read-only reviewer for architecture impact, ADR quality, and cross-component risks.
  tools: read, grep, find, glob
  ---

  Review architecture-related changes without editing files. Read `docs/adr/README.md` first, then only relevant ADRs. Check decision drivers, alternatives, consequences, security boundaries, migration, rollback, validation, and supersession links. Report findings with file references.
  ```
- **MCP.** `.omp/mcp.json`: `{"mcpServers": {"context7": {"type": "http", "url": "https://mcp.context7.com/mcp"}}}`. omp also reads the root `.mcp.json`, so when Claude Code MCP is also selected the server is declared twice. Tell the user.
- **Hooks.** omp hooks are TypeScript files. Skip the hook if there is no test command. Write `.omp/hooks/post/refract-check.ts`, with the confirmed test command as a JSON string literal:

  ```ts
  // refract end-of-turn check: runs the project's test command after each agent run.
  import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";
  const TEST_COMMAND = "<TEST_COMMAND as a JSON string>";
  export default function (pi: HookAPI) {
  	pi.on("agent_end", async (_event, ctx) => {
  		const { code } = await pi.exec("sh", ["-c", TEST_COMMAND], { cwd: ctx.cwd, timeout: 120_000 });
  		if (code !== 0 && ctx.hasUI) ctx.ui.notify(`refract: test command failed: ${TEST_COMMAND}`, "warning");
  	});
  }
  ```

## Support row

| OhMyPi (omp) | Enabled | `AGENTS.md` | `.agents/skills` | `/skill:<skill>` | `.omp/settings.json` tools.approvalMode (reads auto-approved; task subagents run without approvals; autolearn always disabled) | `.omp/RULES.md` | `.omp/agents/*.md` | `.omp/mcp.json` | `.omp/hooks/post/refract-check.ts` (agent_end) |
