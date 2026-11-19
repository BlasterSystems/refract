# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- An agent-guided dry run in text format no longer prints the contents of existing managed files in its diffs. It withholds them as the JSON format does; only the interactive apply shows them.

### Fixed

- An edited seed file such as `AGENTS.md` or `docs/DEPLOYMENT.md` is no longer overwritten on a later re-run (ADR-0013). Before, a re-run that rewrote the manifest recorded the edited content as the generated version, and the next template or fact change replaced the file without a conflict. The manifest now keeps the hash of the generated version a seed started from, and says so with a new `seed_hashes` key.
- Projects already affected are protected when they upgrade. Under a manifest written by 0.3.0 or earlier, Refract updates or removes a seed only when it can show the file is what it generated, and otherwise keeps the file with a note. To take the generated version of a kept seed, delete the file and re-run.
- An edited seed that Refract no longer generates, for example after dropping `--github`, is kept and no longer blocks the run with a conflict. Before, `--remove-obsolete` could delete it. Delete the file yourself to drop it.
- A seed that is brought back in line with the generated version is tracked as generated again.
- `docs-check` ignores Refract's own metadata under `.refract/`, so a version bump no longer fails the strict check.
- `scripts/refract.sh` no longer imports Python modules from the current directory or from an inherited `PYTHONPATH`, so a target repository's files cannot shadow the standard library or Refract when the wrapper runs from a clone. It reports a clear error on Python older than 3.11.
- An agent-guided apply with a wrong `--expected-plan` now displays the recomputed plan before it stops, as ADR-0005 specifies. It still writes nothing.
- Agent-guided previews no longer lose languages and commands in repositories with more than 200 files. `refract inspect` looks up build manifests at the repository root by name, detects lockfiles by presence, reads shallow files before deeper ones, and skips a file that is too large instead of ending the scan. When a root manifest cannot be read, the inspection reports `facts_incomplete` and the plan warns.

### Documentation

- Install and upgrade instructions use pipx or uv, so they work where the system Python is externally managed (PEP 668). The README adds install options, an `externally-managed-environment` troubleshooting entry, and notes for pinned releases and earlier `pip install` setups.
- `docs/PROMPTS.md` set-up prompt needs no install: the agent uses an installed `refract`, `uvx`, or a clone in a temporary folder, runs an agent-guided JSON preview, and you apply in an interactive terminal with `--expected-plan`, so Refract refuses to write if the plan changed.
- New-project and existing-project prompts use the same agent-guided preview and `--expected-plan` apply instead of a plain `--dry-run --yes` preview; the README links to them.
- Agents never install Refract; the prompt rules and the README's rules for coding agents say how to run it in place.
- Advisory setup prompt: when inspection is truncated or a command or ticket prefix is missing, the agent looks for it with its own read-only tools and says where it came from.
- `docs/AGENT_GUIDED.md` describes the apply order as the CLI runs it.

## [0.3.0] - 2026-11-18

### Breaking changes

- Project renamed to Refract: distribution and CLI are `refract`, the Python package is `refract`, generated-project metadata lives in `.refract/`, and protocol schema strings use the `refract-` prefix.
- License switched from MIT to Apache-2.0.
- OpenCode's hand-written `adr-new` and `docs-check` commands are replaced by one generated command per skill; re-run with `--remove-obsolete` to delete the old `adr-new` command.
- `init` and `retrofit` refuse the home directory, the filesystem root, and folders that group several repositories unless `--allow-unscoped-target` is passed.
- The generated ticket lifecycle is section 9 of `docs/DEVELOPMENT_PROCESS.md` (new Skill workflow and Deploy sections).

### Added

- OhMyPi (omp) as a selectable platform.
- Native capability parity across Claude Code, Codex, OpenCode, and omp from one capability registry (ADR-0010): subagents, MCP, permission policies, per-skill invocation, and deterministic agent hooks in each platform's native format; unsupported selections warn instead of being dropped.
- omp: `.omp/agents`, `.omp/mcp.json`, `.omp/settings.json` (auto-learn disabled per project so sessions stop minting user-scope skills), and an `agent_end` hook.
- `--permissions`: opt-in restrictive policies (ask before edit/shell, deny `.env` reads) for every platform.
- `--hooks` adds agent end-of-turn validation through `.refract/bin/agent-check`; Claude Code and Codex Stop hooks pin script hashes, run isolated Python on verified private copies, block a failing turn once, and only report manifest drift.
- Portable agentic workflow skills (ADR-0011): `research`, `confidence-check`, `implement`, `security-check`, `quality-review`, `commit`, `deploy-dev`, `deploy-prd`, `hotfix`; a project-owned `docs/DEPLOYMENT.md` seed with the deterministic `.refract/bin/deploy-ready` gate; `docs/branches/` seed; extended task template; GitHub pull request template with a deploy-affecting block.
- `--keep-existing` retrofit (ADR-0012): keep unmanaged files and whole skill groups as project-owned; refract control paths still conflict. Retrofit prints migration findings about existing agent setups; see `docs/MIGRATION.md`.
- Validators check agent and skill front matter, skill-mirror identity, and references to user-level agent directories.

