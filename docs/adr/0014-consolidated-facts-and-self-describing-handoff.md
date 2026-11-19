# ADR-0014: Consolidated fact resolution and a self-describing agent handoff

- **Status:** Accepted
- **Date:** 2026-11-19
- **Decision owners:** Project owner (accepted 2026-11-19)
- **Scope:** Fact resolution and validation, stored configuration, kept files, and the agent-guided preview and apply handoff
- **Tags:** agents, facts, handoff, retrofit, safety, configuration
- **Supersedes:** None
- **Superseded by:** None

## Context

ADR-0005 placed an optional agent-guided layer over the deterministic core. Its trust model has held: repository evidence and agent proposals are untrusted, the core renders and plans, and a human confirms in an interactive terminal.

The entry paths built on that model have not held. A project review on 2026-11-19, after five review rounds on two pull requests, found these structural problems (details and evidence in `tasks/research-entry-path-consolidation.md`):

- Plain mode and agent-guided mode detect project facts with different code, and the same repository yields different facts in 14 cases.
- The two modes also validate facts differently. Agent-guided mode rejects characters such as `#` and `[`, so text that plain mode accepts and stores cannot be previewed.
- `.refract/config.json` stores every confirmed fact and feature, and no code reads it back. A re-run without the original flags reverts facts, changes the platform set, and schedules feature files for removal. `--keep-existing` is not stored either, so a re-run without it conflicts on every kept file.
- Some facts cannot be set, others cannot be cleared, and the same input normalizes differently in a preview and in an apply.
- Only a 64-character identifier crosses from the agent's preview to the human's apply. The human retypes the flags and answers 13 prompts, and a mismatch cannot say what differs.
- A preview is about 163 KB, and the running code does not know which commit it was built from.

These are decisions about what Refract trusts, what a dry run may write, and what the human must confirm. They need a record.

## Decision drivers

- Keep the ADR-0005 trust model: untrusted evidence and proposals, a deterministic core, human confirmation in a trusted terminal.
- Give both modes the same facts and the same validation for the same repository.
- Make a re-run idempotent without retyping flags.
- Remove every preview and apply divergence that the human did not cause.
- Tell the human what differs when a plan identifier does not match.
- Keep privileged features opt-in and visible.
- Add no runtime dependency and no new subcommand.

## Considered options

### Option 1: Patch each defect

Fix the open issues one by one and keep two detectors, two validation regimes, write-only configuration, and the identifier-only handoff.

This is the smallest change. It is also what the five review rounds did, and each round found a similar number of new problems, because every new flag or prompt reopens the same gaps.

### Option 2: Consolidate the entry paths

One fact resolver, one detector, and one validation regime for both modes, stored configuration as a source, and a handoff file that carries the previewed request. The core, the trust model, and the command surface stay.

This removes the causes. It changes behavior in plain mode and amends four decisions of ADR-0005.

### Option 3: Agent-first redesign

Add `plan` and `apply` subcommands, make a plan file the primary artifact, and treat plain mode as legacy.

This is the cleanest end state. It replaces the command surface that ADR-0005 decision 6 kept, invalidates the existing documentation and tests at once, and can be reconsidered after option 2.

## Decision

Adopt option 2. The owner selected it on 2026-11-19.

### Fact resolution

