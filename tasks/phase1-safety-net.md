# Phase 1: safety net

Implements phase 1 of [plan-entry-path-consolidation.md](plan-entry-path-consolidation.md) (work packages 1.1–1.6). No CLI behavior change; the only generated-output change is the `docs-check` template (1.6), which ships with the next minor release.

- **Status:** In progress, branch `phase/1-safety-net`.
- **Baseline:** `9a895f5` (v0.3.1).

## Work packages

| WP | Deliverable | Owner |
|---|---|---|
| 1.1 | `scripts/check.sh` runs the full CI gate locally; CI calls it | main agent |
| 1.2 | `tests/contracts/test_documented_commands.py` parses every documented command | DocsParseTest |
| 1.3 | `tests/integration/test_documented_flows.py` runs documented preview/apply pairs in a pseudo-terminal; markers in `docs/PROMPTS.md` | DocsFlowTest |
| 1.4 | `scripts/sync-version.py` rewrites documented version literals; literals tied to one constant | VersionLiterals |
| 1.5 | `tests/contracts/test_mirrored_docs.py` compares template docs with the repo docs they mirror | MirroredDocs |
| 1.6 | `docs-check` template ignores test directories; golden tree, `docs/GENERATED_OUTPUT.md`, examples, and the repo's own `.refract/bin/docs-check` refreshed | main agent |

## Acceptance (from the design)

- `scripts/check.sh` reproduces every CI check; CI invokes it.
- Every documented `refract …` / `scripts/refract.sh …` / `uvx --from … refract …` command in `README.md`, `AGENTS.md`, and top-level `docs/*.md` parses with the real argument parser.
- Every documented preview/apply pair runs end to end in a pseudo-terminal and `refract validate` passes afterwards.
- Every hand-written version literal is rewritten by `sync-version.py` and asserted by a test.

## Gates

- Full suite + both validators + `check.sh` green before the PR.
- Independent review of the final commit (`docs/DEVELOPMENT_PROCESS.md` §6) before merge.

## Record

- 1.2 — `tests/contracts/test_documented_commands.py`: 39 documented commands across 8 files extracted (fenced blocks, inline backticks, continuations, `python3 -m` / `uvx --from` / `refract.sh` forms), every one parsed with `build_parser()`; per-file floors guard the extractor against going vacuous.
- 1.3 — 8 markers in `docs/PROMPTS.md` (4 preview/apply pairs, no command text altered); `tests/integration/test_documented_flows.py` runs each pair end to end (preview → `plan_id` → PTY apply driven on prompt text → validate), on empty, own-agent-files, and hostile fixtures; own `AGENTS.md` asserted byte-identical after apply.
- 1.4 — `scripts/sync-version.py` rewrites the documented floor in README.md, docs/PROMPTS.md, docs/PROJECT_SUMMARY.md (three contexts only, missing/non-regular docs skipped) with the same temp-file+rename safety; `tests/unit/test_version_literals.py` asserts every floor literal equals `__version__`. Floors rewritten to 0.3.1.
- 1.5 — `tests/contracts/test_mirrored_docs.py`: claim-driven discovery found only `SECURITY_AUDIT.md` and `TASK_BREAKDOWN.md` are true mirrors (both docs claim it); heading-set equality both directions for claimed pairs, and a classification ledger requiring every template doc to be claimed or explicitly `NOT_MIRRORED` with a reason. The six name-collisions are different documents by design and are recorded, not allowlisted.
- Integration fixes: sync-version skips a missing/non-regular doc instead of failing (kept the symlink-attack test hermetic); mirrored-docs literals reworded so no unresolved `{{TOKEN}}` appears (validator). `scripts/check.sh` green: 192 tests, both validators, strict docs-check, wheel + installed-CLI smoke.

- 1.1 — `scripts/check.sh` added (sync-version --check, full suite, both validators, strict docs-check vs `CHECK_BASE`, wheel build + installed-CLI smoke with a pip-or-uv fallback); `.github/workflows/test.yml` gained a `gate` job calling it, included in `test-gate`. Verified locally: `scripts/check.sh` exits 0, smoke reports `refract 0.3.1`.
- 1.6 — `src/refract/templates/core/bin/docs-check.py` and the repo's `.refract/bin/docs-check` now drop paths under `tests/`, `test/`, `__tests__/`, `spec/` before classification; regression test `tests/integration/test_cli.py::test_docs_check_ignores_test_directories` (test-dir change passes strict, a handler rename outside test dirs is still flagged). Examples regenerated (`.refract/bin/docs-check` + manifests); golden tree and `docs/GENERATED_OUTPUT.md` list paths only — unchanged and verified by `test_golden`.
