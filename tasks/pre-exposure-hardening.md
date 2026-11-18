# Task: Pre-exposure repository hardening

## Objective

Close the repository-operations gaps found in the 2026-11-18 pre-exposure review so the public repository is ready for increased visibility: security policy, CI supply-chain hardening, packaging metadata, exact generated-output documentation, and a hardened `docs-check --base`.

No Jira ticket exists for this repository (no ticket prefix configured); this task file is the record.

## Product manager summary

- **One-liner:** Make the public repository safe to point people at before promoting it.
- **User value:** A defined vulnerability-reporting channel, verifiable CI supply chain, and accurate documentation of what the tool generates.
- **Business impact:** Low effort; removes the most likely sources of external confusion (unprotected repo, missing policy, stale docs).
- **Success metric:** Fresh clone validates; golden output matches `--platform all`; security policy discoverable.
- **Dependencies & constraints:** Branch protection is a GitHub setting, not a file; requested separately.

## Acceptance criteria

- [x] `SECURITY.md` publishes a vulnerability-reporting policy (ADR-0009).
- [x] Repository workflows pin actions by commit SHA; Dependabot tracks updates.
- [x] Golden tree and `docs/GENERATED_OUTPUT.md` match a true all-platform render (36 files incl. `.omp/RULES.md`), with executable-mode assertions.
- [x] `docs-check --base` rejects option-like values (no arbitrary git-option injection).
- [x] `pyproject.toml` carries `readme` and project URLs; wheel METADATA verified.
- [x] Local agent tool state (`.serena/`, `.mcp.json`, `uv.lock`) is gitignored; `git status` clean.
- [x] `docs/PROJECT_SUMMARY.md` no longer claims 0.1.0 or omits omp.

## Scope

### Included

- Repository docs and metadata only; no generator behavior change except the `docs-check` guard (template + regenerated artifacts).

### Excluded

- Branch protection (repository setting; attempted out-of-band).
- Rewording `.omp/` in `docs/PLATFORM_SUPPORT.md` — rejected: ADR-0008 item 5 requires support docs to describe omp artifacts, and the support matrix names every platform's artifact paths by design. The portable-token invariant applies to `AGENTS.md` and `.agents/skills/`, which are clean.

## Plan

- [x] Understand requirements and inspect relevant code
- [x] Confirm architecture impact (ADR-0009, Proposed)
- [x] Implement the smallest complete change
- [x] Add or update tests
- [x] Update documentation
- [x] Run validation

## Architecture impact

- **ADR required:** Yes (security-sensitive repository decisions) — ADR-0009 created as Proposed.
- **Relevant ADRs:** ADR-0003 (opt-in integrations), ADR-0008 (omp artifacts and golden tree).
- **Proposed ADR:** ADR-0009 (pre-exposure repository hardening).

## Key changes

- `SECURITY.md` (new): GitHub private vulnerability reporting, supported versions, scope, response contract.
- `docs/adr/0009-pre-exposure-repository-hardening.md` (new) + index row.
- `.github/dependabot.yml` (new): weekly `github-actions` updates.
- `.github/workflows/test.yml`, `.github/workflows/docs-check.yml`: actions pinned to commit SHAs (`checkout` v4.2.2, `setup-python` v5.6.0, resolved via API).
- `src/refract/templates/core/bin/docs-check.py` + repo/examples `.refract/bin/docs-check`: reject `--base` values starting with `-`.
- `tests/integration/test_golden.py`: golden test renders `SUPPORTED_PLATFORMS` (5 platforms) and asserts executable modes; examples comparison asserts modes.
- `tests/golden/all-platforms/tree.txt`, `docs/GENERATED_OUTPUT.md`: 36-file all-platform set.
- `pyproject.toml`: `readme`, `[project.urls]`.
- `.gitignore`: `/.serena/`, `/.mcp.json`, `/uv.lock`.
- `docs/PROJECT_SUMMARY.md`: release 0.2.0, omp listed, "all platform contract diagnostics".

## Validation evidence

- Configuration validation: `refract validate --target .` and `.refract/bin/validate` — pass.
- Tests: 99/99 pass (`PYTHONPATH=src python3 -m unittest discover -s tests`), incl. new `test_docs_check_rejects_option_like_base` and 5-platform golden tests.
- Build: `pip wheel --no-deps -w /tmp/refract-wheel2 .` succeeds; METADATA contains Project-URLs and README description.
- Documentation check: `.refract/bin/docs-check` passes; `--base=--output=...` exits 2, writes no file; positive `--base HEAD~1` exits 0.
- Workflows/dependabot parse as YAML.
- Canonical preview (repo rule): `scripts/refract.sh init --platform all --dry-run --yes --target <tmp>` — dry-run writes nothing.
- Example refresh (RELEASING step 7): only `.refract/bin/docs-check` + manifest updated in both examples; post-apply validation passed.

## Review

- Correctness: guard placed before the non-git early return so it always applies; empty `--base` keeps prior no-base semantics.
- Security: no new secret surfaces; SHA pins resolved from `gh api` (verified commit SHAs); generated template intentionally keeps tag pins (documented in ADR-0009).
- Compatibility: `docs-check` failure path unchanged for other failures (exit 2 with `--strict`); `--base ""` still means "no base".
- Limitations: branch protection not settable from this session without admin API write; `SECURITY.md` channel requires enabling private vulnerability reporting in repo settings (one click).
- Residual risks: none identified beyond those documented in ADR-0009 revisit triggers.

## Adversarial review (independent, 2026-11-18)

Verdict: **correct — no confirmed problems** (confidence 0.97). Fresh read-only pass; all seven claims verified by independent execution:

- Golden tree rerendered independently: 36 files, byte-equal to `tree.txt` and the `GENERATED_OUTPUT.md` fence; all executable flags match; example renders byte-identical with correct modes.
- `docs-check` guard probed live: `--output=` injection writes nothing in either strictness mode; `--base HEAD~1`/`origin/main`/`''`/`abc123` keep correct semantics; repo and example copies byte-identical to the template.
- SHA pins cross-checked via `gh api` against `v4.2.2`/`v5.6.0`; all three YAML files parse.
- Validators pass; ADR-0009 index row and filename agree (Proposed).
- `.gitignore` anchors verified (`examples/all-platforms/.mcp.json` still tracked); no tracked file newly ignored.
- Scope confirmed: no generator behavior change beyond docs-check; 99/99 tests pass.