### Changed

- Codex `.codex/config.toml` and Claude `.claude/settings.json` are generated only when a selected feature needs them.
- The planner flags customized seeds whose generated version changed.
- Repository hardening: security policy, SHA-pinned CI actions, Dependabot, and a stable merge-gate check.

### Security

Release-gate audit (quick profile, partial coverage) of `v0.2.0..v0.3.0`:

- `setup-hooks.sh` installs a hash-pinned launcher into git's own hooks directory instead of pointing `core.hooksPath` at the agent-writable `.githooks/`. It runs private copies of the verified hook, validator, docs-check, and `.refract/config.json`, and a change to any of them blocks the commit until the user re-pins it. The configured test and build commands still run project code from the working tree.
- A repository-supplied manifest can no longer mark refract control files as customized seeds; only refract decides which generated files are mutable.
- git runs in target repositories through one hardened helper, so repository-configured programs (`core.fsmonitor`, signature programs) never execute during detection or migration scans.
- Control characters are rejected in generated and manifest paths; repository-derived names and validator output are printed one line each, so they cannot forge warnings or Stop-hook instructions.
- `.refract/bin` scripts run in isolated Python mode (`-I`), so modules planted next to them are ignored.
- OpenCode advisory commands now run in a plan agent whose edits are actually denied.
- `deploy-prd` reads its policy from the default branch, asks before running gate and probe commands, and merges with the inspected head commit pinned.
- Platform documentation states exactly what `--permissions` enforces on each platform, including where `.env` files remain readable.

### Documentation

- README restructured with progressive disclosure: a "Choose your path" router, task sections with ready-to-paste prompts, and collapsed reference blocks.
- New `docs/PROMPTS.md` prompt library; `docs/AGENT_GUIDED.md` intent example updated.

### Deprecated

- Pi: selecting it prints a deprecation warning; it will be removed in the next major release in favour of omp.

## [0.2.0] - 2026-11-09

### Added

- Optional install-on-demand security-audit integration (ADR-0006): guidance mode during review, a scoped `quick`-profile release gate, and `standard`/`deep` audits at epic boundaries; renders `docs/SECURITY_AUDIT.md`.
- Optional install-on-demand task-breakdown and ticket skills (ADR-0007): step 2 planning with tracker-neutral task list targets; renders `docs/TASK_BREAKDOWN.md`.
- Process gates: pull requests for reviewable changes and pre-merge adversarial review (step 6), plus the security-audit release gate (step 7).
- Use-with-an-agent quickstart, upstream credits, and an MIT license (`LICENSE`, package metadata).

### Changed

- Development process mandates pull requests for all changes; direct pushes to the default branch are a process violation.
- Conditional ticket lifecycle section in the development process and a product-manager summary section in the task template.

## [0.1.0] - 2026-07-31

### Added

- Provider-neutral bootstrap CLI with `init`, `retrofit`, `inspect`, and `validate` commands.
- Native Claude Code, Codex, Pi, and OpenCode adapters.
- Progressive-disclosure documentation, ADR lifecycle, safe planning, ownership manifests, rollback, validation, examples, and cross-platform tests.
- Answers-file reference and a repository version-metadata synchronization helper.
- Optional agent-guided bounded inspection, strict typed proposals, deterministic plan-integrity identifiers, trusted-terminal human handoff, and a provider-neutral maintenance skill.

### Changed

- Expanded CLI help for safe noninteractive generation and retrofit flags.
- Added the read-only `inspect` command while preserving direct non-LLM initialization, retrofit, and validation workflows.

### Fixed

- Ignore Pi subagent runtime artifacts during unmanaged repository validation.
- Report missing ADR supersession references without validator tracebacks.
