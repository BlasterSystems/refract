# Security Policy

Refract is a set of instructions that coding agents follow to set up a project: `BOOTSTRAP.md`, the skills and docs in `content/`, and the platform notes. It runs no code of its own. Its attack surface is what those instructions make an agent do in someone else's repository.

## Supported versions

Refract is pre-1.0. Only the latest tagged release and `main` receive security fixes.

| Version | Supported |
|---|---|
| latest tag | Yes |
| older 0.4.x tags | No; re-run the setup from the latest tag |
| 0.3.x and earlier (the Python CLI) | No; the CLI is discontinued |

## Reporting a vulnerability

Use GitHub private vulnerability reporting on this repository (**Security → Report a vulnerability**). Do not open a public issue for a suspected vulnerability.

Include:
- **The refract release** (tag or commit), and the file involved: `BOOTSTRAP.md`, a skill, a platform note, or a doc.
- **The agent and its version**, for example Claude Code 2.1.328 or Codex 0.169.0.
- **The exact prompt** you gave the agent.
- **A minimal reproduction:** the target project's layout and the relevant file contents, including any planted text.
- **What the agent did, compared with what the rules require,** and the concrete impact.

Do not include secrets, credentials, or third-party repository content in the report.

## Scope

**In scope:** refract's instructions or content causing, or failing to prevent, any of the following:
- writing outside the target project, or to user-level or global agent folders
- changing, moving, or deleting an existing file without an approved diff, or losing user content outside `.refract/deprecated/`
- enabling permissions, hooks, subagents, or MCP that the user did not name
- following instructions found in the target project's own files, or carrying them over from `.refract/deprecated/`
- reading or exposing secrets, or generating configuration that weakens a platform's security defaults
- hook commands, plugins, or generated configuration that can be abused, for example through quoting or injection of a project's test command
- integrity of the source the agent clones, including third-party content and its license notices

**Out of scope:**
- vulnerabilities in the coding agents themselves (report those to their vendors)
- vulnerabilities in a target project's own code
- changes the user explicitly approved after seeing the diff
- environments where the agent already holds broader permissions than the setup needs

Reports of a model ignoring a rule that refract states clearly are welcome. They are handled as hardening (clearer or stronger wording), not as vulnerabilities, unless refract's wording caused the behavior.

## Response expectations

- Acknowledgement within 7 days.
- Confirmed vulnerabilities ship in the next patch release, and are credited in `CHANGELOG.md` unless the reporter prefers anonymity.
- Coordinated disclosure: please allow a reasonable window before publishing details.
