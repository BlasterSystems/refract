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
- [x] The manifest records the hash of the generated version for a seed, never of the edited file, and states this with `"seed_hashes": "generated"`.
- [x] The "generated seed changed" note appears once per change. A seed made identical to the generated version is tracked as generated again.
- [x] Under a manifest without the key (0.3.0 or earlier), a seed is updated or removed only when its content equals what that release would have generated. Otherwise it is preserved.
- [x] An edited seed that is no longer generated is released from the manifest and kept, not reported as a conflict and not removed.
- [x] The plan document's `resulting_ownership` equals the manifest that apply writes.
- [x] `docs-check` ignores `.refract/` and files that a manifest records as generated; other configuration paths are still reported.
- [x] This repository's `.refract/bin/docs-check` is identical to the packaged template, and a test keeps it so.
- [x] Tests fail when the fix is removed.

## Out of scope

- Recognizing an unedited seed under an older manifest when the project facts change in the same run. Refract then keeps the file and says how to take the generated version. Reading facts back from `.refract/config.json` (entry-path consolidation, phase 2) removes this limit.
- The other `docs-check` heuristics (for example test paths containing `integration`), planned with the verification work in the entry-path consolidation.

## Key changes

- `src/refract/manifest.py`: `seed_hashes` key, `Manifest.tracks_generated_seeds`, and `generated_entry`, the one place that builds a manifest entry for a file as generated.
- `src/refract/planner.py`: `Operation.customized`; equality with the generated version is checked first; protection under older manifests; release of edited seeds that are no longer generated.
- `src/refract/renderer.py`: `render_project(..., generator_version=...)`, used to ask what an earlier release would have generated.
- `src/refract/apply.py`, `src/refract/protocol.py`: a customized seed is recorded as generated, in the written manifest and in the plan document.
- `src/refract/templates/core/bin/docs-check.py` and `.refract/bin/docs-check`: skip Refract's metadata and manifest-recorded generated files.
- `docs/ARCHITECTURE.md`: states the seed-hash rule.

## Review history

The first version carried a customized seed's old manifest entry forward. Independent review found that it still lost edits on the first upgrade of an already affected project, kept a re-adopted seed marked customized forever, repeated the review note on every run, and turned an edited obsolete seed into a permanent conflict. The second version records the generated version's hash instead and adds the older-manifest rule.

## Validation evidence

Recorded in the pull request.

## Review

Independent review before merge, recorded in the pull request.
