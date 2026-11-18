# Task: Stable merge-gate check for branch protection

## Objective

Make the `main` branch protection satisfiable: the required context `test` cannot match matrix check-run names (`test (ubuntu-latest, 3.11)`, …), so every non-admin merge was blocked. Add an aggregate `test-gate` job with a stable check-run name and require it instead.

## Background

Branch protection was applied 2026-11-18 (see `tasks/pre-exposure-hardening.md` and ADR-0009). PR #5 merged green via the documented admin bypass after the policy proved unsatisfiable.

## Acceptance criteria

- [x] `test.yml` gains a `test-gate` job: `needs: test`, `if: always()`, fails unless the matrix result is `success`.
- [x] `test-gate` appears as a check run on PRs and passes.
- [x] Protection updated to require exactly `test-gate` + `docs-check` (stable names, no matrix suffixes).
- [x] PR #6 merges without admin bypass.

## Key changes

- `.github/workflows/test.yml`: append `test-gate` job. No template change — the generated workflow is untouched, so no golden/example regeneration is needed.

## Validation evidence

- Workflow YAML parses (`yaml.safe_load`).
- `test-gate` check run green on PR #6 before the protection switch; full matrix still green.
- Protection contexts verified via API after the switch.

## Review

- Correctness: `if: always()` + explicit non-success exit reports red when any leg fails; matrix result propagates.
- Security: no new permissions (workflow keeps `contents: read`); gate uses no secrets.
- Compatibility: check-run name is matrix-independent; adding/removing matrix legs cannot orphan the required context.
- Residual risks: none identified.
