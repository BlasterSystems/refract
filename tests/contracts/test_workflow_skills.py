from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from refract.model import CORE_SKILLS
from refract.renderer import render_project
from tests.helpers import request

WORKFLOW = ("research", "confidence-check", "implement", "security-check", "code-review", "commit")
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

    def test_deploy_skills_are_gated_on_configured_deployment_seed(self) -> None:
        files = self.render()
        seed = files["docs/DEPLOYMENT.md"]
        self.assertTrue(seed.mutable, "deployment parameters are project-owned")
        self.assertIn("Status: UNCONFIGURED", seed.content.decode())
        for skill in RELEASE[:2]:
            text = files[f".agents/skills/{skill}/SKILL.md"].content.decode()
            self.assertIn("Status: UNCONFIGURED", text)
            self.assertIn("explicitly asks", text)
            self.assertIn("Confirm with the user", text)
            self.assertIn("regex", text)

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
        self.assertIn("(section 9)", files["docs/TASK_BREAKDOWN.md"].content.decode())
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
        for skill in ("confidence-check", "security-check", "code-review"):
            self.assertIn("\nagent: plan\n", files[f".opencode/commands/{skill}.md"].content.decode())
        for skill in ("implement", "commit", "deploy-prd"):
            self.assertNotIn("agent: plan", files[f".opencode/commands/{skill}.md"].content.decode())


if __name__ == "__main__":
    unittest.main()
