# ADR-0010: Native capability parity across agentic CLIs

- **Status:** Accepted
- **Date:** 2026-11-18
- **Decision owners:** Project owner (accepted 2026-11-18)
- **Scope:** Generator architecture, platform support, and generated security defaults
- **Tags:** platforms, adapters, parity, omp, hooks, permissions, scope
- **Supersedes:** ADR-0008
- **Superseded by:** None

## Context

refract exists to give new and existing projects the same agentic development structure on every coding-agent CLI a team uses. Before this decision, the generated capabilities were uneven:

- OpenCode was the only platform with a permission policy and slash commands.
- OMP received only `.omp/RULES.md`, and `--mcp` / `--agents` were dropped for it without any warning.
- Claude Code received no shared settings.
- Codex received a `config.toml` only when MCP or agents were requested.
- The platform matrix was hard-coded separately in the renderer, the CLI warnings, and the support documentation.

ADR-0008 had rejected native OMP agents, MCP and hooks. The installed omp 18.22.2 sources contradict that premise: they define project-scoped `.omp/agents/*.md` with a stable front-matter contract, `.omp/mcp.json` with a published schema, a project settings layer (`.omp/settings.json` / `.omp/config.yml`), and `.omp/hooks/pre|post`.

There was also a real incident. Applying the structure from a parent folder, combined with omp's experimental auto-learn (`autolearn.enabled`), filled user scope with skills: `~/.omp/agent/skills/{research,implement}`, and hundreds of auto-minted entries in `~/.omp/agent/managed-skills`. Those skills then leaked into every unrelated project.

## Decision drivers

- One capability, rendered in each platform's native format. Real gaps are documented and warned about, never dropped silently.
- Generated content and writes stay project-scoped. refract never writes to, and never instructs agents to write to, user or global agent directories.
- Safe defaults are equivalent across platforms: ask before edits and shell commands, and deny reading `.env` secrets.
- Hooks remain opt-in and deterministic (ADR-0005). They never invoke an LLM or mutate the bootstrap.
- Generation stays offline and serializer-based. Platform contracts are verified against installed CLIs.
- Pi's capabilities overlap with omp's and lag behind it.

## Considered options

### Option 1: Native capability parity driven by a capability registry (selected)

A single `capabilities.py` table maps each capability to a native artifact, or to an unsupported reason, for each platform. Adapters render the native artifacts. Effective feature flags, warnings and support rows all derive from the table.

### Option 2: Lowest common denominator

Keep everything in `AGENTS.md` and `.agents/skills`, and remove the platform extras. This is simple, but it gives up native subagents, MCP, permissions and hooks, which are the features that make the process enforceable.

### Option 3: Keep ADR-0008's minimal OMP adapter

Leave OMP as a second-class platform. This was rejected because the premise is outdated and because it would not fix the global-skills incident.

## Decision

Adopt Option 1. The parity contract is:

| Capability | Claude Code | Codex | OpenCode | OMP |
|---|---|---|---|---|
| Permissions (`--permissions`) | `.claude/settings.json` (secret denies; native ask mode) | `.codex/config.toml` `approval_policy=on-request`, `sandbox_mode=workspace-write`, no network | `opencode.json` ask/ask + `.env` read deny | `.omp/settings.json` `tools.approvalMode=always-ask` |
| Skill invocation | `/<skill>` | native skills | `.opencode/commands/<skill>.md` generated per skill | `/skill:<skill>` |
| Subagents (`--agents`) | `.claude/agents` | `.codex/agents` | `.opencode/agents` | `.omp/agents` |
| MCP (`--mcp`) | `.mcp.json` | `.codex/config.toml` | `opencode.json` | `.omp/mcp.json` |
| Agent hooks (`--hooks`) | Stop hook | `.codex/hooks.json` Stop hook | `session.idle` plugin | `agent_end` post hook |

All agent hooks call one deterministic script, `.refract/bin/agent-check`. It runs the project validator and reports the result in each CLI's hook protocol.

Scope guard:
- `init` and `retrofit` refuse the home directory, the filesystem root, and any non-repository folder that contains nested git repositories, unless `--allow-unscoped-target` is passed.
- Validators reject references to user-level agent configuration directories (for example `~/.omp/`, `$HOME/.claude/`) in generated skills, agents, commands and rules. The user-editable `AGENTS.md` is exempt.
- omp projects always receive `.omp/settings.json` with `autolearn.enabled=false`. This is scope protection, not a permission, so it ships even without `--permissions`.

Restrictive permission policies are opt-in (`--permissions`, AGENTS.md rule 3). Without the flag, no new settings file collides with a project's existing Claude or Codex configuration during retrofit.

Hook roots are resolved by walking up from the hook's working directory to the nearest folder holding `.refract/bin/agent-check`. This works for non-git and monorepo-subdirectory projects. The Claude Code and Codex Stop hooks pin the SHA-256 of `agent-check` and `validate` in their protected hook configuration and run both in isolated Python mode (`-I`).
- Validators reject skill mirrors that drift from the portable copy.

Pi is deprecated. Selecting it emits a warning, and it will be removed in the next major release per `docs/RELEASING.md`.

## Consequences

### Positive

- Every selected platform receives the same capabilities, or an explicit warning and a support-matrix row explaining the gap.
- omp sessions in refract projects stop minting user-scope managed skills, and agents are steered away from global installs.
- One registry removes the drift between renderer, CLI and documentation.

### Negative

- More generated files per platform, with a larger golden tree and examples.
- `.claude/settings.json` is generated when `--permissions` or `--hooks` is selected. omp also merges this file into its project settings layer, but the Claude-only keys there do not collide with omp setting ids.
- The OpenCode plugin and omp hook live in agent-writable directories and are not hash-pinned. Neither platform sandboxes the agent, so a hook cannot widen access the agent already has.
- Residual: a time-of-check/time-of-use window between hashing and executing the hook scripts.
- Codex loads project `.codex/` configuration, hooks included, only for trusted projects.

### Risks and mitigations

- CLI contract drift: contract tests exercise `claude`, `codex`, `opencode` and `omp` when installed, and the verified versions are re-dated in `docs/PLATFORM_SUPPORT.md`.
- Hook loops: the Stop hooks block a failing turn once, and only report on a turn that a Stop hook has already continued (`stop_hook_active`).
- Disabling omp auto-learn per project may surprise users who want it. The setting is visible in `.omp/settings.json` and documented.

## Implementation and validation

1. `src/refract/capabilities.py`; adapter updates in `src/refract/adapters/`; `templates/core/bin/agent-check.py`; `project_scope_problems` in `src/refract/paths.py`; platform-surface checks in both validators.
2. Gates: the unittest suite (CLI-gated contracts for all four CLIs), `refract validate --target .`, the all-platform dry-run preview, golden tree and example refresh.
3. Live evidence on 2026-11-18:
   - `opencode debug config` showed the permissions, MCP and plugin.
   - `codex mcp list --json` and `codex doctor` parsed the generated config.
   - `omp config get` resolved `always-ask` and `autolearn=false` from the project layer, over a user layer set to `yolo` / `true`.
   - `claude mcp get context7` resolved the project MCP server.

## Revisit triggers

- A CLI changes its project discovery paths, hook protocol, or permission schema.
- Codex removes the trust requirement for project layers, or adds native per-project permission profiles.
- omp promotes auto-learn out of experimental status or scopes managed skills per project.
- Pi removal at the next major release.

## References

- ADR-0001, ADR-0003, ADR-0005, ADR-0008
- `docs/PLATFORM_SUPPORT.md`
- `tasks/research-omp-support.md`
