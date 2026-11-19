# Answers File

Use `--answers FILE` to provide confirmed project facts and feature choices without repeating every CLI flag. CLI flags override values from the file; detector evidence supplies fields that remain absent.

## Example

```json
{
  "project": {
    "name": "example-service",
    "description": "Processes example requests",
    "build_command": "python3 -m build",
    "test_command": "python3 -m unittest discover -s tests -v",
    "run_command": "python3 -m example_service",
    "ticket_prefix": null
  },
  "features": {
    "platforms": ["claude", "codex", "opencode", "omp"],
    "mcp": false,
    "agents": false,
    "github": true,
    "scheduled_audit": false,
    "hooks": false,
    "permissions": false
  }
}
```

`features.platforms` may also be the string `"all"` or a comma-separated string such as `"claude,codex"`. Feature values must be JSON booleans, not strings. Project command fields and `ticket_prefix` accept a string or `null`.

### What each feature generates

Each feature is rendered in every selected platform's native format, following the capability matrix in `docs/PLATFORM_SUPPORT.md` (ADR-0010). A feature that a selected platform cannot express produces a warning; it is never dropped silently.

- `mcp`: native MCP configuration per platform (`.mcp.json`, `.codex/config.toml`, `opencode.json`, `.omp/mcp.json`).
- `agents`: the read-only architecture reviewer as a native subagent per platform.
- `hooks`: Git hooks plus deterministic agent end-of-turn hooks. Each agent hook runs `.refract/bin/agent-check`, which executes the project validator. Run `./setup-hooks.sh` once to install the pre-commit hook: it writes a hash-pinned launcher into git's own hooks directory, and a commit is blocked if `.githooks/pre-commit`, the validator, docs-check, or `.refract/config.json` changed since setup. Review the change, then re-run `./setup-hooks.sh` to re-pin. The pins cover refract's own scripts and configuration. The configured test and build commands still run the project's code from the working tree (for example `npm test` runs `package.json` scripts), exactly as running them by hand would.
- `permissions`: restrictive native project policies (`.claude/settings.json`, `.codex/config.toml`, `opencode.json`, `.omp/settings.json`). It is off by default, so existing Claude and Codex settings never conflict during retrofit.

`pi` remains a valid platform but is deprecated.

The target must be a single project root. refract refuses the home directory, the filesystem root, and folders that group several repositories. `--allow-unscoped-target` is a CLI-only override and cannot be set from an answers file.

Preview before applying:

```bash
refract init --answers answers.json --dry-run --yes --target /path/to/project
```

Keep answers files free of credentials. They describe project metadata and generated features, not secrets or provider tokens.

## Agent proposals

`--answers` is a trusted-caller input and is not an LLM proposal format. Agent-guided workflows use `--agent-intent FILE` with schema `refract-intent/v1`; those values remain unverified until confirmed in the separate interactive human apply. Agent intents reject unknown fields, arbitrary paths, content, patches, modes, manifest entries, credentials, confirmations, and approvals. See `docs/AGENT_GUIDED.md`.
