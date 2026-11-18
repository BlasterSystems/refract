from __future__ import annotations

import json

from ..model import GeneratedFile
from .base import AdapterContext
from .shared import CONTEXT7_URL


class OmpAdapter:
    name = "omp"

    def render(self, context: AdapterContext) -> dict[str, GeneratedFile]:
        # omp natively discovers standalone AGENTS.md and .agents/skills and
        # auto-registers /skill:<name> commands. Native project surfaces below
        # follow the omp contracts verified in docs/PLATFORM_SUPPORT.md.
        features = context.request.features
        templates = context.templates
        files = {
            ".omp/RULES.md": GeneratedFile.text(
                ".omp/RULES.md", templates.render("adapters/omp/RULES.md", context.values)
            ),
        }
        # Project settings layer. Auto-learn is always disabled: it mints
        # user-scope managed skills from this project's sessions, which then
        # load into every other project (scope protection, not a permission).
        # The ask-before-write/exec policy is opt-in like other platforms.
        settings: dict[str, object] = {"autolearn": {"enabled": False}}
        if features.permissions:
            settings["tools"] = {"approvalMode": "always-ask"}
        files[".omp/settings.json"] = GeneratedFile.text(".omp/settings.json", json.dumps(settings, indent=2))
        if features.agents:
            target = ".omp/agents/architecture-reviewer.md"
            files[target] = GeneratedFile.text(
                target, templates.render("adapters/omp/agents/architecture-reviewer.md", context.values)
            )
        if features.mcp:
            config = {"mcpServers": {"context7": {"type": "http", "url": CONTEXT7_URL}}}
            files[".omp/mcp.json"] = GeneratedFile.text(".omp/mcp.json", json.dumps(config, indent=2))
        if features.hooks:
            target = ".omp/hooks/post/refract-check.ts"
            files[target] = GeneratedFile.text(
                target, templates.render("adapters/omp/hooks/refract-check.ts", context.values)
            )
        return files
