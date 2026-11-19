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

The rule and its states are decided in ADR-0013.

- [x] A seed is replaced or removed only when its content is shown to be Refract's own output.
- [x] The manifest keeps the hash of the generated version a seed started from, never the hash of the edited file, and states this with `"seed_hashes": "generated"`.
- [x] A preserved seed never blocks an apply, whether the path is still generated or obsolete.
- [x] A seed made identical to the generated version is tracked as generated again.
- [x] Under a manifest without the key (0.3.0 or earlier), seed hashes are not trusted: a seed is recognized only by content, and any other seed is kept with an all-zero "base unknown" hash and a note that says how to take the generated version.
- [x] A manifest's seed claim is ignored for Refract control paths.
- [x] The plan document's `resulting_ownership` equals the manifest that apply writes.
- [x] `docs-check` ignores paths under `.refract/`; other configuration paths are still reported.
- [x] This repository's `.refract/bin/docs-check` is identical to the packaged template, and a test keeps it so.
- [x] There is one test per state, and each rule has a test that fails when the rule is switched off.

## Out of scope

Tracked in issue #20:

- Handing an edited seed back to the project, so that Refract stops claiming it.
- A way to acknowledge a changed generated seed while keeping the edits.
- The generator version footer in editable seeds.
- Recognizing an unedited seed under an older manifest when a template or a project fact changed.
- Exempting other generated files from `docs-check`.

## Key changes

- `docs/adr/0013-editable-seed-ownership.md`: the rule (Proposed).
- `src/refract/manifest.py`: `seed_hashes` key, `Manifest.tracks_generated_seeds`, `UNKNOWN_SEED_BASE`, and `preserved_seed_entry`, the one place that builds the manifest entry of a preserved seed.
- `src/refract/planner.py`: `Operation.seed_base` and the rules of ADR-0013.
- `src/refract/renderer.py`: `render_project(..., generator_version=...)`, used to render the current templates with an earlier version string.
- `src/refract/apply.py`, `src/refract/protocol.py`: a preserved seed is recorded through `preserved_seed_entry`, in the written manifest and in the plan document.
- `src/refract/templates/core/bin/docs-check.py` and `.refract/bin/docs-check`: skip `.refract/`.
- `docs/ARCHITECTURE.md`: states the rule.

## Review history

1. The first version carried a customized seed's manifest entry forward. Review found that it still lost edits on the first upgrade of an already affected project and kept a re-adopted seed marked customized.
2. The second version added rules for older manifests, released edited obsolete seeds from the manifest, moved the recorded hash to the newest generated version, and exempted every manifest-listed file from `docs-check`. Review found problems in each addition.
3. The third version dropped the additions and reported edited or unverifiable obsolete seeds as conflicts. Review found that this blocked upgrades in two ordinary cases.
4. The fourth version stops deciding case by case. ADR-0013 states one rule, the planner applies it to every state, and each state has a test.

## Validation evidence

Recorded in the pull request.

## Review

Independent review before merge, recorded in the pull request.
