# Research: CLI contract-test drift (opencode + codex)

## Jira target

**Resolved: doc-only — no Jira ticket (explicit user decision, 2026-11-18).**

- Phase 0 found no repo mapping: no Jira skills under `.agents/skills/` / `.claude/skills/` (only `refract`, `architecture-decision`, `docs-check`, `semantic-versioning`), no `.pi/prompts`, no ticket keys in `tasks/` filenames, conventional-commit subjects without `[KEY]` prefix.
- Asked the user; answer: **"No Jira — keep it doc-only (tasks/ file is the tracker)."**
- This file is therefore the task tracker; `/implement` reads it directly. No overlap check performed.

## Summary

The two contract tests that drive real installed CLIs fail with current builds, independent of any product change:

1. `tests/contracts/test_platforms.py::test_codex_cli_parses_generated_toml_in_isolated_config_home` — codex now writes a stderr warning; the test merges stderr into stdout, corrupting the JSON it parses.
2. `tests/contracts/test_opencode.py::test_opencode_parses_generated_config_v2` — opencode changed the `debug config` output shape; the test still parses the legacy shape.

Impact: CI never installs these CLIs (`skipUnless(shutil.which(...))` → skip), so CI stays green — but the **local release gate fails** (`docs/RELEASING.md` step 8 runs the full suite), blocking any release on a dev machine with current CLIs.

## Current state (evidence)

- `tests/contracts/test_platforms.py:79` — `@unittest.skipUnless(shutil.which("codex"), ...)`
- `tests/contracts/test_platforms.py:91-100` — runs `codex mcp list --json` with `stderr=subprocess.STDOUT` and `env CODEX_HOME=<tempdir>/.codex`, then `json.loads(result.stdout)` (line 100; failure: `JSONDecodeError: Expecting value: line 1 column 1`).
- `tests/contracts/test_opencode.py:43` — `@unittest.skipUnless(shutil.which("opencode"), ...)`
- `tests/contracts/test_opencode.py:52-55` — `json.loads(result.stdout)` expected to be a **list** of `{type, path, info}` entries; failure: `AttributeError: 'str' object has no attribute 'get'`.
- `.github/workflows/test.yml` — installs only the package; no `opencode`/`codex` install step → both tests skip in CI.
- `docs/PLATFORM_SUPPORT.md:1` — "Last verified: 2026-11-09"; `:3-9` — OpenCode 2.0.28 verified against installed builds; Codex 0.167.0 npm-tracked. `:19` — contract-validation contract.
- `docs/RELEASING.md` step 8 — release gate includes the full unittest suite.
- `docs/DEVELOPMENT_PROCESS.md` step 5 — "run platform contract diagnostics where available"; step 7 — "update support evidence".

### Ground truth (probe, 2026-11-18, temp generated projects)

- `opencode --version` → `1.19.5`; `opencode debug config` (rc=0, `XDG_CONFIG_HOME` isolated) → **one JSON object**: `{"$schema": ..., "permission": {"edit": "ask", "bash": "ask"}, "agent": {...}, ...}` — the effective config, not a source-entry list.
- `codex --version` → `codex-cli 0.169.0`; `codex mcp list --json` (rc=0, `CODEX_HOME=<tmp>`): **stdout is valid JSON** `[{ "name": "context7", "enabled": true, "transport": {"type": "streamable_http", ...} }]`; **stderr** carries `WARNING: proceeding, even though we could not create PATH aliases: Refusing to create helper binaries under temporary dir "/tmp" ...`.

## Gap analysis

| Test | Asserts | Installed build | Breaks because |
|---|---|---|---|
| codex | stdout is JSON array containing `context7` | `codex-cli 0.169.0` (verified: 0.167.0) | New stderr warning under `/tmp` `CODEX_HOME` + `stderr=STDOUT` merge pollutes parsed stdout `[INFERENCE on 0.167.0 not warning — 0.167.0 no longer installed; warning text is tmp-specific]` |
| opencode | list of source entries → document entry `permissions` map | `opencode 1.19.5` (verified: 2.0.28) | Output shape is now the effective config object; legacy list-shape parser throws `AttributeError` |

Both failures are **test-harness coupling**, not product regressions: the generated artifacts themselves are correct (the probe shows `permission.edit/bash = "ask"` and `context7` present).

## Proposed design

