// refract deterministic end-of-turn validation (never invokes an LLM).
// Runs the project validator when a session goes idle and logs the result.
import { existsSync } from "node:fs"
import { dirname, join, resolve } from "node:path"

function projectRoot(start) {
  let dir = resolve(start)
  while (true) {
    if (existsSync(join(dir, ".refract/bin/agent-check"))) return dir
    const parent = dirname(dir)
    if (parent === dir) return undefined
    dir = parent
  }
}

export const RefractCheck = async ({ $, directory }) => {
  return {
    event: async ({ event }) => {
      if (event.type !== "session.idle") return
      const root = projectRoot(directory)
      if (!root) return
      const result = await $`python3 -I ${join(root, ".refract/bin/agent-check")} --format plain`.nothrow().quiet()
      if (result.exitCode !== 0) {
        console.error(result.stdout.toString())
      }
    },
  }
}