1. **One resolver and one detector serve both modes.** Human-confirmable facts resolve through ordered layers: default, detected, stored, answers file, intent file, flag, and an edit at the interactive confirmation. The first layer that supplies a value wins, for every field including feature booleans. The bounded, no-follow inspection of ADR-0005 decision 1 is the only detector; the separate plain-mode detector is removed. Components are derived: they are detected on every preview and never layered.
2. **Ticket conventions are detected through the hardened git helper in both modes,** including `refract inspect`. Detection reads the subjects of the last 100 commits and needs at least three matches. A detected ticket prefix is a proposal: it is applied only after confirmation, and a non-interactive run reports it without applying it.
3. **Stored configuration is a source.** A later `init` or `retrofit` on a managed project starts from the facts, platforms, and features in `.refract/config.json`. The file is used only when the manifest lists it and its hash matches, and it is read through the hardened loader.
4. **Stored configuration is a repository-supplied claim, like the manifest.** It is trusted as much as the rest of the repository and no more. Interactive and agent-guided runs display its values for confirmation. A non-interactive run names every privileged feature that is enabled only because the stored configuration says so.
5. **Kept files persist per path.** When an apply keeps an unmanaged file under `--keep-existing` (ADR-0012), the manifest records the path. Later runs keep exactly the recorded paths without the flag. A collision at any other path is still a conflict. Refract control paths can still never be kept. `--remove-obsolete` is never stored.
6. **One validation regime applies to every source and every mode, and prose is escaped when rendered.** Input rules cover length, Unicode normalization, control and format characters, template delimiters, and backticks in commands. Markdown-significant characters in a prose fact are escaped by the renderer instead of being rejected at input.
7. **One normalization step applies to every source and every mode,** including dry-run and prompt answers. For commands and the ticket prefix, an empty value and the literals `none` and `null` mean "not configured".
8. **Every human-confirmable fact can be set and cleared.** Languages become settable by flag, answers file, and intent file. Each feature gains an explicit off switch.

### Handoff

9. **A dry run may write one handoff file** when the caller names a path with `--handoff`. The path must be outside the target. The file is created exclusively, without following symlinks, with owner-only permissions. A dry run still writes nothing inside the target and nothing to Git.
10. **The handoff file is an untrusted proposal.** It carries the previewed request and plan document, the plan identifier, and the generator version and commit. It carries no file content. The apply loads it through a strict loader, applies the input rules to every field, recomputes rendering and planning with its own code, and displays and confirms as ADR-0005 decision 8 requires. A handoff file cannot suppress the display or the confirmation.
11. **With a handoff file, the human retypes nothing but the identifier.** Request flags are rejected together with `--handoff`. The apply uses the request as written and does not detect again. The existing flag-based handoff keeps working.
12. **Refract computes the labels it shows at the confirmation.** It compares each fact with the stored value and with a fresh detection and labels it accordingly. It never displays a source claimed by the handoff file.
13. **The integrity check runs before the questions, against the request as previewed.** On a mismatch Refract displays the recomputed plan, states which component differs (generator, target, a named file, or the templates), and writes nothing.
14. **A human may change a fact at the confirmation and continue.** Refract recomputes the plan, names the change and the new identifier, displays the complete plan, and asks for confirmation.
15. **Each enabled privileged feature is confirmed by its own question.** Features that are off are not asked about.
16. **Machine formats report errors as data.** In `json` and the new `summary` format, a runtime error is a JSON object with `status: "error"`. Exit codes do not change.
17. **Refract reports the commit it was built from** when the installation records one. The commit appears in `--version`, the summary, and the handoff. It is not part of the plan identifier.

### Relation to earlier records

ADR-0005 and ADR-0012 stay Accepted. This record changes the following and leaves everything else in force:

| Earlier decision | Change |
|---|---|
| ADR-0005 decision 1: inspection excludes VCS locations | Amended. Ticket-convention detection may read commit subjects through the hardened git helper (decision 2 above) |
| ADR-0005 decision 2: languages and components are evidence-derived | Amended. A human may set languages and an agent may propose them; components stay derived (decisions 1 and 8) |
| ADR-0005 decision 3: field validation rejects Markdown delimiters | Amended. Markdown-significant characters are escaped at render instead (decision 6) |
| ADR-0005 decision 13: dry-run artifacts are emitted to stdout only | Amended. A dry run may also write one handoff file to a caller-named path outside the target (decision 9) |
| ADR-0005 decision 8: the apply displays and confirms | Clarified. The integrity check precedes the questions; display and confirmation are unchanged (decision 13) |
| ADR-0005 decision 9: a changed request requires renewed review | Clarified. The renewed review may happen in the same trusted terminal session (decision 14) |
| ADR-0012: `--keep-existing` is chosen per run | Extended. Paths kept by an apply are recorded and stay kept (decision 5) |