**Decision: make the two tests contract-faithful and shape/stream-tolerant. Keep them in the default suite; no version pinning.**

1. **Codex test** — capture stdout and stderr separately (`stderr=subprocess.PIPE`, i.e. drop `stderr=subprocess.STDOUT`); `json.loads(result.stdout)` unchanged; keep rc and `context7` assertions. Optionally assert the returned entry keeps `name`/`transport` keys. Stderr is no longer a data channel; nothing is lost.
2. **OpenCode test** — parse `json.loads(result.stdout)` once, then branch on shape:
   - `dict` → treat as the effective config; assert `config["permission"]["edit"] == "ask"` and `config["permission"]["bash"] == "ask"`.
   - `list` → keep the documented source-entry lookup (`type == "document"`, path ends `opencode.json`, `info["permissions"]` map).
   - Anything else → fail with the raw payload in the message. Keep the filesystem assertions (agents/commands/skills paths) unchanged — they are version-independent and are the real contract.
3. **No version pinning in CI** — the tests skip when CLIs are absent (current CI behavior); pinning would add network flakiness and fight the documented "verified against installed builds" policy for OpenCode.
4. **Support-evidence refresh (same task)** — re-run all four platform contract diagnostics after the fix; only if all pass, update the "Last verified" stamp in `docs/PLATFORM_SUPPORT.md` **and its template** `src/refract/templates/core/docs/PLATFORM_SUPPORT.md` (codex 0.169.0, opencode 1.19.5, claude — record installed version), then regenerate examples and refresh their manifest hashes (RELEASING step 7 flow + hash refresh).

**Rejected alternatives**

- *Pin CLI versions in CI (install opencode@2.0.28 / codex@0.167.0 in `test.yml`)* — deterministic, but adds network/install flakiness to every matrix cell, contradicts the installed-builds verification policy, and still fails local runs with newer CLIs. Rejected.
- *Delete the CLI-parsing tests* — they just caught two real interface changes; deleting removes the only always-on signal. Rejected.
- *Move parsing to a release-only smoke script* — weakens local signal; the release gate already runs the full suite. Rejected.

## Delivery plan (single task — ask is small)

**Task: Fix CLI contract-test drift (codex stderr merge, opencode config shape)**

Acceptance criteria:

1. `PYTHONPATH=src python3 -m unittest discover -s tests` is green on this machine with `opencode 1.19.5` + `codex-cli 0.169.0` installed (only expected skips are absent-CLI tests).
2. The codex test parses **stdout only**; stderr cannot corrupt the JSON assertion; rc and `context7` assertions unchanged.
3. The opencode test passes for **both** payload shapes (effective-config dict and legacy source-entry list) and fails loudly with the raw payload for any other shape.
4. With CLIs absent, both tests still skip (CI matrix on ubuntu/macos × py 3.11/3.13 unaffected).
5. Support evidence updated iff all four platform diagnostics verified: verified-date stamp + versions in `docs/PLATFORM_SUPPORT.md` and its template, examples re-rendered, example manifest hashes refreshed, then `refract validate --target .`, `.refract/bin/validate`, `sync-version.py --check` all green.
6. No product/template behavior change: the fix touches only the two test functions (+ docs stamp). Renderer output is byte-identical.

Priority: **high** — blocks the local release gate for any dev machine with current CLIs.

## Risks & open questions

- **Open:** which Jira project hosts this (Phase 0 unresolved) — and whether a ticket is wanted at all vs. doc-only.
- **Open:** is the `claude` CLI installed locally? If yes, its diagnostic must also pass before touching the verified-date stamp; if absent, record it as skipped and do not claim verification for Claude Code.
- **Risk:** opencode may flip output shape again (channel drift is documented for this CLI). The shape-tolerant branch plus loud failure with raw payload keeps future drift a one-line fix instead of a mystery.
- **Risk:** the codex warning is tmp-dir-specific; on non-tmp `CODEX_HOME` it may not appear. Stream separation is correct regardless.
- **Note:** tests currently pass on CI regardless (CLIs absent) — the fix matters for local dev and release gates, not CI correctness.

## Jira overlap findings

N/A — doc-only decision (no Jira project resolved). If a Jira target is chosen later, check open epics + JQL `text ~ "contract"` / `~ "opencode"` / `~ "codex"` (paginate `search/jql` with `nextPageToken`) before creating anything.
