# ADR-0009: Pre-exposure repository hardening

- **Status:** Proposed
- **Date:** 2026-11-18
- **Decision owners:** Not assigned
- **Scope:** Repository operations, CI, and documentation
- **Tags:** security, ci, supply-chain, dependencies
- **Supersedes:** None
- **Superseded by:** None

## Context

Refract is a public repository whose output is instructions that agents execute. A pre-exposure review (task file `tasks/pre-exposure-hardening.md`, 2026-11-18) confirmed the code-level trust boundaries hold, but found the repository operations side missing pieces expected of an exposed, security-adjacent project: no vulnerability-reporting policy, actions pinned by mutable tag only, no automated action updates, and local agent tool state left as untracked residue.

## Decision drivers

- Users of a bootstrap tool must have a channel to report vulnerabilities in the tool itself, separate from `docs/SECURITY_AUDIT.md`, which documents the optional audit skill.
- GitHub Actions tags are mutable; a compromised action tag would execute inside this repository's CI with `contents: read` and workflow-scope token access.
- The generated workflow template (`src/refract/templates/integrations/github/docs-check.yml`) is a release-versioned artifact rendered into user projects; its pinning strategy must stay readable and coherent across releases.
- Untracked files (`uv.lock`, `.mcp.json`, `.serena/`) are local agent and tool state; leaving them untracked invites accidental commits during exposure.
- The golden tree must reflect what `--platform all` actually renders after ADR-0008 added omp, because `docs/GENERATED_OUTPUT.md` claims to be the exact all-platform output.

## Considered options

### Option 1: Publish a security policy, pin repository workflows by SHA, automate action updates, and ignore local tool state (selected)

- Add `SECURITY.md` routing vulnerability reports to GitHub private vulnerability reporting, with supported versions, scope, and response expectations.
- Pin the repository's own workflow actions to commit SHAs with version comments; add Dependabot (`github-actions`, weekly).
- Keep the *generated* template tag-pinned: it is versioned with each refract release and users can run Dependabot in their own projects.
- Gitignore `.serena/`, `.mcp.json`, and `uv.lock` under the existing "Local agent and tool state" section.
- Pin the golden tree and `docs/GENERATED_OUTPUT.md` to the true all-platform render (`tests/golden/all-platforms/tree.txt`), and assert executable modes in the golden tests.

### Option 2: Pin the generated template by SHA as well

Maximum supply-chain strictness for user projects, but every refract release would need to bump opaque hashes rendered into other repositories, and generated workflows become unauditable prose. Rejected for the template; the repository's own workflows keep the strict behavior.

### Option 3: Do nothing

The gaps stay until an incident or an external report surfaces them. Rejected: the cost is a handful of small files.

## Decision

Adopt Option 1. A security policy is published; the repository's own CI pins actions by commit SHA and tracks updates through Dependabot; generated templates keep tag pins; local agent tool state is ignored by Git; the golden tree is bound to the true all-platform render including executable-mode assertions.

## Consequences

### Positive

- Vulnerability reports have a defined channel and response contract.
- CI cannot execute a mutated action tag; Dependabot keeps pins current.
- `git status` is clean in a fresh clone; accidental commits of local tool state are impossible.
- The advertised generated output is exact again, including file modes.

### Negative

- Dependabot opens weekly PRs for action updates.
- The generated template and repository workflows intentionally differ in pinning style; this must stay documented here and in the template comment.

## Implementation and validation

1. `SECURITY.md`, `.github/dependabot.yml`, SHA-pinned `.github/workflows/*.yml`, `.gitignore` entries, regenerated golden tree, and mode assertions landed on `fix/pre-exposure-hardening`.
2. Gates: full unittest suite, `refract validate --target .`, `.refract/bin/validate`, `docs-check`, wheel build, and fresh all-platform apply compared against the golden tree.
3. Branch protection with required status checks is a repository setting outside this repository; it is requested separately and does not change any file.

## Revisit triggers

- Publishing to PyPI: revisit the reporting channel and supported-version table.
- The generated template gains secrets or write-scope token usage: SHA-pin the template too.
- A second maintainer or a bot account changes the local-tool-state tradeoff: revisit `.gitignore` entries.

## References

- `docs/THREAT_MODEL.md` — trust boundaries and explicit limitations
- `docs/SECURITY_AUDIT.md` — the optional audit skill and its release gate
- ADR-0003 — opt-in integrations and safe apply
- ADR-0008 — omp platform adapter (golden-tree consequences)
- `tasks/pre-exposure-hardening.md` — the review that produced this decision
