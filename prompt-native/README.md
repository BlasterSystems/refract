# refract, prompt-native (spike)

A throwaway experiment. It tests whether refract can be content only: no CLI, no Python, so any supported agent sets up the process from one prompt. The code in `src/` is untouched. See the decision record in the session plan before keeping anything from here.

## Use

In Claude Code, Codex, OpenCode, or omp, inside the project to set up:

> Set up this project with the refract process. Clone https://github.com/BlasterSystems/refract at branch `new-approach` into a temporary folder outside this project, then read and follow `prompt-native/BOOTSTRAP.md` from it.

For a local trial, point the agent at this folder's path instead of the URL.

## Layout

| Path | What it is |
|---|---|
| `BOOTSTRAP.md` | The entry procedure the agent follows |
| `content/` | Files copied into the target (from `src/refract/templates/core`, with CLI references replaced by skills) |
| `content/skills/process-check` | The structural check that replaces `.refract/bin/validate` |
| `content/skills/refract` | Re-runs and upgrades from the release recorded in `.refract.md` |
| `fragments/` | Text inserted when a fact is set (ticket lifecycle) |
| `platforms/` | One note per platform: native files, opt-in features, support row |

## Not carried over

- The GitHub docs-check workflow and the git pre-commit hook. Both ran Python scripts.
- Pi, which is deprecated.
