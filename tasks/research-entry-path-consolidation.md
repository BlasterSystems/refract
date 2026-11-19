# Research: Entry-path consolidation

One fact pipeline, a handoff that explains itself, and documentation that tests run.

- **Status:** Proposed design, awaiting owner approval. No code until approved.
- **Decision record:** [ADR-0014](../docs/adr/0014-consolidated-facts-and-self-describing-handoff.md) (Proposed). It must be Accepted before phase 2 starts.
- **Tracker:** this file. Detailed implementation plan: [plan-entry-path-consolidation.md](plan-entry-path-consolidation.md). GitHub issues #14, #17, and #18 are closed by phase 2.
- **Evidence baseline:** commit `2336f77` (`main` after #13 and #16). File and line references below are to that commit.

## Summary

Five review rounds on #13 and #16 found about seventy problems. A project review on 2026-11-19 traced nearly all of them to five causes, none in the generator core. This design removes the causes instead of patching the symptoms:

1. **One fact pipeline.** One detector, one validation and normalization step, and `.refract/config.json` read back as a source, so both modes agree and a re-run keeps what was confirmed.
2. **A handoff that explains itself.** The preview writes a handoff file. The human applies from it and retypes nothing except the plan identifier. A mismatch says what differs.
3. **Docs under test.** Every documented command is parsed by the real argument parser, and every documented preview and apply pair runs end to end.
4. **Process gates.** One local command runs everything CI runs.
5. **Release identity.** Documented commands pin a release tag, and Refract reports the commit it was built from.

The generator core (model, renderer, planner, apply, manifest, adapters) and the ADR-0005 trust model stay as they are.

## Why

The owner's direction: "the focus of this cli app should be the agentic angle" and "we need to make this process flawless".

Success looks like this:

- An agent with nothing installed sets up any repository with one preview command and a short report.
- The human applies with one command typed from the documentation, plus a file path and an identifier.
- When preview and apply disagree, Refract says which part differs and what to do.
- A re-run never loses a confirmed fact, a selected platform, an enabled feature, a kept file, or a user edit.
- A document cannot ship a command that does not run.

No design makes this flawless. The aim is that this class of defect is caught by a test before a reviewer or a user sees it.

## Goals

- **G1.** Plain mode and agent-guided mode derive the same facts from the same repository, under the same validation.
- **G2.** Facts, platforms, features, and kept files persist across re-runs without retyping flags.
- **G3.** Every human-confirmable fact can be set and cleared from every input (flag, answers file, intent file, prompt). Components are derived and are the one exception.
- **G4.** At apply, the human types one fixed command plus a file path and an identifier.
- **G5.** A plan identifier mismatch names the component that differs.
- **G6.** The agent-facing preview output is at most about 5 KB.
- **G7.** Tests parse every documented `refract` command and execute every documented preview and apply pair.
- **G8.** One local command reproduces every CI check.
- **G9.** Documented install and run-in-place commands pin a release tag.

## Non-goals

- New `plan` or `apply` subcommands (option C below).
- Agent-callable apply, or authenticated, expiring, or multi-party approvals.
- Merging or adopting unmanaged files.
- Monorepo or multi-component detection. Facts still come from the repository root.
- Pseudo-terminal tests on Windows.
- Publishing to PyPI. That is an open decision for the owner (see Open decisions).

## Anti-goals

The design has failed, even if it works, when any of these is true:

- A privileged feature becomes enabled without a human having seen it named.
- A handoff file can make the apply skip the plan display or the confirmation.
- A preview writes inside the target repository.
- A command or prompt exists in two places that must be kept in sync by hand.
- A flag, exit code, or `--plan-format json` key changes meaning without being listed under Behavior changes below.

## Constraints

- `AGENTS.md` working rules, including: never overwrite unmanaged files, keep the portable core provider-neutral, privileged features are opt-in, render structured formats through serializers.
- No runtime dependencies. Python 3.11 or later.
- The ADR-0005 trust model stays: repository evidence and agent proposals are untrusted, the deterministic core renders and plans, and a human confirms in an interactive terminal.
- Accepted ADRs are not edited. ADR-0014 amends four numbered decisions of ADR-0005 (1, 2, 3, and 13), clarifies two (8 and 9), extends ADR-0012, and leaves the rest in force.
- The existing flag-based handoff (`--expected-plan` with retyped flags) keeps working.

## Current state

Condensed from three code surveys run on 2026-11-19. Each claim was read in code; most were also reproduced against scratch projects.

### Facts have two detectors, two validation regimes, and no memory

- One resolver, `_request_from_args` (`src/refract/cli.py:109-235`), picks a detector by mode: `inspect_project` for agent-guided (`cli.py:114-117`), `detect_project` otherwise (`cli.py:118-120`).
- The same repository yields different facts in 14 cases (Appendix A).
- Validation also differs by mode. Plain mode applies `model.py:49-74`. Agent-guided mode additionally applies the proposal rules of `protocol.py:68-96` to every final value (`cli.py:204-218`), which reject characters such as `#` and `[`. A description "Billing API in C# [beta]" is accepted and stored by plain mode and rejected by an agent-guided preview. A directory named `C#-app` cannot be previewed at all.
- `.refract/config.json` stores every fact and feature (`renderer.py:104-137`) and no code path reads it back. A bare `retrofit --yes` on a project set up for Claude only reverted the name, description, commands, and ticket prefix, created files for all five platforms, and marked the hook files for removal.
- `--keep-existing` is not stored either. After the documented setup with that flag, a re-run without it exits with a conflict on every kept file (`planner.py:183-198`, `321-329`).
- `languages` and `components` come from detection only (`cli.py:223`, `cli.py:228`). No flag, answers key, or intent field sets them.
- Feature flags are `store_true` and OR-combined across sources (`cli.py:152-173`), so no source can switch a feature off.
- Normalization differs by path. A command given as `""` stays `""` in a preview and becomes null at the interactive apply (`cli.py:179-181`), so identical flags always mismatch. The literal `none` is a command everywhere, and the generated pre-commit hook would run it.
- Under `--yes`, the detected ticket prefix is dropped (`cli.py:140`); other detected values are kept.

The three open issues restate parts of this: #14 (agent-guided mode never detects the ticket prefix), #17 (`retrofit` does not read facts back from `.refract/config.json`), #18 (flags cannot clear a command or set languages).

### The handoff carries only a hash

- The plan identifier hashes 12 keys (`protocol.py:334-386`): schema, generator version, target path, target-root state, request, desired files, observed files, operations, resulting ownership, `remove_obsolete`, `keep_existing`, and the manifest claim.
- Nothing else crosses from preview to apply. The human retypes the flags and answers 13 prompts. Refract holds only the 64 characters of the preview, so on a mismatch it can print two hashes and nothing more (`cli.py:375-378`).
- Things that change the identifier without anyone intending it: permission bits of kept files, the target directory's mode, a different commit with the same version string, and detection drift (deleting 100 unrelated files changed the detected languages).
- A four-platform preview is 163 KB. `diffs` is 77% of it. There is no compact format.
- Exit code 2 means both an argparse usage error and a plan conflict. On a runtime error, stdout is empty even in JSON mode.

### A release has no identity

- The version is a static literal (`src/refract/__init__.py:3`, `pyproject.toml:7`). Every commit between releases reports the same version, and every documented install follows `main`.
- The running code does not know its commit. A git-based install does record it in `direct_url.json` (PEP 610), which the standard library can read.
- The name `refract` on PyPI belongs to an unrelated project.

### Docs describe flows that no test runs

- No test reads a command from `README.md` or `docs/*.md`.
- No test runs a preview followed by an interactive apply. Apply tests use a fake terminal and an identifier computed in-process (`tests/unit/test_agent_guided_cli.py:17-61`).
- Agent-guided preview and apply commands appear in about a dozen places. The 0.3.0 version floor is written by hand in eight. The identifier placeholder has three spellings.
- `scripts/sync-version.py` updates one field in `.refract/config.json`. It does not cover `docs/PROJECT_SUMMARY.md` or any literal in `README.md` or `docs/PROMPTS.md`.

### The process let a docs change become a code change without its gates

- #13 began as three documentation files and ended with wrapper and CLI changes. Neither #13 nor #16 had a task file, an ADR, or a review of its final commits.
- `.refract/bin/docs-check` classifies changes by substrings in path names. It failed #13 from commit 6 to commit 8 because a test path contains "integration", and nobody saw it until the last round.
- No single local command runs everything CI runs. The strict docs check appears only in the workflow file.
- CI does not test any documented install method except `pip install .`.

## Approaches

| | What changes | Trade-off |
|---|---|---|
| **A. Patch the list** | Fix each open issue and add one documentation test | Smallest. Keeps two detectors, write-only configuration, and the hash-only handoff, so the same problems return with each new flag |
| **B. Consolidate the entry paths** | One fact pipeline, a self-describing handoff, docs under test. Core and trust model stay | Four phases and one new ADR. The handoff changes need care |
| **C. Agent-first redesign** | New `plan` and `apply` commands. Plain mode becomes legacy | Cleanest end state. Breaks the command surface and ADR-0005 decision 6 in one step |

**Picked: B**, by the owner on 2026-11-19. A was the path of the five review rounds and did not converge. C can be reconsidered once B's foundations exist; nothing in B blocks it.

## Design

### 1. One fact pipeline

**One resolver module.** A new `src/refract/facts.py` owns resolution. `cli.py` passes it the parsed inputs and receives the request and a list of notes. Layers, lowest to highest:

1. Default
2. Detected
3. Stored (`.refract/config.json`)
4. Answers file
5. Intent file
6. Flag
7. Edit at the interactive confirmation

The first layer that supplies a value wins, for every human-confirmable field, including booleans. This replaces the OR-combination of features.

**One detector.** `inspection.py` becomes the only detector, for both modes, and `detection.py` is removed. Plain mode therefore gains the limits, exclusions, and no-follow rules, and stops following symlinked manifests. Appendix A lists the 14 current differences and the single expected result for each.

- A root manifest that exists as a regular file identifies its stack by presence, even when its content cannot be read. Commands then stay unset and `facts_incomplete` is true with the reason.
- A symlinked manifest or marker is treated as absent and sets `facts_incomplete`.
- Root names matched by suffix (`*.sln`, `*.csproj`) are found by listing the root, independent of the file budget and of the secret-name exclusions, because their content is never read.

**Ticket prefix.** Detection moves into the shared detector and keeps using the hardened git helper (`gitsafe.py`), so `refract inspect` also runs `git log`. It requires the prefix in at least three of the last 100 commit subjects, which removes false positives such as `UTF` from "Switch to UTF-8". A detected prefix is a proposal: it is offered as the default at the interactive confirmation, and under `--yes` it is reported in a note and not applied. This makes today's undocumented `--yes` behavior explicit.

**Stored configuration is a source.** When a project is managed, a later `init` or `retrofit` starts from the stored facts, platforms, and features.

- It is used only when the manifest lists `.refract/config.json` and the file's hash matches the manifest entry, and it is read through the same hardened loader as an intent file.
- It is as trusted as the rest of the repository, no more. In interactive and agent-guided runs the values are displayed for confirmation, as detected values are today.
- In a `--yes` run, any privileged feature that is on only because the stored configuration says so is listed in one line of the plan output.
- When a detected value differs from the stored one, the stored value wins and the plan carries a note, for example "detected test command `npm test` differs from the stored value".
- Components are derived and never layered: they are detected on every preview, and the stored value is ignored.

**Kept files persist per path.** When an apply keeps an unmanaged file because of `--keep-existing`, the manifest records that path in a new `kept` list. A later run keeps exactly those paths without the flag. A new collision at any other path is still a conflict unless `--keep-existing` is passed again. A kept path whose file is later removed leaves the list, and Refract generates the file. Refract control paths can still never be kept. `--remove-obsolete` is an action for one run and is never stored.

**One validation regime, with escaping at render.** Today's stricter agent-guided rules exist to stop proposed text from injecting Markdown structure into `AGENTS.md`. Rejecting characters also rejects legitimate text such as `C#`. The design replaces rejection with escaping:

- Every source in every mode passes one set of input rules: length limits, Unicode normalization, no control or format characters (so no newlines), no template delimiters, and no backticks in commands.
- When a prose fact (name, description, a language, the ticket prefix) is rendered into Markdown, the renderer escapes Markdown-significant characters. Commands are rendered inside code spans, as today.
- The existing injection payload tests are kept and re-targeted: each payload must render as inert text.

**Every human-confirmable fact can be set and cleared.**

| Field | Set from | Clear with |
|---|---|---|
| name | flag, intent, answers, stored; default is the stored name, then the directory name | cannot be cleared |
| description | flag, intent, answers, stored | empty value |
| languages (free text, one validated entry each) | new `--language` (repeatable), intent, answers, stored, detected | `--language none` |
| components | detected only | not applicable |
| build, test, run command | flag, intent, answers, stored, detected | `none`, or JSON null |
| ticket prefix | flag, intent, answers, stored, detected | `none`, or JSON null |
| platforms | flag, intent, answers, stored; default all | not applicable |
| each feature | `--feature` and new `--no-feature`, intent, answers, stored; default off | `--no-feature`, or `false` |

**One normalization step**, applied to every source and to prompt answers before the request is built, in every mode including dry-run:

- Text is stripped.
- For commands and the ticket prefix, an empty value and the literals `none` and `null` (any case) become null.
- Platforms accept a string or a list and expand `all`.
- Booleans are three-state: on, off, or not supplied.

The invariant, enforced by a test: for the same inputs, the request built for a preview equals the request built for an apply where the human accepts every default.

### 2. A handoff that explains itself

**Preview.** `init` and `retrofit` accept `--handoff PATH` with `--agent-guided --dry-run`.

- Refract writes a handoff document to `PATH`: the 12 hashed keys of the plan, the plan identifier, and the generator version and commit. It has no diffs and is about 30 KB.
- `PATH` must be outside the target. The file is created exclusively (no overwrite, no symlink following) with mode 0600.
- Standard output carries a summary of about 5 KB in a new `summary` plan format:
  - status, plan identifier, handoff path, generator version and commit, and target;
  - the request, with the source of each fact (flag, intent, answers, stored, detected, or default);
  - a count of operations by action;
  - every operation that is not a plain create or no-change;
  - warnings and notes.
- `--plan-format json` is unchanged and remains available for full detail.

**Apply.** The human runs one fixed command. The documented agent prompts all preview with `retrofit`, which handles empty repositories too, so the documentation shows one apply command:

```bash
refract retrofit --agent-guided --handoff <HANDOFF_FILE> --expected-plan <PLAN_ID> --target .
```

`init` accepts `--handoff` as well, for a handoff made by an `init` preview.

1. Refract loads the handoff through a hardened loader (regular file, size limit, strict schema, unknown keys rejected).
2. It checks that the document hashes to its recorded identifier and that this equals `--expected-plan`. If not, it stops: the file is not the preview the human was told about.
3. It checks that the subcommand and the target match the handoff. If they do not, it names the right subcommand or the previewed target.
4. It rejects any request flag given together with `--handoff`. The handoff is the single source, so nothing is retyped.
5. It builds the request from the handoff as written, after the input rules above. Components must come from the detector's fixed vocabulary. It does not detect again. It recomputes the plan with its own renderer and planner.
6. On a mismatch it displays the recomputed plan, as ADR-0005 decision 8 requires, then a "what changed since the preview" section, and stops without writing.
7. Otherwise it shows the facts and asks the human to accept them or edit individual ones. Each enabled privileged feature gets its own yes or no question.
8. If the human edited anything, Refract recomputes, names what changed, and shows the new identifier. In both cases it displays the complete plan and asks for final confirmation.

**Labels at the confirmation are computed by Refract, never read from the handoff.** For each fact, the apply compares the handoff's value with the stored value and with a fresh detection, and labels it "same as stored", "same as detected", or "proposed", showing the stored value when it differs. A handoff therefore cannot present its own proposal as a stored or detected value. This comparison only produces labels; it never changes the request.

**Mismatch explanation.** Refract compares the handoff document with the recomputed one, key by key:

| Differs | Message |
|---|---|
| Generator version or commit | "Preview: refract 0.5.0 (commit abc1234). Here: refract 0.5.0 (commit def5678). Run the same Refract on both sides." |
| Target | "The preview was made for `/a/b`; this is `/c/d`." |
| Observed files | "`AGENTS.md` changed after the preview", per path, with whether content or permissions changed |
| Desired files, same version | "Refract's templates differ: the two copies are different commits." |

**Edits at apply no longer dead-end.** The integrity check runs against the request as previewed. An edit made afterwards by the human in the trusted terminal is the human's own decision: Refract recomputes, displays the new plan, and asks again. This also applies to the existing flag-based handoff, where the check now runs before the questions.

**Machine-readable errors.** In `json` and `summary` formats, a runtime error prints a JSON object with `status: "error"` on standard output. Exit codes do not change. One table in `docs/AGENT_GUIDED.md` documents them. Agents key on `status`, not on the exit code.

**Generator identity.** `refract --version` prints the commit when it is known, for example `refract 0.5.0 (commit 2336f77)`. The commit comes from `direct_url.json` for git-based installs, or from the checkout's `.git` when run through `scripts/refract.sh`. It is reported in the summary and the handoff, and it is not hashed into the identifier.

### 3. Docs under test

- **One home per flow.** Each prompt and its apply command live once, in `docs/PROMPTS.md`. `README.md` and other documents link to them.
- **Parsed commands.** A test extracts every `refract …`, `scripts/refract.sh …`, and `uvx --from … refract …` invocation from `README.md`, `AGENTS.md`, and `docs/*.md`, substitutes placeholders, and parses it with the real argument parser and argument validation. An unknown flag or an invalid combination fails the test.
- **Executed flows.** Each documented preview and apply pair carries a marker comment. A test runs the preview in a fixture repository, takes the identifier, and runs the apply in a pseudo-terminal, answering with defaults. It asserts the result and runs `validate`. The fixtures include an empty repository, an existing agent setup, and a hostile one (a `token.py`, a `refract/` package, 250 documentation files, an oversized lockfile, ticket-style commits).
- **Literals.** A test ties every hand-written version literal in the documentation to one constant, and `sync-version.py` updates them. The identifier and file placeholders get one spelling each.
- **Mirrored documents.** A test compares the template documents that the repository's own `docs/` claims to mirror.

### 4. Process gates

- **`scripts/check.sh`** runs the test suite, both validators, `docs-check --strict` against the merge base, `sync-version.py --check`, and a wheel build with an installed-CLI smoke test in a temporary environment. CI calls this script, so local and CI results match.
- **`docs-check`** stops classifying paths under test directories (`tests/`, `test/`, `__tests__/`, `spec/`). Matching is otherwise unchanged. The script is generated into every project, so this changes generated output and ships with the next release.
- **A pull request template** for this repository asks for the task file, the ADR decision, the `check.sh` result, and an independent review of the final commit.
- **`docs/DEVELOPMENT_PROCESS.md`** gains two rules. A documentation change that needs a code change stops, and the code change gets its own task and pull request first. A commit pushed after the last review needs a new review or a waiver recorded in the pull request.
- **CI install matrix.** One job runs the documented install methods (pipx, `uv tool`, `uvx`, virtual environment, clone and wrapper) against the pull request's commit on an image whose Python is externally managed, then runs one documented flow.

### 5. Release identity

- Documented install and run-in-place commands pin the current tag, for example `git+https://github.com/BlasterSystems/refract@v0.5.0`. `sync-version.py` rewrites them at release time. Following `main` is documented as the development option.
- `docs/RELEASING.md` uses `scripts/check.sh` for its gate, so the wheel check no longer assumes setuptools in the system Python.
- PyPI is an open decision (below).

## Follow-ups outside this design

The seed-overwrite fix (`tasks/fix-customized-seed-overwrite.md`, #19, ADR-0013) left these product questions open on purpose. They are tracked in issue #20 and are not part of this design:

- **Handing an edited seed back to the project**, so that Refract stops claiming the path.
- **Acknowledging a changed generated seed** while keeping the edits. Today the "generated seed changed" note stays until the file matches the generated version.
- **The version footer in editable seeds.** `AGENTS.md` embeds the generator version, so every release changes the generated seed and triggers that note for every customized `AGENTS.md`.
- **Exempting generated files from `docs-check`.** A Refract upgrade that regenerates files such as `.claude/settings.json` still trips the configuration heuristic.

Phase 2 helps one of ADR-0013's limits: once stored facts are readable, the check for seeds under a 0.3.0 manifest can use the facts the project was generated with.

## Behavior changes

Each ships in a minor release and is called out in the changelog.

**Phase 1**

- The generated `docs-check` script ignores test directories.

**Phase 2**

- Plain mode uses the bounded detector: file and size limits apply, and symlinked manifests are not followed.
- A command given as `none`, `null`, or an empty value means "not configured". Today `none` is a literal command.
- On a managed project, an omitted `--platform` means the stored platforms. Today it means all platforms.
- Feature flags are layered and gain `--no-feature`. Today sources are OR-combined.
- A re-run of a managed project uses stored facts and kept paths.
- A detected ticket prefix needs three matching commits.
- One validation regime: characters such as `#` and `[` are accepted in every mode and escaped in rendered Markdown, so files that contain such facts are re-rendered once.
- `refract inspect` runs `git log` through the hardened helper and reports the ticket prefix.
- `.refract/manifest.json` gains a `kept` list.

**Phase 3**

- New `--handoff` option and `summary` plan format.
- The identifier check runs before the questions, and an edit at apply continues after a new display.
- In machine formats, a runtime error is a JSON object on standard output.
- `refract --version` may include the commit.

## Phases

Each phase has its own task file, tests written first, and an independent review of the final commit before merge.

| Phase | Content | Done when |
|---|---|---|
| 0 (in review, #19) | Seed-overwrite fix (ADR-0013); `docs-check` ignores `.refract/` | Merged; 0.3.1 released |
| 1. Safety net | Sections 3 and 4, against today's flows. No change to the CLI | `scripts/check.sh` equals CI; every documented command parses; every documented flow runs in a pseudo-terminal |
| 2. Fact pipeline | Section 1. Closes #14, #17, #18. Needs ADR-0014 Accepted | Appendix A is a fixture test per row; a bare re-run of a managed project, including one set up with `--keep-existing`, plans no changes; the normalization invariant test passes; injection payloads render inert |
| 3. Handoff | Section 2; prompts moved to `--handoff` | A flow test applies from a handoff with no retyped flags; each mismatch cause in the table has a test; an edit at apply continues after a new display; a forged handoff cannot skip display, confirmation, or relabel a fact |
| 4. Release identity | Section 5 | Documented commands carry the release tag, kept by `sync-version.py` and a test |

**Slicing phases 2 and 3.** Each is two pull requests. The first adds the code, its tests, and the protocol documentation. The second is the release: the version bump together with the prompt and README changes that use the new flags. User-facing documentation on `main` therefore never describes a flag that the pinned release lacks.

## Calls I made

These are my decisions, not the owner's. Each can be overturned at review. The first two are security-relevant and are repeated under Open decisions.

1. **Stored configuration is trusted like other repository content.** Under `--yes` it is used without a prompt, and privileged features that carry over are listed in the output. The alternative, requiring flags again on every re-run, is what makes upgrades lose features today.
2. **One validation regime with escaping at render** replaces the stricter agent-guided rejection rules (ADR-0005 decision 3). The alternative keeps two regimes and leaves text such as `C#` unusable in agent-guided mode.
3. **A dry run may write the handoff file** to a caller-named path outside the target. ADR-0005 decision 13 says a dry run writes nothing, so ADR-0014 amends it. The alternative is shell redirection plus a second command to summarize, which is more steps for the agent to get wrong.
4. **The apply uses the handoff's request as written** and does not detect again. This removes detection drift between preview and apply. The request is still validated, displayed, and confirmed.
5. **Fact labels at apply are computed by Refract**, not read from the handoff.
6. **Kept files are recorded per path in the manifest.** A stored blanket `keep_existing` switch would silently keep future collisions.
7. **Plain mode adopts the bounded detector.**
8. **Features are layered, not OR-combined.** `docs/ANSWERS.md` already claims flags override the file; today that is false for booleans.
9. **A detected ticket prefix needs confirmation and three matching commits.**
10. **Exit codes stay as they are.** Conflict and usage error both remain 2; `status` in the JSON distinguishes them.
11. **The typed identifier stays at 64 characters.** Shortening it is not needed once nothing else is retyped.
12. **Languages become settable free text; components stay derived and are never stored as a source.**
13. **The documented agent prompts all use `retrofit`.** `init` stays for plain mode and accepts `--handoff` for its own previews.
14. **Phases 2 and 3 each end with a release pull request** that carries the user-facing documentation.
15. **The design lives in `tasks/` and an ADR**, following this project's process.

## Open decisions for the owner

1. **Call 1.** Confirm that stored privileged features may carry over under `--yes` with a notice.
2. **Call 2.** Confirm that escaping at render may replace rejection of Markdown characters. Both calls get a security review in phase 2 either way.
3. **PyPI.** `refract` is taken. Publishing as `refract-cli` (the command stays `refract`) would make `uvx --from refract-cli refract` and `pipx install refract-cli` work, and it would stop an agent that improvises `pip install refract` from getting another project. It needs an account, an owner for the name, and a publishing workflow. Recommended, after phase 4.

## Left to the builder

- Module layout inside `facts.py`, and whether `inspection.py` is split.
- Exact JSON field names of the summary and handoff schemas, within the content listed above.
- The Markdown escape set and where in the renderer it is applied, within the rule above.
- The wording of prompts, notes, and mismatch messages.
- The marker syntax that ties a documented command to a flow test.
- Fixture construction, and the size limit for the handoff loader.
- Whether `check.sh` is a shell script or a Python script.

## Risks

- **Stored configuration as an attack surface.** A repository can ship a forged configuration and manifest. Mitigation: it grants nothing that committing the generated files directly would not, values pass the input rules and are displayed, and carried-over privileged features are named. Covered by the security review of phase 2.
- **Escaping bugs.** An unescaped character could let proposed text add Markdown structure to `AGENTS.md`. Mitigation: one escape function, applied in the renderer, tested with the existing payload set plus new ones; the security review of phase 2.
- **The handoff file as an attack surface.** An agent can write any handoff. Mitigation: it carries a request, not files; the core recomputes everything; display and confirmation are unconditional; labels are computed by Refract; the loader is strict.
- **Behavior changes in phase 2** could surprise users of plain mode. Mitigation: a minor release with each change called out in the changelog.
- **Pseudo-terminal tests can be flaky.** Mitigation: drive on prompt text, not on timing, and skip where no pseudo-terminal exists.
- **Scope.** Four phases can sprawl. Mitigation: phase 1 changes no CLI behavior and protects the rest; each phase is releasable on its own.

## Appendix A: detector differences and expected results

Each row becomes one fixture test in phase 2. "Today" is the result of plain detection, then of agent-guided inspection.

| # | Case | Today (plain / agent-guided) | Expected |
|---|---|---|---|
| 1 | Ticket-style commits (`ABC-12 …`) | `ABC` / none | `ABC` proposed when at least three subjects match; `UTF` from "Switch to UTF-8" is not proposed |
| 2 | `.ts` only outside the root and `src/` (for example `lib/a.ts`) | JavaScript / TypeScript | TypeScript |
| 3 | `.ts` only in an excluded directory, under a secret-like name, or binary | TypeScript / JavaScript | JavaScript, unless `tsconfig.json` is a regular root file |
| 4 | `tsconfig.json` is a directory | TypeScript / JavaScript | JavaScript |
| 5 | `package.json` with a byte-order mark | Node without commands / commands found | Commands found |
| 6 | `package.json` whose root is a list | Error / Node without commands | Node without commands, no error |
| 7 | `package.json` or `pyproject.toml` that is not UTF-8 | Error / stack omitted | Stack identified by presence, commands unset, `facts_incomplete` with the reason |
| 8 | `package.json` over the size limit | Node with commands / no Node | Stack identified by presence, commands unset, `facts_incomplete` |
| 9 | Symlinked manifest | Followed / ignored silently | Treated as absent, `facts_incomplete` with the reason |
| 10 | Symlinked lockfile or `gradlew` | `pnpm`, `./gradlew` / `npm`, `gradle` | Treated as absent (`npm`, `gradle`), `facts_incomplete` with the reason |
| 11 | `requirements.txt` is a directory | Python / none | None |
| 12 | Root `.sln` with a secret-like name (`TokenService.sln`) | C# / none | C# |
| 13 | More than 200 root files before the `.sln`, or more than the entry limit | C# / missed, with `facts_incomplete` false or true | C# when the root listing completes; otherwise `facts_incomplete` |
| 14 | Both `.sln` and `.csproj` at the root | Evidence names differ | The `.sln` is the evidence |
