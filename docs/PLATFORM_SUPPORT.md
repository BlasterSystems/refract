# Platform Support

Last verified: 2026-11-18 against installed CLIs (Claude Code 2.1.327, Codex 0.169.0, OpenCode 1.19.5, omp 18.22.2). Pi was last reviewed 2026-11-09 and is deprecated (ADR-0010).

Capability parity is defined by ADR-0010 and generated from `src/refract/capabilities.py`. A capability a selected platform cannot express produces a CLI warning and an "Unsupported" support row; it is never dropped silently.

| Capability | Claude Code | OpenAI Codex | OpenCode | OhMyPi (omp) |
|---|---|---|---|---|
| Instructions | `CLAUDE.md` importing `AGENTS.md` | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` |
| Skills | `.claude/skills` mirror | `.agents/skills` | `.agents/skills` | `.agents/skills` |
| Skill invocation | `/<skill>` | native skills | `.opencode/commands/<skill>.md` | `/skill:<skill>` |
| Permissions (`--permissions`) | `.claude/settings.json`: Read tool denied on `.env*`; native ask-before-edit/shell mode | `.codex/config.toml`: `on-request`, `workspace-write`, no network for sandboxed commands; no `.env` protection | `opencode.json`: edit/bash ask; Read tool denied on `*.env*` (grep and shell can still read) | `.omp/settings.json`: `tools.approvalMode=always-ask` (reads auto-approved; no `.env` protection) |
| Sticky rules | `CLAUDE.md` | `AGENTS.md` | `AGENTS.md` | `.omp/RULES.md` |
| Subagents (`--agents`) | `.claude/agents/*.md` | `.codex/agents/*.toml` | `.opencode/agents/*.md` | `.omp/agents/*.md` |
| MCP (`--mcp`) | `.mcp.json` | `.codex/config.toml` | `opencode.json` | `.omp/mcp.json` |
| Agent hooks (`--hooks`) | `Stop` hook in `.claude/settings.json` | `Stop` hook in `.codex/hooks.json` | `.opencode/plugins/refract-check.js` (`session.idle`) | `.omp/hooks/post/refract-check.ts` (`agent_end`) |

Every agent hook runs the same deterministic script, `.refract/bin/agent-check`. It executes the project validator and reports the result. It never invokes an LLM. On a validation failure the Claude Code and Codex Stop hooks block once, so the agent fixes the problem before finishing. On a turn a hook has already continued they only report, which prevents fix loops. The OpenCode and omp hooks report.

Permission policies are opt-in. Without `--permissions`, OpenCode keeps its baseline ask-before-edit/shell configuration and the other platforms keep their own defaults. omp projects always receive `.omp/settings.json` with `autolearn.enabled=false`, which stops omp from minting user-scope skills from project sessions.

Agent hooks find the project root by walking up from their working directory, so non-git and monorepo-subdirectory projects work. The Claude Code and Codex Stop hooks pin the SHA-256 of `agent-check` and `validate` and skip the check if either file was modified. They also run Python in isolated mode, so modules planted beside the scripts are ignored. Hash or mode drift of managed files is reported, never blocked on, so an agent is not pushed to revert a deliberate edit.

Platform notes:

- **Codex** loads the project `.codex/` layer (config, hooks, agents) only after the project is trusted.
- **omp** merges `.omp/settings.json` and `.claude/settings.json` into its project settings layer. The Claude-only `permissions` and `hooks` keys do not collide with omp setting ids.
- **omp skill precedence.** omp ranks `.claude/skills` above `.agents/skills`, so when Claude Code and omp are both selected the validators require the two skill copies to stay identical.
- **omp MCP.** omp also reads root `.mcp.json` as a fallback. When `claude` and `omp` are both selected with `--mcp`, the same `context7` server is declared twice, and omp resolves it by provider priority.
- **Pi** is deprecated. It consumes only the portable core, and selecting it prints a deprecation warning.

## Project scope and user-level skills

refract writes only inside the target project. `init` and `retrofit` refuse the home directory, the filesystem root, and any non-repository folder that contains nested git repositories, unless `--allow-unscoped-target` is passed. Run refract inside each project instead. The validators reject generated skills, agents, commands and rules that reference user-level agent configuration directories such as `~/.omp/` or `$HOME/.claude/`. The user-editable `AGENTS.md` is exempt.

Skills that live in user scope load into every project on the machine. The generated omp settings disable auto-learn per project, but refract never deletes user-level files. To clean up after an earlier parent-folder or global install, review and remove the stray entries yourself, for example:

- `~/.omp/agent/skills/<name>` and `~/.agents/skills/<name>`: hand-installed global skills.
- `~/.omp/agent/managed-skills/`: skills minted by omp auto-learn. Set `autolearn.enabled: false` in `~/.omp/agent/config.yml` to stop minting them globally.

## Support contract

Capabilities are classified independently as native, portable fallback, extension-based, unsupported, or unverified. Selecting a platform does not install credentials, models, third-party extensions, optional integrations, or user-scoped skills. The packaged/project-scoped `refract` skill is advisory and stops before apply; pre-bootstrap loading is manual and not claimed as a portable installation contract. The external planning-and-task-breakdown and create-tickets skills are documented and installed on demand (ADR-0007); they are never generated, auto-installed, or manifest-owned.

## Contract validation

Tests validate official file locations, agent front matter, skill-mirror identity, and parse generated JSON/TOML. When the CLIs are installed, contract tests run `claude mcp get`, `codex mcp list --json` (isolated `CODEX_HOME`), `opencode debug config`, and `omp config get`. Provider-authenticated release smoke tests remain a release activity.

## Security defaults

No MCP server, Git hook, repository-host workflow, broad permission grant, or issue tracker is enabled without selection. Hooks never invoke an LLM or perform bootstrap mutation.

`--permissions` applies each platform's strongest native project policy. Protection differs by platform; do not rely on it to keep secrets out of an agent's reach:

- **Claude Code** asks before edits and shell commands; its Read tool is denied on `.env` and `.env.*`. Shell commands the user approves can still read them.
- **Codex** runs commands and edits inside the `workspace-write` sandbox without asking; it asks only to leave the sandbox. Sandboxed commands have no network, but configured MCP servers (for example context7 with `--mcp`) are contacted by Codex itself. Nothing restricts reading `.env` inside the workspace.
- **OpenCode** asks before edits and shell commands; the Read tool is denied on `*.env` and `*.env.*`, but the grep tool and approved shell commands can still read those files. Advisory commands run in the plan agent with edits denied.
- **omp** `always-ask` prompts for write and exec tools and auto-approves reads. omp task subagents run with approvals off, so approving one task call approves everything that subagent does.

Keep secrets out of the repository, or out of the agent's working tree, when this matters. Pi extension-based capabilities are never described as native. The external security-audit skill is documented and installed on demand (ADR-0006); it is never generated, auto-installed, or manifest-owned.
