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
- [x] The manifest keeps the hash of the generated version a seed started from, never the hash of the edited file, and states this with `"seed_hashes": "generated"`.
- [x] A seed made identical to the generated version is tracked as generated again.
- [x] Under a manifest without the key (0.3.0 or earlier):
  - a seed is updated only when its content equals what Refract would have generated under that release's version;
  - any other differing seed is preserved and recorded with an all-zero "base unknown" hash, and its note says how to take the generated version;
  - an obsolete seed is never removed, and a seed that became fully generated is a conflict.
- [x] The plan document's `resulting_ownership` equals the manifest that apply writes.
- [x] `docs-check` ignores paths under `.refract/`; other configuration paths are still reported.
- [x] This repository's `.refract/bin/docs-check` is identical to the packaged template, and a test keeps it so.
- [x] Tests fail when the fix is removed.

## Out of scope

Each of these is a policy decision and is listed in `tasks/research-entry-path-consolidation.md` for an ADR:

- Handing an edited seed back to the project when Refract stops generating it. It stays a conflict, as before.
- A way to acknowledge a changed generated seed while keeping the edits. The "generated seed changed" note stays until the file matches the generated version.
- Recognizing an unedited seed under an older manifest when a template or a project fact changed. Refract keeps the file and says how to take the generated version.
- Exempting other generated files from `docs-check`, and its other heuristics.

## Key changes

- `src/refract/manifest.py`: `seed_hashes` key, `Manifest.tracks_generated_seeds`, `UNKNOWN_SEED_BASE`, and `preserved_seed_entry`, the one place that builds the manifest entry of a preserved seed.
- `src/refract/planner.py`: `Operation.seed_base`; equality with the generated version is checked first; the rules for older manifests.
- `src/refract/renderer.py`: `render_project(..., generator_version=...)`, used to ask what Refract would have generated under an earlier version.
- `src/refract/apply.py`, `src/refract/protocol.py`: a preserved seed is recorded through `preserved_seed_entry`, in the written manifest and in the plan document.
- `src/refract/templates/core/bin/docs-check.py` and `.refract/bin/docs-check`: skip `.refract/`.
- `docs/ARCHITECTURE.md`: states the seed-hash rule.

## Review history

1. The first version carried a customized seed's manifest entry forward. Review found that it still lost edits on the first upgrade of an already affected project and kept a re-adopted seed marked customized.
2. The second version added rules for older manifests but also new policy: it released edited obsolete seeds from the manifest, moved the recorded hash to the newest generated version, and exempted every manifest-listed file from `docs-check`. Review found problems in each addition, and that an ownership change needs an ADR (ADR-0005 decision 10).
3. The third version keeps the first version's rule, keeps the older-manifest protection with an explicit "base unknown" state, and drops the added policy.

## Validation evidence

Recorded in the pull request.

## Review

Independent review before merge, recorded in the pull request.
