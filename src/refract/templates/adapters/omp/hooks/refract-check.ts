// refract deterministic end-of-turn validation (never invokes an LLM).
// Runs the project validator after each agent run and surfaces failures.
import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";

export default function (pi: HookAPI) {
	pi.on("agent_end", async (_event, ctx) => {
		const top = await pi.exec("git", ["rev-parse", "--show-toplevel"]);
		if (top.code !== 0) return;
		const root = top.stdout.trim();
		const { stdout, code } = await pi.exec(`${root}/.refract/bin/agent-check`, ["--format", "plain"], {
			cwd: root,
			timeout: 120_000,
		});
		if (code !== 0 && ctx.hasUI) {
			ctx.ui.notify(stdout.trim(), "warning");
		}
	});
}
