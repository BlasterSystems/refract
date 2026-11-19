# ADR-0013: Editable seeds are replaced only when shown to be generated

- **Status:** Proposed
- **Date:** 2026-11-19
- **Decision owners:** Project owner (decision pending)
- **Scope:** Ownership manifest and planning of editable seeds
- **Tags:** ownership, manifest, seeds, retrofit, safety
- **Supersedes:** None
- **Superseded by:** None

## Context

Refract generates some files as editable seeds, for example `AGENTS.md`, `docs/DEPLOYMENT.md`, and the pull request template. ADR-0003 and ADR-0005 decision 10 promise that a customized seed is preserved. The planner recognizes a customized seed by comparing its content with the hash in `.refract/manifest.json`.

Through 0.3.0, an apply that rewrote the manifest recorded a customized seed's current hash. On the next run the file looked unedited. A template or fact change then replaced the project's edits without a conflict, and `--remove-obsolete` could delete an edited seed that Refract no longer generated.

Fixing the recording is not enough. Manifests already written this way cannot be told apart from correct ones, and the fix raises questions the code never answered: what the recorded hash means for an edited file, and what happens to an edited seed that Refract stops generating.

## Decision drivers

- Never overwrite or delete project content that Refract cannot show to be its own output (`AGENTS.md` working rule 4).
- A file the project edited must not block later runs.
- Unedited seeds should keep updating where that can be shown safely.
- Projects already affected by the defect must be protected when they upgrade.
- Keep the manifest schema version, and keep every existing action name.

## Considered options

### Option 1: Record the base hash and add no rule for older manifests

Carry a customized seed's recorded hash forward and change nothing else.

This stops new damage. It does nothing for manifests that already hold an edited hash: because `AGENTS.md` embeds the generator version, the first run after an upgrade replaces those edits.

### Option 2: Record the newest generated hash for a customized seed

Move the recorded hash to the latest generated version on every apply.

The note that the generated seed changed then appears once per change. It discards the only record of which generated version the edits started from, and a note that was printed once in a non-interactive run is lost.

### Option 3: Release an edited seed from the manifest when it becomes obsolete

Drop the manifest claim and treat the file as unmanaged.

This removes the conflict. It also changes who owns the path: if the feature is enabled again, the file collides with the generated one as an unmanaged file.

### Option 4: Replace a seed only when it is shown to be generated

Keep the base hash, state in the manifest what a seed hash means, distrust seed hashes in manifests that do not say so, and keep (never remove, never conflict on) an obsolete seed that is not shown to be unedited.

This protects affected projects and blocks nobody. Under an older manifest it can recognize an unedited seed only in limited cases.

## Decision

Adopt option 4.

1. **A seed hash is the hash of a generated version.** For an editable seed the manifest records the hash of the generated version its content started from, never the hash of an edited file. The manifest states this with `"seed_hashes": "generated"`.
2. **A seed is shown to be generated** when its content equals the version Refract generates now, or, under a manifest that tracks seed hashes, the recorded hash.
3. **A seed that is not shown to be generated is preserved.** Its recorded hash is carried forward unchanged. It never blocks an apply.
4. **A seed that matches the generated version again is tracked as generated again.**
5. **A manifest without the key is not trusted for seeds.** It was written by 0.3.0 or earlier. Under it:
   - A seed is shown to be generated only when its content equals the current version, or what the current templates and facts render with that manifest's version string.
   - Any other seed is preserved and recorded with an all-zero hash that means "base unknown". Its note says, on every run, to delete the file and re-run to take the generated version.
   - The manifest is rewritten with the key on the first apply.
6. **An obsolete seed that is not shown to be unedited is kept.** Refract keeps the manifest claim, does not remove the file even with `--remove-obsolete`, and does not report a conflict. Deleting the file drops it. An obsolete seed that is shown to be unedited is removed only with `--remove-obsolete`, as before.
7. **A seed that became a fully generated file** is updated when it is shown to be generated and is a conflict otherwise, as for any modified generated file.
8. **Only Refract decides what is a seed.** A manifest's claim is ignored for Refract control paths.

Decision 6 changes one outcome that ADR-0005 decision 10 left in place: an edited obsolete seed was a conflict. It is now kept without blocking. Ownership does not change: Refract still claims the path.

## Consequences

### Positive

- Project edits to a seed survive every re-run, upgrade, and `--remove-obsolete`.
- Projects already affected by the defect keep their edits when they upgrade.
- An edited seed never blocks an apply.
- The plan document and the written manifest use one function for a preserved seed's entry.

### Negative

- Under an older manifest, an unedited seed is recognized only after a pure version change. If a template or a project fact changed as well, the seed is kept with the "base unknown" note until the project deletes it or brings it in line.
- The note that a generated seed changed stays on every run until the file matches the generated version. There is no way yet to acknowledge it and keep the edits.
- The manifest gains one key, and all zeros becomes a reserved hash value.

### Risks and mitigations

- **A forged manifest claims a path as a seed.** The claim can only make Refract keep a file or report a conflict. It cannot cause a write, and it is ignored for control paths.
- **A forged manifest claims seed tracking.** Behavior is then what 0.3.0 had for every manifest. Whoever can forge the manifest can already change the files.
- **Users miss the "base unknown" note in non-interactive runs.** The note is printed on every run, not once.

## Implementation and validation

Implemented with `tasks/fix-customized-seed-overwrite.md`:

- `manifest.py`: the `seed_hashes` key, `UNKNOWN_SEED_BASE`, and `preserved_seed_entry`.
- `planner.py`: `Operation.seed_base` and the rules above.
- `apply.py` and `protocol.py`: both record a preserved seed through `preserved_seed_entry`.

Evidence:

- One unit test per state: manifest with or without seed tracking, content shown to be generated or not, and the path still generated, obsolete, or now fully generated.
- Each rule has a test that fails when the rule is switched off.
- Four projects created with the released 0.3.0, including one affected by the defect, behave as decided when run with the fix.

## Revisit triggers

- Projects need to hand an edited seed back to themselves, so that Refract stops claiming it.
- Projects need to acknowledge a changed generated seed while keeping their edits.
- An editable seed stops embedding the generator version, which would make unedited seeds recognizable in more cases.
- Stored project facts become readable on a re-run (entry-path consolidation), which would let the older-manifest check use the facts the project was generated with.

## References

- `tasks/fix-customized-seed-overwrite.md`
- ADR-0003, ADR-0005 (decision 10), ADR-0012
- Pull request #19
