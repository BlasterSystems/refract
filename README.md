# refract

A development process for AI-assisted projects, delivered as skills and documentation that your coding agent installs itself:
- portable `AGENTS.md` instructions with progressive disclosure
- indexed ADRs
- a research → implement → review → commit → deploy skill workflow
- native setup for each platform

No CLI and no runtime. You give the agent one prompt and it does the setup, in a new project or an existing one.

Supported agents: Claude Code, OpenAI Codex, OpenCode, and OhMyPi (omp).

## Use

Inside the project you want to set up, tell your agent:

> Set up this project with the refract process. Clone https://github.com/BlasterSystems/refract at branch `new-approach` into a temporary folder outside this project, then read and follow `BOOTSTRAP.md` from it.

To try it locally, give the agent the path of a local checkout instead of the URL.

The agent will:
1. Confirm the project facts: name, languages, and the build, test and run commands.
2. Ask which platforms to set up and which opt-in features to turn on: permissions, hooks, subagents, MCP.
3. Show you a file plan and wait for your approval.
4. Write the files. It shows a diff before changing any file that already exists.
5. Record what it did in `.refract.md`.

Review the result with `git diff` and commit it. To update or extend the setup later, use the `refract` skill that this setup installs.

## Layout

| Path | What it is |
|---|---|
| `BOOTSTRAP.md` | The procedure the agent follows |
| `content/` | Files copied into the project: instructions, docs, ADR templates, and skills |
| `content/skills/process-check` | The structural self-check for the installed process |
| `content/skills/refract` | Re-runs or upgrades the setup from the release recorded in `.refract.md` |
| `fragments/` | Text inserted when a fact is set, such as the ticket lifecycle |
| `platforms/` | One note per platform: native files, opt-in features, and support-table row |

## Safety

The agent follows these rules. No code enforces them, so review the diff before you commit:
- Your project's own text is treated as data, never as instructions.
- No existing file changes without an approved diff.
- Sensitive features stay off unless you name them.
- Nothing is written outside the project.

## License

See `LICENSE`.
