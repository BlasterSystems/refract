from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from refract.apply import apply_plan
from refract.capabilities import capability_warnings
from refract.planner import build_plan
from refract.renderer import render_project
from tests.helpers import request


class PlatformContractTests(unittest.TestCase):
    def test_claude_uses_official_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files = render_project(request(Path(directory), ["claude"], mcp=True, agents=True))
            self.assertIn("CLAUDE.md", files)
            self.assertIn(".claude/skills/refract/SKILL.md", files)
            self.assertIn(".claude/skills/docs-check/SKILL.md", files)
            self.assertIn(".claude/skills/semantic-versioning/SKILL.md", files)
            self.assertIn(".claude/agents/architecture-reviewer.md", files)
            self.assertIn(".claude/settings.json", files)
            self.assertNotIn(".claude/settings.local.json", files)
            self.assertIn(".mcp.json", files)
            self.assertNotIn(".claude/claude.json", files)

    def test_codex_uses_agents_and_toml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files = render_project(request(Path(directory), ["codex"], mcp=True, agents=True))
            self.assertIn("AGENTS.md", files)
            self.assertIn(".agents/skills/refract/SKILL.md", files)
            self.assertIn(".agents/skills/docs-check/SKILL.md", files)
            self.assertIn(".agents/skills/semantic-versioning/SKILL.md", files)
            self.assertIn(".codex/config.toml", files)
            self.assertNotIn(".codex.md", files)
            tomllib.loads(files[".codex/config.toml"].content.decode())

    def test_pi_is_deprecated_portable_core_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            req = request(Path(directory), ["pi"], mcp=True, agents=True, hooks=True)
            files = render_project(req)
            self.assertIn("AGENTS.md", files)
            self.assertIn(".agents/skills/refract/SKILL.md", files)
            self.assertFalse(any(path.startswith(".pi/") for path in files))
            self.assertNotIn(".refract/bin/agent-check", files)
            effective = json.loads(files[".refract/config.json"].content)["features"]["effective_by_platform"]["pi"]
            self.assertEqual({"mcp": False, "agents": False, "hooks": False}, effective)
            warnings = capability_warnings(req.features)
            self.assertTrue(any("deprecated" in warning for warning in warnings), warnings)
            self.assertTrue(any("no built-in MCP" in warning for warning in warnings), warnings)

    def test_omp_has_native_parity_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            req = request(Path(directory), ["omp"], mcp=True, agents=True, hooks=True)
            files = render_project(req)
            self.assertEqual(
                [
                    ".omp/RULES.md",
                    ".omp/agents/architecture-reviewer.md",
                    ".omp/hooks/post/refract-check.ts",
                    ".omp/mcp.json",
                    ".omp/settings.json",
                ],
                sorted(path for path in files if path.startswith(".omp/")),
            )
            self.assertNotIn(".mcp.json", files)
            settings = json.loads(files[".omp/settings.json"].content)
            self.assertEqual("always-ask", settings["tools"]["approvalMode"])
            self.assertFalse(settings["autolearn"]["enabled"])
            mcp = json.loads(files[".omp/mcp.json"].content)
            self.assertEqual({"type": "http", "url": "https://mcp.context7.com/mcp"}, mcp["mcpServers"]["context7"])
            agent = files[".omp/agents/architecture-reviewer.md"].content.decode()
            self.assertIn("\nname: architecture-reviewer\n", agent)
            self.assertNotIn("bash", agent.split("---")[1])
            self.assertEqual([], capability_warnings(req.features))
            effective = json.loads(files[".refract/config.json"].content)["features"]["effective_by_platform"]["omp"]
            self.assertEqual({"mcp": True, "agents": True, "hooks": True}, effective)

    def test_claude_and_codex_ship_safe_policy_and_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files = render_project(request(Path(directory), ["claude", "codex"], hooks=True))
            claude = json.loads(files[".claude/settings.json"].content)
            self.assertIn("Read(./.env)", claude["permissions"]["deny"])
            self.assertNotIn("allow", claude["permissions"])
            stop = claude["hooks"]["Stop"][0]["hooks"][0]
            self.assertIn(".refract/bin/agent-check --format json", stop["command"])
            codex = tomllib.loads(files[".codex/config.toml"].content.decode())
            self.assertEqual("on-request", codex["approval_policy"])
            self.assertEqual("workspace-write", codex["sandbox_mode"])
            self.assertFalse(codex["sandbox_workspace_write"]["network_access"])
            hooks = json.loads(files[".codex/hooks.json"].content)
            self.assertIn(".refract/bin/agent-check\" --format json", hooks["hooks"]["Stop"][0]["hooks"][0]["command"])
            plain = render_project(request(Path(directory), ["claude", "codex"]))
            self.assertNotIn("hooks", json.loads(plain[".claude/settings.json"].content))
            self.assertNotIn(".codex/hooks.json", plain)
            self.assertIn(".codex/config.toml", plain)

    def test_agent_check_blocks_once_then_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root, ["claude"], hooks=True)
            apply_plan(build_plan(root, render_project(req)), ["claude"])
            check = root / ".refract/bin/agent-check"
            ok = subprocess.run(
                [str(check), "--format", "json"], cwd=root, input='{"stop_hook_active": false}',
                text=True, capture_output=True, timeout=60, check=False,
            )
            self.assertEqual(0, ok.returncode, ok.stderr)
            self.assertEqual({}, json.loads(ok.stdout))
            (root / "AGENTS.md").write_text("changed {" + "{TOKEN}}\n", encoding="utf-8")
            def decide(active: bool) -> dict:
                result = subprocess.run(
                    [str(check), "--format", "json"], cwd=root,
                    input=json.dumps({"stop_hook_active": active}),
                    text=True, capture_output=True, timeout=60, check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                return json.loads(result.stdout)

            first = decide(False)
            self.assertEqual("block", first["decision"])
            self.assertIn("unresolved template token", first["reason"])
            again = decide(True)
            self.assertNotEqual("block", again.get("decision"), "must not re-block an already continued turn")
            self.assertIn("refract validation failed", again["systemMessage"])

    @unittest.skipUnless(shutil.which("omp"), "omp CLI not installed")
    def test_omp_cli_resolves_project_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            req = request(root, ["omp"])
            apply_plan(build_plan(root, render_project(req)), ["omp"])
            for key, expected in (("tools.approvalMode", "always-ask"), ("autolearn.enabled", "false")):
                result = subprocess.run(
                    ["omp", "config", "get", key], cwd=root,
                    text=True, capture_output=True, timeout=60, check=False,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual(expected, result.stdout.strip())

    @unittest.skipUnless(shutil.which("claude"), "Claude Code CLI not installed")
    def test_claude_parses_project_mcp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root, ["claude"], mcp=True)
            apply_plan(build_plan(root, render_project(req)), ["claude"])
            result = subprocess.run(
                ["claude", "mcp", "get", "context7"], cwd=root,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=30, check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout)
            self.assertIn("Scope: Project config", result.stdout)
            self.assertIn("Type: http", result.stdout)

    @unittest.skipUnless(shutil.which("codex"), "Codex CLI not installed")
    def test_codex_cli_parses_generated_toml_in_isolated_config_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root, ["codex"], mcp=True, agents=True)
            apply_plan(build_plan(root, render_project(req)), ["codex"])
            result = subprocess.run(
                ["codex", "mcp", "list", "--json"], cwd=root,
                env={**os.environ, "CODEX_HOME": str(root / ".codex")},
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30, check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            servers = json.loads(result.stdout)
            self.assertTrue(any(server["name"] == "context7" for server in servers))

    def test_shell_files_parse(self) -> None:
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash not installed")
        root = Path(__file__).resolve().parents[2]
        scripts = list((root / "scripts").glob("*.sh"))
        with tempfile.TemporaryDirectory() as directory:
            req = request(Path(directory), hooks=True)
            req.facts.build_command = "printf '%s\\n' build"
            req.facts.test_command = "python -c \"print('test')\""
            generated = render_project(req)
            for relative in (".githooks/pre-commit", "setup-hooks.sh"):
                path = Path(directory) / relative.replace("/", "_")
                path.write_bytes(generated[relative].content)
                scripts.append(path)
            for script in scripts:
                result = subprocess.run([bash, "-n", str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(0, result.returncode, result.stderr.decode())


if __name__ == "__main__":
    unittest.main()
