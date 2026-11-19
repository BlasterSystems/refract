# Task: Customized seeds must survive every re-run

## Objective

Stop Refract from overwriting a file it seeded and the user then edited. Also unblock version-bump pull requests, which the `docs-check` heuristic rejects.

## Background

Found during the project review on 2026-11-19, before the 0.3.1 release. Present in 0.3.0.

Refract marks some generated files as editable seeds (`AGENTS.md`, `docs/DEVELOPMENT_PROCESS.md`, `docs/DEPLOYMENT.md`, and others). The planner treats a seed as customized when its content differs from the hash in `.refract/manifest.json`, and then preserves it.

When an apply rewrites the manifest for any other reason, it records the customized file's current hash as the new baseline. On the next run the file no longer looks customized, so a changed template or changed fact produces `UPDATE_GENERATED` and the user's edits are replaced without a conflict or warning.

Reproduction: `init`, edit `AGENTS.md`, run `retrofit` twice with a different `--description` each time. The first re-run keeps the edit; the second removes it.

Separately, `.refract/bin/docs-check` treats any changed path containing `config` as configuration that needs a matching document. `.refract/config.json` changes on every version bump and every upgrade, so those pull requests fail the strict check unless an unrelated document changes too.

## Acceptance criteria

- [x] A customized seed keeps its content across any number of re-runs, including runs that rewrite the manifest.
- [x] The manifest keeps the hash of the last generated version for a customized seed, so later runs still recognize the customization and still report when the generated seed changed.
- [x] The plan document's `resulting_ownership` equals the manifest that apply writes.
- [x] `docs-check` ignores paths under a `.refract/` directory; other configuration paths are still reported.
- [x] This repository's `.refract/bin/docs-check` is identical to the packaged template, and a test keeps it so.
- [x] Tests are written first and fail before the fix.

## Out of scope

- Repairing projects whose manifest already recorded a customized hash as the baseline. Refract cannot tell those files from unmodified generated ones; the changelog tells users to check their history.
- The other `docs-check` heuristics (for example test paths containing `integration`), planned with the verification work in the entry-path consolidation.

## Key changes

- `src/refract/planner.py`: `Operation.customized` marks a preserved customized seed.
- `src/refract/apply.py` and `src/refract/protocol.py`: a customized seed carries its previous manifest entry forward.
- `src/refract/templates/core/bin/docs-check.py` and `.refract/bin/docs-check`: skip Refract's own metadata.
- `docs/ARCHITECTURE.md`: states the manifest baseline rule.

## Validation evidence

Recorded in the pull request.

## Review

Independent review before merge, recorded in the pull request.
