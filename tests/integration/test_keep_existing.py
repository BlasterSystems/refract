from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from refract.apply import apply_plan
from refract.cli import main
from refract.migration import existing_setup_findings, plan_findings
from refract.planner import Action, build_plan
from refract.renderer import render_project
from refract.validation import validate_target
from tests.helpers import request


def legacy_project(root: Path) -> None:
    """A repository with a hand-made, Claude-only agent setup."""
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "AGENTS.md").write_text("# Our agents guide\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# Claude notes without an import\n", encoding="utf-8")
    for skill in ("research", "dms-build"):
        (root / f".claude/skills/{skill}").mkdir(parents=True)
        (root / f".claude/skills/{skill}/SKILL.md").write_text(f"---\nname: {skill}\ndescription: ours\n---\n", encoding="utf-8")
    (root / ".claude/settings.local.json").write_text("{}\n", encoding="utf-8")
    (root / ".claude/claude.json").write_text("{}\n", encoding="utf-8")
    (root / ".pi").mkdir()
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "add", "-f", ".claude/settings.local.json"], cwd=root, check=True)


class KeepExistingRetrofitTests(unittest.TestCase):
    def test_default_retrofit_still_stops_on_unmanaged_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_project(root)
            plan = build_plan(root, render_project(request(root)))
            paths = {op.path for op in plan.conflicts}
            self.assertIn("AGENTS.md", paths)
            self.assertIn(".claude/skills/research/SKILL.md", paths)
            self.assertTrue(all("--keep-existing" in op.detail for op in plan.conflicts))

    def test_keep_existing_keeps_user_files_and_skill_groups_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_project(root)
            desired = render_project(request(root))
            plan = build_plan(root, desired, keep_existing=True)
            self.assertEqual([], plan.conflicts)
            by_path = {op.path: op for op in plan.operations}
            self.assertEqual(Action.SKIP_UNMANAGED, by_path["AGENTS.md"].action)
            self.assertEqual(Action.SKIP_UNMANAGED, by_path[".claude/skills/research/SKILL.md"].action)
            for sibling in (".agents/skills/research/SKILL.md", ".opencode/commands/research.md"):
                self.assertEqual(Action.SKIP_KEPT, by_path[sibling].action, sibling)
            self.assertEqual(Action.CREATE, by_path[".agents/skills/implement/SKILL.md"].action)

            apply_plan(plan, ["claude", "codex", "opencode", "omp"])
            self.assertEqual("# Our agents guide\n", (root / "AGENTS.md").read_text())
            self.assertIn("description: ours", (root / ".claude/skills/research/SKILL.md").read_text())
            self.assertFalse((root / ".agents/skills/research").exists())
            manifest = json.loads((root / ".refract/manifest.json").read_text())["files"]
            self.assertNotIn("AGENTS.md", manifest, "kept files are never adopted")
            self.assertNotIn(".agents/skills/research/SKILL.md", manifest)
            self.assertEqual([], validate_target(root))

            rerun = build_plan(root, render_project(request(root)), keep_existing=True)
            self.assertEqual([], rerun.changes[:-1] if rerun.changes and rerun.changes[-1].action == Action.MANIFEST_UPDATE else rerun.changes,
                             "a second keep-existing run is idempotent")

    def test_modified_refract_owned_files_still_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root)
            apply_plan(build_plan(root, render_project(req)), req.features.normalized_platforms())
            (root / ".agents/skills/commit/SKILL.md").write_text("edited\n", encoding="utf-8")
            plan = build_plan(root, render_project(req), keep_existing=True)
            self.assertEqual([".agents/skills/commit/SKILL.md"], [op.path for op in plan.conflicts])

    def test_existing_setup_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_project(root)
            findings = "\n".join(existing_setup_findings(root))
            self.assertIn("settings.local.json is committed", findings)
            self.assertIn("claude.json is not a Claude Code configuration", findings)
            self.assertIn("deprecated Pi", findings)
            self.assertIn("only in .claude/skills (dms-build, research)", findings)
            self.assertIn("does not import @AGENTS.md", findings)

    def test_cli_keep_existing_reports_kept_and_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_project(root)
            stderr, stdout = io.StringIO(), io.StringIO()
            with redirect_stderr(stderr), redirect_stdout(stdout):
                code = main(["retrofit", "--platform", "claude,codex,opencode,omp", "--keep-existing",
                             "--dry-run", "--yes", "--target", str(root)])
            self.assertEqual(0, code, stderr.getvalue())
            self.assertIn("SKIP_KEPT", stdout.getvalue())
            self.assertIn("skill 'research': project-owned at .claude/skills/research/SKILL.md", stderr.getvalue())
            self.assertIn("agents that read only those locations have no 'research' skill", stderr.getvalue())
            self.assertIn("settings.local.json is committed", stderr.getvalue())

    def test_git_config_helpers_never_execute_during_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            legacy_project(root)
            marker = Path(directory) / "PWNED"
            subprocess.run(["git", "config", "core.fsmonitor", f"touch {marker}; false"], cwd=root, check=True)
            findings = existing_setup_findings(root)
            self.assertFalse(marker.exists(), "repository git config must not run commands")
            self.assertTrue(any("settings.local.json is committed" in item for item in findings), findings)

    def test_refract_control_paths_are_never_kept(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".refract/bin").mkdir(parents=True)
            (root / ".refract/bin/validate").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            (root / ".refract/config.json").write_text('{"project":{"commands":{"test":"echo INJECTED"}}}', encoding="utf-8")
            (root / ".githooks").mkdir()
            (root / ".githooks/pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
            plan = build_plan(root, render_project(request(root, hooks=True)), keep_existing=True)
            conflicts = {op.path: op.detail for op in plan.conflicts}
            for path in (".refract/bin/validate", ".refract/config.json", ".githooks/pre-commit"):
                self.assertIn(path, conflicts)
                self.assertIn("cannot be kept", conflicts[path])

    def test_kept_opencode_command_does_not_suppress_skills_elsewhere(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".opencode/commands").mkdir(parents=True)
            (root / ".opencode/commands/implement.md").write_text("---\ndescription: ours\n---\n", encoding="utf-8")
            by_path = {op.path: op.action for op in build_plan(root, render_project(request(root)), keep_existing=True).operations}
            self.assertEqual(Action.SKIP_UNMANAGED, by_path[".opencode/commands/implement.md"])
            self.assertEqual(Action.CREATE, by_path[".agents/skills/implement/SKILL.md"])
            self.assertEqual(Action.CREATE, by_path[".claude/skills/implement/SKILL.md"])

    def test_partially_managed_skill_group_reports_the_split(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apply_plan(build_plan(root, render_project(request(root, ["codex"]))), ["codex"])
            (root / ".claude/skills/commit").mkdir(parents=True)
            (root / ".claude/skills/commit/SKILL.md").write_text("---\nname: commit\ndescription: ours\n---\n", encoding="utf-8")
            plan = build_plan(root, render_project(request(root)), keep_existing=True)
            text = "\n".join(plan_findings(plan))
            self.assertIn("refract's copy remains at .agents/skills/commit/SKILL.md", text)
            self.assertIn("agents will see different 'commit' skills", text)

    def test_repository_controlled_names_cannot_inject_terminal_escapes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_project(root)
            hostile = root / ".claude/skills/evil\x1b[2Jclear"
            hostile.mkdir()
            (hostile / "SKILL.md").write_text("---\nname: x\ndescription: x\n---\n", encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                main(["retrofit", "--platform", "claude", "--keep-existing", "--dry-run", "--yes", "--target", str(root)])
            self.assertNotIn("\x1b", stderr.getvalue())
            self.assertIn("evil\\u001b[2Jclear", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
