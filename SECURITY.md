# Security Policy

## Supported versions

Refract is pre-1.0. Only the latest tagged release and `main` receive security fixes.

| Version | Supported |
|---|---|
| latest tag | Yes |
| older tags | No |

## Reporting a vulnerability

Use GitHub private vulnerability reporting on this repository (**Security → Report a vulnerability**). Do not open a public issue for a suspected vulnerability.

Include:

- affected command (`init`, `retrofit`, `inspect`, `validate`) and full invocation;
- minimal reproduction: target layout, `.refract/manifest.json`, and the intent or answers file if one is involved;
- expected versus actual behavior and the concrete impact;
- affected version (`refract --version`).

Do not include secrets, credentials, or third-party repository content in the report.

## Scope

- **In scope:** the CLI, packaged templates, generated artifacts, manifest/plan/apply integrity, bounded inspection, and the trust boundaries documented in `docs/THREAT_MODEL.md`.
- **Out of scope:** vulnerabilities in a generated project's own code; hosts where an agent already holds equivalent filesystem permissions; issues listed under "Explicit limitations" in `docs/THREAT_MODEL.md`.

## Response expectations

- Acknowledgement within 7 days.
- Confirmed vulnerabilities ship with the next patch release and are credited in `CHANGELOG.md` unless the reporter prefers anonymity.
- Coordinated disclosure: please allow a reasonable window before publishing details.
