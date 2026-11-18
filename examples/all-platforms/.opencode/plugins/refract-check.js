// refract deterministic end-of-turn validation (never invokes an LLM).
// Runs the project validator when a session goes idle and logs the result.
export const RefractCheck = async ({ $, worktree }) => {
  return {
    event: async ({ event }) => {
      if (event.type !== "session.idle") return
      const result = await $`${worktree}/.refract/bin/agent-check --format plain`.nothrow().quiet()
      if (result.exitCode !== 0) {
        console.error(result.stdout.toString())
      }
    },
  }
}
