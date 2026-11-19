---
name: security-check
description: Pre-commit security review of changed files. Look for secrets, injection, authorization, data isolation, and trust-boundary flaws, and report only findings with a demonstrated boundary and result, as CRITICAL, WARNING, and INFO.
---

# Security Check

Review the staged and changed files, and the code they touch, before committing. The aim is real, reachable vulnerabilities, not checklist deviations. Report only what you verified.

## What counts as a finding

For every candidate, name all six parts:
1. the **lower-trust actor** (anonymous user, other tenant, plugin, upstream service)
2. the **input or action** they control
3. the **intended control** that should stop them
4. the **boundary** that is crossed
5. the **affected principal or resource**
6. the **concrete result**

If you can't name all six, it isn't a finding.

Then put the candidate in one of three states:
- **`confirmed`**: the source path, and where possible a local check, shows the result.
- **`needs_validation`**: a specific fact that decides it is outside the repository, such as a proxy, provider setting, identity policy, or deployment topology. Name the exact missing fact and a safe way for the owner to check it. Never assume the control is present or absent. A `needs_validation` record has **no severity**.
- **`rejected`**: the source refutes it. Don't report it.

Evidence stays bounded and local:
- Read the code. Run only the project's existing tests or a minimal local test of your own.
- Never touch deployed, live, or shared environments.
- Stop at the minimum result that proves the point, such as a wrong return value or an unauthorized dummy record.

## Severity (confirmed findings only)

| Label | Severity | Anchor |
|---|---|---|
| **CRITICAL**: must be fixed before commit | critical | An unauthenticated actor gains code execution, full data-store access, or takeover of arbitrary accounts. |
| | high | An explicit security control is fully defeated with real consequences: authentication bypass, cross-tenant read or write, stored script execution affecting other users, authenticated code execution, an unauthenticated remote stop of a shared service. |
| **WARNING**: should be fixed | medium | A real boundary violation with limited blast radius, uncommon preconditions, or narrow scope. |
| | low | Disclosure of non-secret internals, or an effect needing sustained effort for minimal gain. |
| **INFO** | informational | A minimal-impact observation, every `needs_validation` record, and the review notes below. |

To tell high from medium: does the result fully defeat an explicit control for an action with real consequences, or only weaken it? If you can't state the concrete damage, the severity is lower than it feels. Severity never exceeds the impact you showed.

Before reporting a CRITICAL, re-read every cited location. Where the platform allows, have a fresh read-only context try to refute it.

## Where to look in the diff

**Always check:**
1. **Secrets**: hard-coded passwords, tokens, keys, connection strings, or credentials in code, tests, fixtures, or logs. Example and template files with obvious placeholders don't count. A real secret is always CRITICAL.
2. **Injection**: queries, shell commands, templates, paths, or URLs built from untrusted input instead of parameters or safe APIs. That includes **second-order** use: stored data later used as a path, query, template, regex, or URL.
3. **Authorization**: new or changed entry points without authentication and authorization consistent with the project's existing pattern. Ask whether it is the *right* check for the business rule, not just whether a check exists. Can another operation reach the same effect without it?
4. **Data isolation**: scoped reads and writes without their isolation filter, or scope taken from client-supplied identifiers instead of trusted context.

**Then the angles that the diff touches:**
- **Trust between components**: what component A guarantees, compared with what B assumes. Look at truncation, type coercion, normalization, tenant scope. Data from storage, config, or plugins is trusted only if every path that writes it validated it.
- **State and ordering**: skipped, replayed, or reordered steps; partial failure without rollback; non-atomic check-then-act races; expiry and revocation windows; boundary moments and clock skew.
- **Defaults and fallbacks**: the security posture when config is missing, a flag is off, a dependency is down, or a migration is half-done.
- **Numbers**: negative, zero, overflow, precision loss, string-to-number coercion.
- **Indirect disclosure**:
  - export, backup, or search that returns data above the caller's access
  - responses that differ between "not found" and "no access"
  - preview or draft content leaking through listings or caches
- **Server-side fetches**: user-supplied webhook, callback, or notification URLs fetched by the server, including after redirects.
- **Capability growth**: tokens, API keys, OAuth, plugins, MCP, or AI tools gaining scope after delegation, refresh, caching, role change, or composition.
- **Restore paths**: undelete, rollback, or import that skips current ownership, validation, or authorization.

**Lower-severity checks** (WARNING if confirmed):
- internal error details returned to clients
- personal or sensitive data in logs
- debug output in production code
- concurrency patterns the project forbids
- missing validation on new external inputs

**Review notes** (INFO):
- new TODO, FIXME, or HACK comments
- known-vulnerable dependencies, from the ecosystem's audit command when available
- security-relevant configuration changes

## Don't report

- Checklist deviations or missing best practices with no reachable boundary violation.
- Defense-in-depth advice presented as a vulnerability.
- Guessed provider, proxy, browser, identity, or deployment behavior. Use `needs_validation` instead.
- Self-impact, or authority the same principal is meant to have.
- A parser or runtime effect stronger than the one you observed.
- A severity on a `needs_validation` record.

## Fixes

For each confirmed finding, name the invariant the code must enforce. Then give the narrowest source change that enforces it at the last trusted decision point, with a regression test. Prefer specific changes to generic hardening advice.

## Report

```
CRITICAL: <finding> - <path:line> - <actor → boundary → result> - <smallest fix>
WARNING:  <finding> - <path:line> - <actor → boundary → result> - <smallest fix>
INFO:     <finding or needs_validation: the missing fact and how the owner can check it>
Result: PASS (no CRITICAL findings) | FAIL
```

Never weaken a control, test, or check to make this report pass. This check covers one change. For a whole-project audit, see `docs/SECURITY_AUDIT.md`.

*Parts of this skill are adapted from Cloudflare's security-audit skill (MIT License). See `NOTICE.md` in this folder.*