## Consequences

### Positive

- The same repository yields the same facts, under the same validation, in both modes.
- A bare re-run of a managed project plans no changes, including one set up with `--keep-existing`.
- A preview and an apply cannot disagree unless something actually changed, and Refract names what changed.
- An agent reads about 5 KB instead of 163 KB.
- A wrong fact can be corrected at apply without a new preview.
- Legitimate text such as `C#` works in every mode.

### Negative

- Plain mode changes behavior: detection is bounded and no longer follows symlinked manifests, feature flags are layered instead of OR-combined, and a re-run uses stored values. This needs a minor release with each change called out.
- Rendered Markdown changes once for projects whose facts contain escaped characters.
- A dry run gains one write, outside the target.
- The apply has two input styles (handoff file, or flags) until the flag style is retired.
- Two new schemas (summary and handoff) and one manifest addition (`kept`) must be versioned and tested.

### Risks and mitigations

- **Forged stored configuration.** A repository can ship a configuration and a matching manifest. It grants nothing that committing the generated files would not. Values pass the input rules, are displayed in interactive runs, and privileged features that carry over are named in non-interactive runs.
- **Escaping defects.** An unescaped character could let proposed text add Markdown structure to generated instructions. One escape function is applied in the renderer and tested with the existing injection payloads, which must render as inert text.
- **Forged handoff file.** It carries a request, not files. The core recomputes everything, the loader rejects unknown fields, labels are computed by Refract, and display and confirmation are unconditional.
- **Handoff file left on disk.** It contains project facts and file hashes, not file contents. It is created with owner-only permissions at a path the caller chose.
- **Edits at apply weaken the integrity check.** The check runs first, against the request as previewed. Edits happen afterwards, by the human, and are followed by a full display and confirmation.
- **Ticket detection runs git on untrusted repositories.** It uses the hardened helper that plain mode already uses, which disables repository-configured programs.

## Implementation and validation

Phases and acceptance criteria are in `tasks/research-entry-path-consolidation.md`; sequencing and file-level work packages are in `tasks/plan-entry-path-consolidation.md`. This record was Accepted before phase 2 started.

1. Safety net: documented commands are parsed and documented flows are executed by tests; one script runs every CI check. It does not depend on this record.
2. Fact pipeline (decisions 1 to 8). Evidence: each of the 14 detector differences becomes a fixture test with one expected result; a bare re-run of a managed project plans no changes; a test proves the preview request equals the apply request for the same inputs; injection payloads render inert.
3. Handoff (decisions 9 to 17). Evidence: a flow test applies from a handoff file with no retyped flags; each mismatch cause has a test; an edit at apply continues after a new display; a forged handoff cannot skip display or confirmation, or relabel a fact.
4. Release identity.

Phases 2 and 3 receive a security review before merge. `docs/AGENT_GUIDED.md`, `docs/THREAT_MODEL.md`, `docs/ANSWERS.md`, `docs/PROMPTS.md`, and the packaged `refract` skill are updated with the phase that changes their subject.

## Revisit triggers

- A verified host integration can supply user-presence authorization (ADR-0005 decision 8). The handoff could then be applied by an agent.
- Stored configuration needs authentication, for example because Refract starts to act on it without display.
- Users ask for `plan` and `apply` subcommands, or the two apply input styles cause confusion (option 3).
- Monorepos need facts per component.
- Escaping proves insufficient for a rendering context, for example a new template format.

## References

- `tasks/research-entry-path-consolidation.md`
- `tasks/fix-customized-seed-overwrite.md`
- ADR-0003, ADR-0005, ADR-0012, ADR-0013
- GitHub issues #14, #17, #18, #20; pull requests #13, #16, #19
