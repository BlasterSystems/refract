from __future__ import annotations

import hashlib
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
            self.assertNotIn(".claude/settings.json", files, "permission policy is opt-in")
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
            req = request(Path(directory), ["pi"], mcp=True, agents=True, hooks=True, permissions=True)
            files = render_project(req)
            self.assertIn("AGENTS.md", files)
            self.assertIn(".agents/skills/refract/SKILL.md", files)
            self.assertFalse(any(path.startswith(".pi/") for path in files))
            self.assertNotIn(".refract/bin/agent-check", files)
            effective = json.loads(files[".refract/config.json"].content)["features"]["effective_by_platform"]["pi"]
            self.assertEqual({"mcp": False, "agents": False, "hooks": False, "permissions": False}, effective)
            warnings = capability_warnings(req.features)
            self.assertTrue(any("deprecated" in warning for warning in warnings), warnings)
            self.assertTrue(any("no built-in MCP" in warning for warning in warnings), warnings)

    def test_omp_has_native_parity_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            req = request(Path(directory), ["omp"], mcp=True, agents=True, hooks=True, permissions=True)
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
            self.assertEqual({"mcp": True, "agents": True, "hooks": True, "permissions": True}, effective)
            plain = json.loads(render_project(request(Path(directory), ["omp"]))[".omp/settings.json"].content)
            self.assertEqual({"autolearn": {"enabled": False}}, plain, "only scope protection without --permissions")

    def test_claude_and_codex_ship_safe_policy_and_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files = render_project(request(Path(directory), ["claude", "codex"], hooks=True, permissions=True))
            claude = json.loads(files[".claude/settings.json"].content)
            self.assertIn("Read(./.env)", claude["permissions"]["deny"])
            self.assertNotIn("allow", claude["permissions"])
            stop = claude["hooks"]["Stop"][0]["hooks"][0]
            self.assertIn("CLAUDE_PROJECT_DIR", stop["command"])
            self.assertIn(".refract/bin/agent-check", stop["command"])
            self.assertIn(hashlib.sha256(files[".refract/bin/agent-check"].content).hexdigest(), stop["command"])
            self.assertIn(hashlib.sha256(files[".refract/bin/validate"].content).hexdigest(), stop["command"])
            codex = tomllib.loads(files[".codex/config.toml"].content.decode())
            self.assertEqual("on-request", codex["approval_policy"])
            self.assertEqual("workspace-write", codex["sandbox_mode"])
            self.assertFalse(codex["sandbox_workspace_write"]["network_access"])
            hooks = json.loads(files[".codex/hooks.json"].content)
            codex_command = hooks["hooks"]["Stop"][0]["hooks"][0]["command"]
            self.assertIn(hashlib.sha256(files[".refract/bin/validate"].content).hexdigest(), codex_command)
            plain = render_project(request(Path(directory), ["claude", "codex"]))
            self.assertNotIn(".claude/settings.json", plain)
            self.assertNotIn(".codex/hooks.json", plain)
            self.assertNotIn(".codex/config.toml", plain)

    def test_retrofit_keeps_unmanaged_platform_settings_without_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".claude").mkdir()
            (root / ".claude/settings.json").write_text('{"permissions": {"allow": ["Bash(npm test)"]}}\n')
            (root / ".codex").mkdir()
            (root / ".codex/config.toml").write_text('model = "o3"\n')
            plan = build_plan(root, render_project(request(root, ["claude", "codex"])))
            self.assertEqual([], plan.conflicts)
            conflicted = build_plan(root, render_project(request(root, ["claude", "codex"], permissions=True)))
            self.assertTrue(conflicted.conflicts, "unmanaged files are reported, never overwritten")

    def test_stop_hook_blocks_once_then_reports_and_refuses_tampered_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root, ["claude"], hooks=True)
            apply_plan(build_plan(root, render_project(req)), ["claude"])
            command = json.loads((root / ".claude/settings.json").read_text())["hooks"]["Stop"][0]["hooks"][0]["command"]

            def run_hook(active: bool) -> dict:
                result = subprocess.run(
                    ["bash", "-c", command], cwd=root,
                    env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)},
                    input=json.dumps({"stop_hook_active": active}),
                    text=True, capture_output=True, timeout=60, check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                return json.loads(result.stdout)

            self.assertEqual({}, run_hook(False))
            agents = root / "AGENTS.md"
            original = agents.read_text(encoding="utf-8")
            agents.write_text(original + "\nUser config lives in ~/.config/myapp/config.toml.\n", encoding="utf-8")
            self.assertEqual({}, run_hook(False), "documenting ~/ paths in AGENTS.md is legitimate")
            claude_md = root / "CLAUDE.md"
            claude_md.write_text(claude_md.read_text(encoding="utf-8") + "\nlocal note\n", encoding="utf-8")
            drift = run_hook(False)
            self.assertNotEqual("block", drift.get("decision"), "hash drift is reported, never forced to revert")
            self.assertIn("manifest-owned file content changed", drift["systemMessage"])
            agents.write_text("changed {" + "{TOKEN}}\n", encoding="utf-8")
            first = run_hook(False)
            self.assertEqual("block", first["decision"])
            self.assertIn("unresolved template token", first["reason"])
            again = run_hook(True)
            self.assertNotEqual("block", again.get("decision"), "must not re-block an already continued turn")
            self.assertIn("refract validation failed", again["systemMessage"])

            marker = root / "tampered"
            check = root / ".refract/bin/agent-check"
            shadow = root / ".refract/bin/json.py"
            shadow.write_text(f"open({str(marker)!r}, 'w').close()\nfrom json import *\n", encoding="utf-8")
            self.assertEqual("block", run_hook(False)["decision"])
            self.assertFalse(marker.exists(), "modules planted beside hook scripts must not be imported")
            shadow.unlink()

            check.write_text(check.read_text() + f"\nopen({str(marker)!r}, 'w').close()\n", encoding="utf-8")
            skipped = run_hook(False)
            self.assertIn("hook scripts do not match", skipped["systemMessage"])
            self.assertFalse(marker.exists(), "tampered hook script must not execute")

    def test_codex_hook_resolves_non_git_monorepo_subproject_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "mono/packages/app"
            project.mkdir(parents=True)
            apply_plan(build_plan(project, render_project(request(project, ["codex"], hooks=True))), ["codex"])
            command = json.loads((project / ".codex/hooks.json").read_text())["hooks"]["Stop"][0]["hooks"][0]["command"]
            nested = project / "src/module"
            nested.mkdir(parents=True)
            (project / "AGENTS.md").write_text("changed {" + "{TOKEN}}\n", encoding="utf-8")
            result = subprocess.run(
                ["bash", "-c", command], cwd=nested, input='{"stop_hook_active": false}',
                text=True, capture_output=True, timeout=60, check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            decision = json.loads(result.stdout)
            self.assertEqual("block", decision.get("decision"), decision)

    @unittest.skipUnless(shutil.which("omp"), "omp CLI not installed")
    def test_omp_cli_resolves_project_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            req = request(root, ["omp"], permissions=True)
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
