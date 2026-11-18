from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from refract.apply import apply_plan
from refract.model import CORE_SKILLS
from refract.planner import Action, build_plan
from refract.renderer import render_project
from tests.helpers import request

WORKFLOW = ("research", "confidence-check", "implement", "security-check", "quality-review", "commit")
RELEASE = ("deploy-dev", "deploy-prd", "hotfix")


class WorkflowSkillContractTests(unittest.TestCase):
    def render(self, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            return render_project(request(Path(directory), **kwargs))

    def test_workflow_and_release_skills_render_on_every_platform(self) -> None:
        files = self.render()
        for skill in WORKFLOW + RELEASE:
            self.assertIn(skill, CORE_SKILLS)
            portable = files[f".agents/skills/{skill}/SKILL.md"].content
            self.assertEqual(portable, files[f".claude/skills/{skill}/SKILL.md"].content, skill)
            self.assertIn(f".opencode/commands/{skill}.md", files)

    def test_skills_are_tracker_and_project_neutral(self) -> None:
        files = self.render()
        for skill in WORKFLOW + RELEASE:
            text = files[f".agents/skills/{skill}/SKILL.md"].content.decode()
            for token in ("Jira", "MWA-", "DMS", "atlassian", "Confluence", "dotnet", "Lambda"):
                self.assertNotIn(token, text, f"{skill} leaks project specifics: {token}")
            self.assertIsNone(re.search(r"https?://", text), f"{skill} hard-codes a URL")
            self.assertIsNone(re.search(r"\b[A-Z]{2,}-[0-9]+\b", text), f"{skill} hard-codes a ticket key")

    def test_deploy_skills_are_gated_on_configured_deployment_seed(self) -> None:
        files = self.render()
        seed = files["docs/DEPLOYMENT.md"]
        self.assertTrue(seed.mutable, "deployment parameters are project-owned")
        self.assertIn("Status: UNCONFIGURED", seed.content.decode())
        for skill in RELEASE:
            text = files[f".agents/skills/{skill}/SKILL.md"].content.decode()
            self.assertIn("explicitly asks", text, skill)
            self.assertIn("Confirm with the user", text, skill)
        for skill in RELEASE[:2]:
            text = files[f".agents/skills/{skill}/SKILL.md"].content.decode()
            self.assertIn(".refract/bin/deploy-ready", text)
            self.assertIn("regex", text)
            self.assertIn("numeric", text)
        prd = files[".agents/skills/deploy-prd/SKILL.md"].content.decode()
        for guard in ("approving review", "Never use administrator or bypass merges", "will be deleted", "Production never deploys from any other branch"):
            self.assertIn(guard, prd)

    def test_commit_skill_never_pushes_to_default_branch_or_without_request(self) -> None:
        text = self.render()[".agents/skills/commit/SKILL.md"].content.decode()
        for guard in ("Never commit or push directly to the default branch", "git diff --staged", "`security-check`", "Push only when the user asked", "Never force-push without explicit confirmation"):
            self.assertIn(guard, text)

    def test_deploy_ready_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apply_plan(build_plan(root, render_project(request(root))), ["claude"])
            seed = root / "docs/DEPLOYMENT.md"

            def ready() -> subprocess.CompletedProcess[str]:
                return subprocess.run([str(root / ".refract/bin/deploy-ready")], cwd=root, capture_output=True, text=True, timeout=30, check=False)

            self.assertEqual(1, ready().returncode, "the generated seed is not ready")
            text = seed.read_text(encoding="utf-8").replace("Status: UNCONFIGURED", "Status: CONFIGURED")
            seed.write_text(text, encoding="utf-8")
            partial = ready()
            self.assertEqual(1, partial.returncode)
            self.assertIn("Pre-deploy gates is not configured", partial.stdout)
            seed.write_text(re.sub(r"(?i)not configured", "configured: see runbook", text), encoding="utf-8")
            self.assertEqual(0, ready().returncode, ready().stdout)
            seed.write_text(seed.read_text(encoding="utf-8") + "\nStatus: UNCONFIGURED\n", encoding="utf-8")
            self.assertEqual(1, ready().returncode, "conflicting status lines are not ready")

    def test_customized_seeds_survive_reruns_and_flag_upstream_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = request(root, github=True)
            apply_plan(build_plan(root, render_project(req)), req.features.normalized_platforms())
            for relative in ("docs/DEPLOYMENT.md", "docs/branches/README.md", ".github/PULL_REQUEST_TEMPLATE.md"):
                (root / relative).write_text("customized\n", encoding="utf-8")
            plan = build_plan(root, render_project(req))
            self.assertEqual([], plan.conflicts)
            kept = {op.path: op for op in plan.operations if op.action == Action.NO_CHANGE}
            for relative in ("docs/DEPLOYMENT.md", "docs/branches/README.md", ".github/PULL_REQUEST_TEMPLATE.md"):
                self.assertIn("customized and is preserved", kept[relative].detail)
                self.assertNotIn("review the new version", kept[relative].detail)
            manifest = json.loads((root / ".refract/manifest.json").read_text())
            manifest["files"]["docs/DEPLOYMENT.md"]["sha256"] = "0" * 64
            (root / ".refract/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            upgraded = {op.path: op for op in build_plan(root, render_project(req)).operations}
            self.assertIn("review the new version manually", upgraded["docs/DEPLOYMENT.md"].detail)

    def test_unmanaged_same_named_files_are_reported_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs/DEPLOYMENT.md").write_text("ours\n", encoding="utf-8")
            (root / ".agents/skills/commit").mkdir(parents=True)
            (root / ".agents/skills/commit/SKILL.md").write_text("ours\n", encoding="utf-8")
            plan = build_plan(root, render_project(request(root)))
            self.assertEqual({"docs/DEPLOYMENT.md", ".agents/skills/commit/SKILL.md"}, {op.path for op in plan.conflicts})
            self.assertEqual("ours\n", (root / "docs/DEPLOYMENT.md").read_text())

    def test_seed_tag_regexes_compile_and_match_their_patterns(self) -> None:
        seed = self.render()["docs/DEPLOYMENT.md"].content.decode()
        rows = re.findall(r"\| `(dev|prd)-\{YYMMDD\}-\{N\}` \| `([^`]+)` \|", seed)
        self.assertEqual({"dev", "prd"}, {env for env, _ in rows})
        for env, pattern in rows:
            self.assertRegex(f"{env}-261118-3", re.compile(pattern))
            self.assertNotRegex(f"{env}-261118-3;rm -rf", re.compile(pattern))

    def test_process_and_templates_reference_the_workflow(self) -> None:
        files = self.render(github=True, ticket_prefix="ABC")
        process = files["docs/DEVELOPMENT_PROCESS.md"].content.decode()
        for skill in WORKFLOW + RELEASE:
            self.assertIn(f"`{skill}`", process)
        self.assertIn("## 7. Deploy", process)
        self.assertIn("## 9. Ticket lifecycle", process)
        self.assertIn("Ticket lifecycle section", files["docs/TASK_BREAKDOWN.md"].content.decode())
        template = files["tasks/task-template.md"].content.decode()
        for heading in ("## Implementation plan", "## Deployment", "## Completion summary"):
            self.assertIn(heading, template)
        pull_request = files[".github/PULL_REQUEST_TEMPLATE.md"]
        self.assertTrue(pull_request.mutable)
        self.assertIn("Deploy-affecting?", pull_request.content.decode())
        self.assertTrue(files["docs/branches/README.md"].mutable)
        self.assertNotIn(".github/PULL_REQUEST_TEMPLATE.md", self.render())

    def test_opencode_review_skills_run_in_plan_agent(self) -> None:
        files = self.render(platforms=["opencode"])
        for skill in ("security-check", "quality-review"):
            self.assertIn("\nagent: plan\n", files[f".opencode/commands/{skill}.md"].content.decode())
        for skill in ("confidence-check", "implement", "commit", "deploy-prd"):
            self.assertNotIn("agent: plan", files[f".opencode/commands/{skill}.md"].content.decode())


if __name__ == "__main__":
    unittest.main()
