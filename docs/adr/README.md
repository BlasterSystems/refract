# Architecture Decision Records

Read this index first and load only records relevant to the current scope.

| ADR | Status | Scope | Tags | Summary | Supersedes |
|---|---|---|---|---|---|
| [ADR-0001](0001-portable-core-and-platform-adapters.md) | Accepted | Generator architecture | portability, adapters | Separate provider-neutral core from platform adapters | — |
| [ADR-0002](0002-adr-lifecycle-and-progressive-disclosure.md) | Accepted | Documentation architecture | adr, progressive-disclosure | Index ADRs and load only relevant decisions | — |
| [ADR-0003](0003-opt-in-integrations-and-safe-apply.md) | Accepted | Security and generation | safety, manifest | Make integrations opt-in and writes ownership-aware | — |
| [ADR-0004](0004-defer-llm-wiki-integration.md) | Proposed | Documentation architecture | documentation, progressive-disclosure, llm-wiki | Defer wiki integration and define pilot triggers | — |
| [ADR-0005](0005-agent-guided-bootstrap-with-deterministic-core.md) | Accepted | Generator interface and trust boundary | agents, llm, safety, portability, retrofit | Add optional LLM guidance over the deterministic core | — |
| [ADR-0006](0006-opt-in-security-audit-skill.md) | Proposed | Documentation architecture | security, integrations, progressive-disclosure | Add the security-audit skill as an install-on-demand capability with tiered triggers | — |
| [ADR-0007](0007-install-on-demand-task-breakdown-skills.md) | Proposed | Documentation architecture | planning, integrations, progressive-disclosure | Add install-on-demand task-breakdown and ticket skills with tracker-neutral wiring | — |
| [ADR-0008](0008-omp-platform-adapter.md) | Superseded | Generator architecture | platforms, omp, adapters, portability | Add OhMyPi (omp) as a fifth selectable platform with a minimal adapter emitting the sticky invariant file | — |
| [ADR-0009](0009-pre-exposure-repository-hardening.md) | Proposed | Repository operations | security, ci, supply-chain, dependencies | Harden the public repository before increased exposure: security policy, SHA-pinned CI, Dependabot, and local tool state hygiene | — |
| [ADR-0010](0010-native-capability-parity.md) | Accepted | Generator architecture and platform support | platforms, adapters, parity, omp, hooks, permissions, scope | Render every capability natively on Claude, Codex, OpenCode, and omp from one registry; project-scope guard; deprecate Pi | ADR-0008 |

Valid statuses: `Proposed`, `Accepted`, `Rejected`, `Deprecated`, `Superseded`.

Accepted ADRs are historical. Replace them by creating a new ADR and cross-linking the supersession.
