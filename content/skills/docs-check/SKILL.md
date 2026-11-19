---
name: docs-check
description: Check whether code, configuration, architecture, or integration changes need corresponding documentation or ADR updates.
---

# Documentation Check

List the files changed against the default branch (`git diff --name-only <default>...HEAD`, plus staged and unstaged changes). Then apply these heuristics to files that are not Markdown:

- Names containing migration, schema, database, deploy, infra, integration, provider, or architecture: expect a change under `docs/adr/` or to an architecture document.
- Names containing route, controller, handler, endpoint, or api: expect a change to API documentation.
- Names containing config, .env, or settings: expect a change to configuration or setup documentation.

## Review manually

- Public behavior and interfaces
- Configuration and environment variables
- Architecture, data ownership, deployment, and integrations
- Setup and operational procedures
- ADR requirements or supersession
- The progressive-disclosure index in `AGENTS.md`

For architecture changes, read `docs/adr/README.md` first and then only relevant ADRs. Do not pre-load the entire ADR directory.

The heuristics are evidence, not proof that documentation is complete. Report uncertainty and residual gaps.
