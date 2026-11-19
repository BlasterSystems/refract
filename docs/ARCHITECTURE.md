# Architecture

## Overview

Refract separates portable project knowledge, coding-platform adapters, and optional integrations.

```text
bounded evidence ──> untrusted agent proposal ──> human-confirmed facts
                                                        |
                                                        v
                                               typed project model
                                                        |
                                                        v
portable renderer ──> platform adapters ──> optional integrations
                 |
                 v
ownership-aware plan + integrity identifier
                 |
                 v
trusted-terminal confirmation ──> staged apply/rollback ──> ownership manifest
```

## Modules

- `model.py`: typed facts, features, and generated files
- `detection.py`: evidence-based stack and command detection
- `inspection.py`: bounded, no-follow, read-only evidence collection; root build manifests are looked up by name, so fact derivation does not depend on walk order or limits
- `protocol.py`: strict agent intent and canonical plan-integrity schemas
- `facade.py`: safe inspection, prepare, and apply entry points
- `renderer.py`: portable core composition
- `capabilities.py`: the per-platform capability registry behind effective features, warnings, and the support matrix (ADR-0010)
- `adapters/`: Claude Code, Codex, OpenCode, omp, and deprecated Pi native artifacts, plus the hash-pinned hook launcher in `adapters/shared.py`
- `planner.py`: ownership-aware file operation planning, including `--keep-existing` and protected control paths (ADR-0012)
- `paths.py`: path normalization, target-containment checks, and the project-scope guard
- `migration.py`: read-only findings about an existing agent setup
- `gitsafe.py`: the only way refract runs git in a target, with repository-configured helper programs disabled
- `apply.py`: staged apply and rollback
- `manifest.py`: generated-file hashes and adapter selection
- `validation.py`: syntax, token, portable-core, and ADR checks
- `cli.py`: init, retrofit, inspect, and validate commands

## Safety model

Unmanaged files are never overwritten. Immutable manifest-owned files update only when their content and mode match the prior generated state; drift becomes a conflict. Explicitly marked mutable seeds—project instructions, architecture/process docs, ADR index/template, and task template—may be customized and are preserved while their structure is validated. An editable seed is replaced or removed only when its content is shown to be refract's own output (ADR-0013). The manifest records the hash of the generated version a seed started from, never the hash of an edited file, and states this with `"seed_hashes": "generated"`. A seed that differs from that hash is preserved with the hash carried forward, and an edited seed that refract no longer generates is kept without blocking the apply. A manifest without the key comes from a release that could record an edited file's hash, so its seed hashes are not trusted: a seed is then recognized as generated only when it equals what the current templates and facts render with that release's version string, and any other seed is kept and recorded with an all-zero hash that means "base unknown".

Git hooks are generated only when selected. `setup-hooks.sh` installs a hash-pinned launcher into git's own hooks directory, which sandboxed agents cannot write; it refuses to replace an existing custom hook or `core.hooksPath` without `--force`.

### Hook and script trust

Generated hooks and scripts run as the developer, outside any agent sandbox, while the files they execute live in the agent-writable workspace:

- **Agent Stop hooks (Claude Code, Codex)** pin the SHA-256 of `agent-check` and `validate` in their hook configuration. They run verified private copies in isolated Python mode and skip if the pins do not match.
- **The git pre-commit launcher** pins the hook, validator, docs-check, and `.refract/config.json` at setup time. It runs private copies of exactly those verified bytes and blocks the commit on any change. The configured test and build commands are project code and are not pinned; they run from the working tree, as they would by hand.
- **`.refract/bin` scripts** use `python3 -I`, so modules planted beside them are never imported.
- **Repository-supplied manifests are untrusted.** They can never mark refract control paths as mutable.
- **Repository-derived names are escaped** before they reach the terminal or a hook's reply to the agent.
- **OpenCode plugins and omp hooks are not pinned.** Those platforms do not sandbox the agent, so the agent can already change what they load.

## Agent-guided trust boundary

Repository evidence, agent proposals, and repository-supplied manifests are untrusted. Agents may inspect bounded evidence and preview deterministic plans, but cannot supply generated files or apply. Agent-guided apply is recomputed, fully displayed, and directly confirmed in a separate interactive human terminal. Plan identifiers provide integrity, not identity or authorization. See `docs/AGENT_GUIDED.md`, `docs/THREAT_MODEL.md`, and ADR-0005.

- **Previews never carry existing file contents.** A dry run withholds them in both the JSON and the text format; only the interactive apply shows exact diffs against existing files.
- **The recomputed plan is displayed before the expected identifier is checked,** so a mismatch still shows the human the current plan, and nothing is written.
- **`scripts/refract.sh` isolates its imports.** Agents may run it from a temporary clone inside a target repository, so it keeps the current directory and any inherited `PYTHONPATH` off the import path.

## Portable core

`AGENTS.md`, workflow documents, tasks, ADRs, validators, and `.agents/skills` contain no coding-platform tool syntax. Adapters add only officially supported platform files.

## Architecture decisions

See `docs/adr/README.md`. Read the index before loading individual records.
