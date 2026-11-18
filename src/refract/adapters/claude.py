from __future__ import annotations

import json

from ..model import CORE_SKILLS, GeneratedFile
from .base import AdapterContext
from .shared import CONTEXT7_URL, SECRET_GLOBS


class ClaudeAdapter:
    name = "claude"

    def render(self, context: AdapterContext) -> dict[str, GeneratedFile]:
        templates = context.templates
        values = context.values
        features = context.request.features
        files = {
            "CLAUDE.md": GeneratedFile.text(
                "CLAUDE.md", templates.render("adapters/claude/CLAUDE.md", values)
            ),
        }
        for skill in CORE_SKILLS:
            source = f"core/skills/{skill}/SKILL.md"
            target = f".claude/skills/{skill}/SKILL.md"
            files[target] = GeneratedFile.text(target, templates.render(source, values))

        # Committed, shared project policy. Claude's default mode already asks
        # before edits and shell commands; the project layer adds secret denies.
        # Personal allowlists belong in the uncommitted settings.local.json.
        settings: dict[str, object] = {
            "$schema": "https://json.schemastore.org/claude-code-settings.json",
            "permissions": {
                "deny": [f"Read(./{pattern})" for pattern in SECRET_GLOBS],
            },
        }
        if features.hooks:
            settings["hooks"] = {
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": '"$CLAUDE_PROJECT_DIR"/.refract/bin/agent-check --format json',
                                "timeout": 120,
                            }
                        ]
                    }
                ]
            }
        files[".claude/settings.json"] = GeneratedFile.text(
            ".claude/settings.json", json.dumps(settings, indent=2)
        )

        if features.agents:
            target = ".claude/agents/architecture-reviewer.md"
            files[target] = GeneratedFile.text(
                target, templates.render("adapters/claude/agents/architecture-reviewer.md", values)
            )
        if features.mcp:
            target = ".mcp.json"
            config = {"mcpServers": {"context7": {"type": "http", "url": CONTEXT7_URL}}}
            files[target] = GeneratedFile.text(target, json.dumps(config, indent=2))
        return files
