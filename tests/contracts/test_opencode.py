from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from refract.apply import apply_plan
from refract.model import CORE_SKILLS
from refract.planner import build_plan
from refract.renderer import render_project
from tests.helpers import request


class OpenCodeContractTests(unittest.TestCase):
    def test_native_artifacts_and_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root, ["opencode"], agents=True, mcp=True)
            files = render_project(req)
            config = json.loads(files["opencode.json"].content)
            self.assertEqual("ask", config["permission"]["edit"])
            self.assertEqual("ask", config["permission"]["bash"])
            self.assertNotIn("model", config)
            self.assertNotIn("read", config["permission"], ".env read deny is part of opt-in permissions")
            restricted = json.loads(render_project(request(root, ["opencode"], permissions=True))["opencode.json"].content)
            self.assertEqual("deny", restricted["permission"]["read"]["*.env"])
            for skill in ("refract", "architecture-decision", "docs-check", "semantic-versioning"):
                command = files[f".opencode/commands/{skill}.md"].content.decode()
                self.assertTrue(command.startswith("---\ndescription: "), command)
                self.assertIn(f"`{skill}` skill", command)
                self.assertEqual(skill in {"refract", "docs-check"}, "\nagent: plan\n" in command, skill)
            self.assertNotIn(".opencode/plugins/refract-check.js", files)
            hooked = render_project(request(root, ["opencode"], hooks=True))
            self.assertIn(".opencode/plugins/refract-check.js", hooked)
            self.assertIn(".refract/bin/agent-check", hooked)
            self.assertIn(".opencode/agents/architecture-reviewer.md", files)
            self.assertIn(".agents/skills/refract/SKILL.md", files)
            self.assertIn(".agents/skills/architecture-decision/SKILL.md", files)
            self.assertIn(".agents/skills/semantic-versioning/SKILL.md", files)

    @unittest.skipUnless(shutil.which("opencode"), "OpenCode CLI not installed")
    def test_opencode_parses_generated_config_v2(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root, ["opencode"], agents=True)
            apply_plan(build_plan(root, render_project(req)), ["opencode"])
            env = {**os.environ, "XDG_CONFIG_HOME": str(root / "xdg")}
            result = subprocess.run(
                ["opencode", "debug", "config"],
                cwd=root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout)
            payload = json.loads(result.stdout)
            if isinstance(payload, dict):
                # Current opencode (>= 1.19) prints the merged effective
                # configuration document directly.
                self.assertEqual(
                    "ask", payload["permission"]["edit"],
                    f"unexpected effective config: {result.stdout}",
                )
                self.assertEqual(
                    "ask", payload["permission"]["bash"],
                    f"unexpected effective config: {result.stdout}",
                )
            elif isinstance(payload, list):
                generated = next(
                    (
                        entry["info"]
                        for entry in payload
                        if entry.get("type") == "document"
                        and entry.get("path", "").endswith("opencode.json")
                    ),
                    None,
                )
                self.assertIsNotNone(
                    generated,
                    f"no opencode.json document entry in: {result.stdout}",
                )
                effects = {
                    item["action"]: item["effect"] for item in generated["permissions"]
                }
                self.assertEqual("ask", effects["edit"])
                self.assertEqual("ask", effects["shell"])
            else:
                self.fail(f"unrecognized `opencode debug config` payload: {result.stdout}")
            # OpenCode v2 removed `debug skill` and `debug agent` and does not
            # list project agents; the agents/commands/skills surface is
            # verified on the filesystem instead.
            self.assertTrue((root / ".opencode/agents/architecture-reviewer.md").is_file())
            self.assertTrue((root / ".opencode/commands/architecture-decision.md").is_file())
            self.assertTrue((root / ".opencode/commands/docs-check.md").is_file())
            skills = {
                path.parent.name for path in (root / ".agents/skills").glob("*/SKILL.md")
            }
            self.assertEqual(set(CORE_SKILLS), skills)


if __name__ == "__main__":
    unittest.main()
