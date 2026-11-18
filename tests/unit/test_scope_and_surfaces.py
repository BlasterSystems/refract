from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from refract.apply import apply_plan
from refract.cli import main
from refract.paths import project_scope_problems
from refract.planner import build_plan
from refract.renderer import render_project
from refract.validation import validate_rendered, validate_target
from tests.helpers import request


class ProjectScopeTests(unittest.TestCase):
    def test_folder_of_repositories_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one/.git").mkdir(parents=True)
            (root / "group/two/.git").mkdir(parents=True)
            problems = project_scope_problems(root)
            self.assertEqual(1, len(problems), problems)
            self.assertIn("one", problems[0])
            self.assertIn("group/two", problems[0])

    def test_repository_root_and_empty_greenfield_target_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual([], project_scope_problems(root / "new-project"))
            self.assertEqual([], project_scope_problems(root))
            (root / ".git").mkdir()
            (root / "vendored/lib/.git").mkdir(parents=True)
            self.assertEqual([], project_scope_problems(root))

    def test_home_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("pathlib.Path.home", return_value=Path(directory)):
                self.assertTrue(project_scope_problems(Path(directory)))

    def test_cli_refuses_unscoped_target_unless_overridden(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a/.git").mkdir(parents=True)
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = main(["init", "--platform", "omp", "--dry-run", "--yes", "--target", str(root)])
            self.assertNotEqual(0, code)
            self.assertIn("nested repositories", stderr.getvalue())
            with redirect_stderr(io.StringIO()), mock.patch("sys.stdout", new=io.StringIO()):
                code = main([
                    "init", "--platform", "omp", "--dry-run", "--yes",
                    "--allow-unscoped-target", "--target", str(root),
                ])
            self.assertEqual(0, code)


class AgentSurfaceValidationTests(unittest.TestCase):
    def test_generated_output_has_no_surface_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files = render_project(request(Path(directory), mcp=True, agents=True, hooks=True))
            self.assertEqual([], validate_rendered(files))

    def test_global_scope_references_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root, ["omp"])
            apply_plan(build_plan(root, render_project(req)), ["omp"])
            (root / ".omp/RULES.md").write_text("Install skills into ~/.omp/agent/skills\n", encoding="utf-8")
            errors = validate_target(root)
            self.assertTrue(any("user/global scope" in error for error in errors), errors)

    def test_skill_mirror_drift_and_agent_front_matter_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            files = render_project(request(Path(directory), ["claude", "omp"], agents=True))
            mirror = ".claude/skills/docs-check/SKILL.md"
            files[mirror] = type(files[mirror])(mirror, files[mirror].content + b"\nextra\n")
            agent = ".omp/agents/architecture-reviewer.md"
            files[agent] = type(files[agent])(agent, b"---\nname: other\n---\nbody\n")
            errors = validate_rendered(files)
            self.assertTrue(any("differs from .agents/skills/docs-check" in error for error in errors), errors)
            self.assertTrue(any(agent in error and "agent front matter" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
