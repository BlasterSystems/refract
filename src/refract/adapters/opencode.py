from __future__ import annotations

import json

from ..model import CORE_SKILLS, GeneratedFile
from .base import AdapterContext
from .shared import CONTEXT7_URL, SECRET_GLOBS, skill_description


# Skills that only inspect and report run in OpenCode's read-only plan agent.
ADVISORY_SKILLS = {"refract", "docs-check", "confidence-check", "security-check", "code-review"}


def _frontmatter_value(value: str) -> str:
    # JSON strings are valid YAML double-quoted scalars.
    return json.dumps(value, ensure_ascii=False)


class OpenCodeAdapter:
    name = "opencode"

    def render(self, context: AdapterContext) -> dict[str, GeneratedFile]:
        features = context.request.features
        config: dict[str, object] = {
            "$schema": "https://opencode.ai/config.json",
            "permission": {
                "edit": "ask",
                "bash": "ask",
            },
        }
        if features.permissions:
            config["permission"]["read"] = {"*": "allow", **{f"*{pattern}": "deny" for pattern in SECRET_GLOBS}}  # type: ignore[index]
        if features.mcp:
            config["mcp"] = {
                "context7": {"type": "remote", "url": CONTEXT7_URL, "enabled": True}
            }
        files: dict[str, GeneratedFile] = {
            "opencode.json": GeneratedFile.text("opencode.json", json.dumps(config, indent=2)),
        }
        # One slash command per portable skill, derived from the skill list so
        # invocation stays at parity with the other platforms' native /<skill>.
        for skill in CORE_SKILLS:
            description = skill_description(
                context.templates.render(f"core/skills/{skill}/SKILL.md", context.values)
            )
            target = f".opencode/commands/{skill}.md"
            agent = "agent: plan\n" if skill in ADVISORY_SKILLS else ""
            body = (
                f"---\ndescription: {_frontmatter_value(description)}\n{agent}---\n\n"
                f"Load and follow the `{skill}` skill for this request.\n\n$ARGUMENTS"
            )
            files[target] = GeneratedFile.text(target, body)
        if features.agents:
            target = ".opencode/agents/architecture-reviewer.md"
            files[target] = GeneratedFile.text(
                target,
                context.templates.render("adapters/opencode/agents/architecture-reviewer.md", context.values),
            )
        if features.hooks:
            target = ".opencode/plugins/refract-check.js"
            files[target] = GeneratedFile.text(
                target, context.templates.render("adapters/opencode/plugins/refract-check.js", context.values)
            )
        return files
