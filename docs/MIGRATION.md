# Migrating an Existing Agent Setup

Use this guide to adopt refract in a repository that already has hand-made agent configuration, such as `CLAUDE.md`, `.claude/skills`, `.pi/`, or a committed `settings.local.json`.

## 1. Preview

Run refract inside the project root, never in a folder that groups several repositories:

```bash
refract retrofit --platform claude,codex,opencode,omp --dry-run --yes --target /path/to/project
```

The plan lists every path and its action. It also prints **migration findings** about the existing setup:

| Finding | What to do |
|---|---|
| `.claude/settings.local.json` is committed | Move shared policy to `.claude/settings.json` (`--permissions`), then untrack the local file; it holds personal settings |
| `.claude/claude.json` exists | Claude Code ignores it; move anything useful into documentation or real settings |
| `.pi/` exists | Pi is deprecated; select `omp` instead |
| Skills exist only in `.claude/skills` | Codex, OpenCode, and omp read `.agents/skills`; copy project-specific skills there to share them |
| `CLAUDE.md` does not import `@AGENTS.md` | Keep shared rules in `AGENTS.md` and import it from `CLAUDE.md` so the two files cannot drift |

## 2. Resolve conflicts

By default, any unmanaged file at a generated path is a `CONFLICT`, and the apply stops without changing anything. You have two options for each conflicting path.

- **Adopt refract's version.** Move or merge your file aside, then re-run. Do this for generic files you no longer need to customize.
- **Keep yours.** Re-run with `--keep-existing`:
  - Every conflicting unmanaged file is kept as project-owned (`SKIP_UNMANAGED`). refract never adopts it into its manifest and never overwrites it.
  - When you keep a skill (for example your own `research`), refract does not generate its copies of that skill for the other agents (`SKIP_KEPT`), so every agent sees exactly one version. To give Codex, OpenCode, and omp the same skill, copy yours into `.agents/skills/<name>/SKILL.md`.
  - Keeping `.claude/settings.json` or `.codex/config.toml` means refract's hooks, MCP, and permission settings for that platform are not installed; the plan warns about this.

`--keep-existing` never overrides a refract-owned file that was edited after generation, a symlink, or a non-regular file. Those remain conflicts.

## 3. Apply and configure

```bash
refract retrofit --platform claude,codex,opencode,omp --keep-existing --yes --target /path/to/project
```

Then:

1. Fill in `docs/DEPLOYMENT.md` and set `Status: CONFIGURED`. `.refract/bin/deploy-ready` must pass before the deploy skills will act.
2. If you kept your own `AGENTS.md` or `docs/DEVELOPMENT_PROCESS.md`, compare them with the generated seeds (preview them in a temporary directory) and bring over the skill workflow table and the Deploy section.
3. Move domain-specific skills (integrations, language and cloud checklists) into `.agents/skills` so every agent can use them, and keep them out of user-level directories.
4. Clean up user-level skills that earlier global installs left behind (see `docs/PLATFORM_SUPPORT.md`).

## 4. Validate

```bash
.refract/bin/validate
.refract/bin/docs-check
```

Re-running the same retrofit later is idempotent. Kept files stay untouched, and customized seeds are preserved, with a note when their generated version changed.
